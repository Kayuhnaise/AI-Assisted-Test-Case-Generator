import os
import time
import uuid

import psycopg
from psycopg import sql
from sqlglot import exp

from app.dbms_sql_validation import parse_and_validate_sql
from app.models import (
    DBMSSQLExecutionResponse,
    DBMSSQLExecutionResult,
    DBMSSQLTestPackage,
)


def execute_dbms_sql_tests(
    packages: list[DBMSSQLTestPackage],
    database_url: str | None = None,
) -> DBMSSQLExecutionResponse:
    dsn = database_url or os.getenv("DBMS_TEST_DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DBMS_TEST_DATABASE_URL must point to a dedicated, non-superuser "
            "PostgreSQL test database"
        )

    results = []
    for package in packages:
        parsed, validation_errors = parse_and_validate_sql(package)
        if validation_errors:
            raise ValueError(
                f"Test {package.test_id} failed SQL validation: "
                + "; ".join(validation_errors)
            )
        started = time.monotonic()
        result = _execute_package(dsn, package, parsed, started)
        results.append(result)
    return DBMSSQLExecutionResponse(results=results)


def _execute_package(
    dsn: str,
    package: DBMSSQLTestPackage,
    parsed: dict[str, list[exp.Expression]],
    started: float,
) -> DBMSSQLExecutionResult:
    schema_name = f"dbtest_{uuid.uuid4().hex}"
    actual_sqlstate: str | None = None
    status = "error"
    detail: str | None = None

    try:
        with psycopg.connect(
            dsn,
            connect_timeout=5,
            options="-c statement_timeout=5000 -c lock_timeout=1000",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("CREATE SCHEMA {}").format(
                        sql.Identifier(schema_name)
                    )
                )
                cursor.execute(
                    sql.SQL("SET LOCAL search_path TO {}").format(
                        sql.Identifier(schema_name)
                    )
                )
                for field in ("setup_sql", "data_sql"):
                    _execute_statements(cursor, parsed[field])

                cursor.execute("SAVEPOINT dbms_test_operation")
                try:
                    _execute_statements(cursor, parsed["test_sql"])
                except psycopg.Error as exc:
                    actual_sqlstate = exc.sqlstate
                    cursor.execute(
                        "ROLLBACK TO SAVEPOINT dbms_test_operation"
                    )
                    cursor.execute(
                        "RELEASE SAVEPOINT dbms_test_operation"
                    )
                    if actual_sqlstate == package.expected_sqlstate:
                        status = "passed"
                    else:
                        status = "failed"
                        detail = (
                            f"Expected SQLSTATE {package.expected_sqlstate}, "
                            f"received {actual_sqlstate or 'none'}: "
                            f"{str(exc).strip().splitlines()[0][:400]}"
                        )
                else:
                    cursor.execute(
                        "RELEASE SAVEPOINT dbms_test_operation"
                    )
                    if package.expected_outcome == "success":
                        status = "passed"
                    else:
                        status = "failed"
                        detail = (
                            "Expected SQLSTATE "
                            f"{package.expected_sqlstate}, but the test SQL "
                            "completed successfully"
                        )

                _execute_statements(cursor, parsed["cleanup_sql"])
            connection.rollback()
    except psycopg.Error as exc:
        status = "error"
        actual_sqlstate = exc.sqlstate
        detail = str(exc).strip().splitlines()[0][:500]

    return DBMSSQLExecutionResult(
        test_id=package.test_id,
        scenario_id=package.scenario_id,
        status=status,
        expected_sqlstate=package.expected_sqlstate,
        actual_sqlstate=actual_sqlstate,
        duration_ms=(time.monotonic() - started) * 1000,
        detail=detail,
    )


def _execute_statements(
    cursor: psycopg.Cursor,
    statements: list[exp.Expression],
) -> None:
    for statement in statements:
        cursor.execute(statement.sql(dialect="postgres"))
