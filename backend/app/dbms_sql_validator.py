
import sqlite3

from app.models import (
    DBMSSQLTestCase,
    DBMSSQLValidationResult,
    DBMSSQLValidationResponse,
)


VALIDITY_TARGET = 90.0


def validate_sql_test(
    test_case: DBMSSQLTestCase,
) -> DBMSSQLValidationResult:

    setup_successful = False
    execution_successful = False
    assertion_passed = False
    actual_outcome = ""
    errors = []
    mismatches = []

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

    # Check that the test has a usable expected outcome.
    if (
        expected.outcome_type == "error"
        and not expected.expected_error
    ):
        errors.append("Expected SQL error message is missing")

    if test_case.verification_sql:
        errors.append(
            "Legacy verification_sql has no expected results. "
            "Use verification_assertions instead."
        )

    if (
        expected.outcome_type == "database_state"
        and not test_case.verification_assertions
    ):
        errors.append(
            "database_state requires verification_assertions"
        )

    if expected.outcome_type == "rows":
        errors.append(
            "rows outcome type is not yet supported"
        )

    if errors:
        actual_outcome = "Invalid test configuration"
        return build_result("error")

    connection = sqlite3.connect(":memory:")

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        # 1. Establish the database preconditions.
        for statement in test_case.setup_sql:
            connection.execute(statement)

        connection.commit()
        setup_successful = True

        # 2. Execute the operation under test.
        connection.execute("SAVEPOINT test_operation")

        try:
            cursor = connection.execute(test_case.test_sql)
            execution_successful = True

            if expected.outcome_type == "error":
                actual_outcome = (
                    "SQL succeeded, but an error was expected"
                )
                mismatches.append(
                    "Expected SQL error did not occur"
                )

            elif expected.outcome_type == "scalar":
                row = cursor.fetchone()
                actual_value = (
                    row[0] if row is not None else None
                )
                actual_outcome = repr(actual_value)

                if actual_value != expected.expected_value:
                    mismatches.append(
                        f"Expected scalar {expected.expected_value!r}, "
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

            elif expected.outcome_type == "database_state":
                actual_outcome = (
                    "SQL executed; checking resulting state"
                )

            # Successful changes remain visible to verification.
            connection.execute(
                "RELEASE SAVEPOINT test_operation"
            )

        except sqlite3.Error as exc:
            actual_outcome = str(exc)

            if expected.outcome_type == "error":
                if (
                    expected.expected_error.lower()
                    not in str(exc).lower()
                ):
                    mismatches.append(
                        f"Expected error "
                        f"{expected.expected_error!r}, "
                        f"got {str(exc)!r}"
                    )
            else:
                errors.append(
                    f"Unexpected SQL execution error: {exc}"
                )

            # Restore state before the rejected operation.
            connection.execute(
                "ROLLBACK TO SAVEPOINT test_operation"
            )
            connection.execute(
                "RELEASE SAVEPOINT test_operation"
            )

        # 3. Verify the database state.
        for verification in test_case.verification_assertions:
            try:
                rows = connection.execute(
                    verification.query
                ).fetchall()

                if verification.expected_rows is not None:
                    actual_rows = [
                        list(row) for row in rows
                    ]

                    if actual_rows != verification.expected_rows:
                        mismatches.append(
                            f"Verification failed for "
                            f"{verification.query}: "
                            f"expected {verification.expected_rows!r}, "
                            f"got {actual_rows!r}"
                        )

                elif verification.expected_scalar is not None:
                    if len(rows) == 1 and len(rows[0]) == 1:
                        actual_scalar = rows[0][0]
                    else:
                        mismatches.append(
                            f"Expected one scalar result from "
                            f"{verification.query}, "
                            f"got {rows!r}"
                        )
                        continue

                    if (
                        actual_scalar
                        != verification.expected_scalar
                    ):
                        mismatches.append(
                            f"Verification failed for "
                            f"{verification.query}: "
                            f"expected "
                            f"{verification.expected_scalar!r}, "
                            f"got {actual_scalar!r}"
                        )

                else:
                    errors.append(
                        "Verification assertion has no "
                        "expected value"
                    )

            except sqlite3.Error as exc:
                errors.append(
                    f"Verification SQL error: {exc}"
                )

    except sqlite3.Error as exc:
        errors.append(
            f"Database setup or transaction error: {exc}"
        )

    finally:
        connection.close()

    if errors:
        status = "error"
    elif mismatches:
        status = "failed"
    else:
        status = "passed"
        assertion_passed = True

    return build_result(status)


def validate_sql_tests(
    test_cases: list[DBMSSQLTestCase],
) -> DBMSSQLValidationResponse:

    if not test_cases:
        raise ValueError(
            "At least one SQL test case is required"
        )

    results = [
        validate_sql_test(test_case)
        for test_case in test_cases
    ]

    passed = sum(
        result.status == "passed"
        for result in results
    )

    failed = sum(
        result.status == "failed"
        for result in results
    )

    errors = sum(
        result.status == "error"
        for result in results
    )

    validity_percentage = (
        100.0 * passed / len(results)
    )

    return DBMSSQLValidationResponse(
        total_tests=len(results),
        passed=passed,
        failed=failed,
        errors=errors,
        validity_percentage=validity_percentage,
        target_percentage=VALIDITY_TARGET,
        target_met=(
            validity_percentage >= VALIDITY_TARGET
        ),
        results=results,
    )
