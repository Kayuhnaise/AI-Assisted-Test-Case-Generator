
import sqlite3

from app.models import DBMSSQLTestCase


def evaluate_independent_oracle(
    test_case: DBMSSQLTestCase,
    oracle: dict,
) -> dict:
    """
    Execute a generated SQL test in an isolated SQLite
    database and compare its behavior against an
    independently defined benchmark oracle.

    Use only with trusted local benchmark inputs.
    """

    result = {
        "passed": False,
        "setup_successful": False,
        "execution_successful": False,
        "operation_matched": False,
        "assertions_passed": False,
        "assertion_results": [],
        "errors": [],
    }

    connection = sqlite3.connect(":memory:")

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        # 1. Establish the generated preconditions.
        for statement in test_case.setup_sql:
            connection.execute(statement)

        connection.commit()
        result["setup_successful"] = True

        # 2. Execute the generated operation.
        connection.execute("SAVEPOINT oracle_operation")

        operation_error = None

        try:
            connection.execute(test_case.test_sql)
            result["execution_successful"] = True

            connection.execute(
                "RELEASE SAVEPOINT oracle_operation"
            )

        except sqlite3.Error as exc:
            operation_error = str(exc)

            connection.execute(
                "ROLLBACK TO SAVEPOINT oracle_operation"
            )
            connection.execute(
                "RELEASE SAVEPOINT oracle_operation"
            )

        # 3. Compare the operation against the
        # independently defined expected behavior.
        expected_type = oracle["expected_outcome_type"]

        if expected_type == "error":
            expected_error = oracle.get("expected_error")

            result["operation_matched"] = (
                operation_error is not None
                and bool(expected_error)
                and expected_error.lower()
                in operation_error.lower()
            )

            if not result["operation_matched"]:
                result["errors"].append(
                    "Expected SQL error "
                    f"{expected_error!r}, "
                    f"got {operation_error!r}"
                )

        else:
            result["operation_matched"] = (
                operation_error is None
            )

            if operation_error is not None:
                result["errors"].append(
                    f"Unexpected SQL error: {operation_error}"
                )

        # 4. Execute independent database-state
        # assertions against the resulting database.
        assertions = oracle.get(
            "verification_assertions", []
        )

        if not assertions:
            result["errors"].append(
                "Independent oracle has no assertions"
            )

        for assertion in assertions:
            query = assertion["query"]
            expected_scalar = assertion["expected_scalar"]

            try:
                rows = connection.execute(query).fetchall()

                if len(rows) != 1 or len(rows[0]) != 1:
                    actual = rows
                    passed = False
                else:
                    actual = rows[0][0]
                    passed = (
                        type(actual) is type(expected_scalar)
                        and actual == expected_scalar
                    )

                result["assertion_results"].append(
                    {
                        "query": query,
                        "expected": expected_scalar,
                        "actual": actual,
                        "passed": passed,
                    }
                )

                if not passed:
                    result["errors"].append(
                        f"Oracle assertion failed: {query}"
                    )

            except sqlite3.Error as exc:
                result["assertion_results"].append(
                    {
                        "query": query,
                        "expected": expected_scalar,
                        "actual": None,
                        "passed": False,
                    }
                )

                result["errors"].append(
                    f"Oracle query failed: {query}: {exc}"
                )

        result["assertions_passed"] = (
            bool(assertions)
            and len(result["assertion_results"])
            == len(assertions)
            and all(
                item["passed"]
                for item in result["assertion_results"]
            )
        )

        result["passed"] = (
            result["operation_matched"]
            and result["assertions_passed"]
        )

    except sqlite3.Error as exc:
        result["errors"].append(
            f"SQLite setup or transaction error: {exc}"
        )

    finally:
        connection.close()

    return result
