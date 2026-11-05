
"""PostgreSQL execution utilities for DB-TestGen R2."""

import os
from contextlib import contextmanager

import psycopg

from app.models import DBMSSQLTestCase, DBMSSQLValidationResult


@contextmanager
def postgres_test_connection():
    """Provide a PostgreSQL connection that always rolls back."""

    database_url = os.getenv("DBTESTGEN_POSTGRES_URL")

    if not database_url:
        raise RuntimeError(
            "DBTESTGEN_POSTGRES_URL is not configured"
        )

    connection = psycopg.connect(
        database_url,
        autocommit=False,
        connect_timeout=5,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            cursor.execute(
                "SET LOCAL search_path = dbtestgen_sandbox"
            )

        yield connection

    finally:
        connection.rollback()
        connection.close()


def validate_postgres_sql_test(
    test_case: DBMSSQLTestCase,
    *,
    trusted_sql: bool = False,
) -> DBMSSQLValidationResult:
    """Validate a trusted SQL test in a rolled-back transaction.

    This is not an arbitrary SQL sandbox. The caller must explicitly
    opt in with trusted_sql=True. Do not pass LLM-generated SQL.
    """

    if not trusted_sql:
        raise ValueError(
            "PostgreSQL execution currently requires trusted_sql=True"
        )
    
    if test_case.sql_dialect != "postgresql":
        raise ValueError(
            "PostgreSQL executor requires sql_dialect='postgresql'"
        )

    errors = []
    mismatches = []
    setup_successful = False
    execution_successful = False
    assertion_passed = False
    actual_outcome = ""
    expected = test_case.expected_outcome

    def build_result(status):
        return DBMSSQLValidationResult(
            test_case_id=test_case.id,
            scenario_id=test_case.scenario_id,
            status=status,
            setup_successful=setup_successful,
            execution_successful=execution_successful,
            assertion_passed=assertion_passed,
            expected_outcome=expected.assertion_description,
            actual_outcome=actual_outcome,
            errors=errors + mismatches,
        )

    if test_case.verification_sql:
        errors.append(
            "Legacy verification_sql is not supported"
        )

    if (
        expected.outcome_type == "error"
        and not expected.expected_error
    ):
        errors.append("Expected SQL error is missing")

    if expected.outcome_type == "rows":
        errors.append("Rows outcome is not yet supported")

    if (
        expected.outcome_type == "database_state"
        and not test_case.verification_assertions
    ):
        errors.append(
            "Database-state outcome requires verification assertions"
        )

    if errors:
        return build_result("error")

    try:
        with postgres_test_connection() as connection:
            with connection.cursor() as cursor:

                # 1. Establish preconditions.
                for statement in test_case.setup_sql:
                    cursor.execute(statement)

                setup_successful = True

                # 2. Execute the operation under a savepoint.
                cursor.execute("SAVEPOINT test_operation")

                try:
                    cursor.execute(test_case.test_sql)
                    execution_successful = True

                    if expected.outcome_type == "error":
                        mismatches.append(
                            "Expected SQL error did not occur"
                        )
                        actual_outcome = "SQL succeeded"

                    elif expected.outcome_type == "scalar":
                        row = cursor.fetchone()
                        actual_value = (
                            row[0] if row is not None else None
                        )
                        actual_outcome = repr(actual_value)

                        if actual_value != expected.expected_value:
                            mismatches.append(
                                f"Expected {expected.expected_value!r}, "
                                f"got {actual_value!r}"
                            )

                    elif expected.outcome_type == "row_count":
                        actual_value = cursor.rowcount
                        actual_outcome = str(actual_value)

                        if actual_value != expected.expected_value:
                            mismatches.append(
                                f"Expected row count "
                                f"{expected.expected_value!r}, "
                                f"got {actual_value!r}"
                            )

                    else:
                        actual_outcome = (
                            "SQL executed; checking database state"
                        )

                    cursor.execute(
                        "RELEASE SAVEPOINT test_operation"
                    )

                except psycopg.Error as exc:
                    actual_outcome = str(exc)

                    cursor.execute(
                        "ROLLBACK TO SAVEPOINT test_operation"
                    )
                    cursor.execute(
                        "RELEASE SAVEPOINT test_operation"
                    )

                    if expected.outcome_type == "error":
                        if (
                            expected.expected_error.lower()
                            not in str(exc).lower()
                        ):
                            mismatches.append(
                                f"Expected error "
                                f"{expected.expected_error!r}, "
                                f"got {exc!s}"
                            )
                    else:
                        errors.append(
                            f"Unexpected SQL execution error: {exc}"
                        )

                # 3. Verify database state.
                for verification in test_case.verification_assertions:
                    cursor.execute(verification.query)
                    rows = cursor.fetchall()

                    if verification.expected_rows is not None:
                        actual_rows = [
                            list(row) for row in rows
                        ]

                        if actual_rows != verification.expected_rows:
                            mismatches.append(
                                f"Verification failed: "
                                f"{verification.query}; "
                                f"expected "
                                f"{verification.expected_rows!r}, "
                                f"got {actual_rows!r}"
                            )

                    elif verification.expected_scalar is not None:
                        if len(rows) != 1 or len(rows[0]) != 1:
                            mismatches.append(
                                f"Expected one scalar result from "
                                f"{verification.query}, got {rows!r}"
                            )
                        elif (
                            rows[0][0]
                            != verification.expected_scalar
                        ):
                            mismatches.append(
                                f"Verification failed: "
                                f"{verification.query}; "
                                f"expected "
                                f"{verification.expected_scalar!r}, "
                                f"got {rows[0][0]!r}"
                            )
                    else:
                        errors.append(
                            "Verification assertion has no expected value"
                        )

    except psycopg.Error as exc:
        errors.append(
            f"PostgreSQL setup or verification error: {exc}"
        )

    if errors:
        status = "error"
    elif mismatches:
        status = "failed"
    else:
        status = "passed"
        assertion_passed = True

    return build_result(status)
