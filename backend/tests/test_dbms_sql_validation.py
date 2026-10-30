
from app.models import (
    DBMSSQLTestCase,
    SQLExpectedOutcome,
    SQLVerificationAssertion,
)
from app.dbms_sql_validator import (
    validate_sql_test,
    validate_sql_tests,
)


def make_sql_case(
    test_sql: str,
    outcome_type: str,
    expected_value=None,
    expected_error=None,
):
    return DBMSSQLTestCase(
        id="SQL-001",
        scenario_id="DBMS-001",
        title="SQL validation test",
        category="negative",
        sql_dialect="sqlite",
        preconditions=["A users table exists"],
        constraints=["id is a primary key"],
        setup_sql=[
            "CREATE TABLE users (id INTEGER PRIMARY KEY)",
            "INSERT INTO users VALUES (1)",
        ],
        test_sql=test_sql,
        expected_outcome=SQLExpectedOutcome(
            outcome_type=outcome_type,
            expected_value=expected_value,
            expected_error=expected_error,
            assertion_description="Verify SQL behavior",
        ),
    )


def test_expected_constraint_error_passes():
    case = make_sql_case(
        test_sql="INSERT INTO users VALUES (1)",
        outcome_type="error",
        expected_error="UNIQUE constraint failed",
    )

    result = validate_sql_test(case)

    assert result.status == "passed"
    assert result.assertion_passed


def test_missing_expected_error_fails():
    case = make_sql_case(
        test_sql="INSERT INTO users VALUES (2)",
        outcome_type="error",
        expected_error="UNIQUE constraint failed",
    )

    result = validate_sql_test(case)

    assert result.status == "failed"


def test_scalar_query_passes():
    case = make_sql_case(
        test_sql="SELECT COUNT(*) FROM users",
        outcome_type="scalar",
        expected_value=1,
    )

    result = validate_sql_test(case)

    assert result.status == "passed"


def test_wrong_expected_value_fails():
    case = make_sql_case(
        test_sql="SELECT COUNT(*) FROM users",
        outcome_type="scalar",
        expected_value=2,
    )

    result = validate_sql_test(case)

    assert result.status == "failed"


def test_invalid_setup_returns_error():
    case = make_sql_case(
        test_sql="SELECT COUNT(*) FROM users",
        outcome_type="scalar",
        expected_value=1,
    )

    case.setup_sql = [
        "CREATE TABLE invalid syntax"
    ]

    result = validate_sql_test(case)

    assert result.status == "error"
    assert not result.setup_successful


def test_validity_percentage():
    passing = make_sql_case(
        "SELECT COUNT(*) FROM users",
        "scalar",
        expected_value=1,
    )

    failing = make_sql_case(
        "SELECT COUNT(*) FROM users",
        "scalar",
        expected_value=2,
    )

    failing.id = "SQL-002"
    failing.scenario_id = "DBMS-002"

    result = validate_sql_tests(
        [passing, failing]
    )

    assert result.total_tests == 2
    assert result.passed == 1
    assert result.failed == 1
    assert result.validity_percentage == 50.0
    assert not result.target_met


def test_successful_update_preserves_state_for_verification():
    case = make_sql_case(
        test_sql="UPDATE users SET id = 2 WHERE id = 1",
        outcome_type="database_state",
    )

    case.verification_assertions = [
        SQLVerificationAssertion(
            query="SELECT id FROM users",
            expected_scalar=2,
        )
    ]

    result = validate_sql_test(case)

    assert result.status == "passed"
    assert result.assertion_passed


def test_incorrect_post_update_state_fails():
    case = make_sql_case(
        test_sql="UPDATE users SET id = 2 WHERE id = 1",
        outcome_type="database_state",
    )

    case.verification_assertions = [
        SQLVerificationAssertion(
            query="SELECT id FROM users",
            expected_scalar=3,
        )
    ]

    result = validate_sql_test(case)

    assert result.status != "passed"
    assert not result.assertion_passed


def test_failed_constraint_preserves_original_state():
    case = make_sql_case(
        test_sql="INSERT INTO users VALUES (1)",
        outcome_type="error",
        expected_error="UNIQUE constraint failed",
    )

    case.verification_assertions = [
        SQLVerificationAssertion(
            query="SELECT COUNT(*) FROM users",
            expected_scalar=1,
        )
    ]

    result = validate_sql_test(case)

    assert result.status == "passed"
    assert result.assertion_passed


def test_wrong_state_after_expected_error_fails():
    case = make_sql_case(
        test_sql="INSERT INTO users VALUES (1)",
        outcome_type="error",
        expected_error="UNIQUE constraint failed",
    )

    case.verification_assertions = [
        SQLVerificationAssertion(
            query="SELECT COUNT(*) FROM users",
            expected_scalar=2,
        )
    ]

    result = validate_sql_test(case)

    assert result.status != "passed"


def test_database_state_requires_assertions():
    case = make_sql_case(
        test_sql="UPDATE users SET id = 2 WHERE id = 1",
        outcome_type="database_state",
    )

    result = validate_sql_test(case)

    assert result.status == "error"
    assert not result.assertion_passed


def test_legacy_verification_sql_cannot_establish_validity():
    case = make_sql_case(
        test_sql="SELECT COUNT(*) FROM users",
        outcome_type="scalar",
        expected_value=1,
    )

    case.verification_sql = [
        "SELECT COUNT(*) FROM users"
    ]

    result = validate_sql_test(case)

    assert result.status == "error"
