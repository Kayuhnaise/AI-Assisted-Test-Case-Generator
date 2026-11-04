
from app.dbms_r2_oracle import evaluate_independent_oracle
from app.models import DBMSSQLTestCase


def make_test_case(test_sql, setup_sql):
    return DBMSSQLTestCase.model_validate(
        {
            "id": "SQL-001",
            "scenario_id": "R2-001",
            "title": "Independent oracle test",
            "category": "positive",
            "sql_dialect": "sqlite",
            "preconditions": [],
            "constraints": [],
            "setup_sql": setup_sql,
            "test_sql": test_sql,
            "verification_assertions": [],
            "verification_sql": [],
            "expected_outcome": {
                "outcome_type": "database_state",
                "assertion_description": (
                    "Check resulting database state"
                ),
            },
            "cleanup_sql": [],
        }
    )


def test_independent_oracle_passes_correct_insert():
    case = make_test_case(
        "INSERT INTO users VALUES (2, 'bob@example.com')",
        [
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)",
            "INSERT INTO users VALUES (1, 'alice@example.com')",
        ],
    )

    oracle = {
        "expected_outcome_type": "database_state",
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM users",
                "expected_scalar": 2,
            }
        ],
    }

    result = evaluate_independent_oracle(case, oracle)

    assert result["passed"] is True


def test_independent_oracle_detects_wrong_result():
    case = make_test_case(
        "INSERT INTO users VALUES (2, 'bob@example.com')",
        [
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)",
            "INSERT INTO users VALUES (1, 'alice@example.com')",
        ],
    )

    oracle = {
        "expected_outcome_type": "database_state",
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM users",
                "expected_scalar": 3,
            }
        ],
    }

    result = evaluate_independent_oracle(case, oracle)

    assert result["passed"] is False
    assert result["assertions_passed"] is False


def test_independent_oracle_passes_expected_error():
    case = make_test_case(
        "INSERT INTO users VALUES (2, 'alice@example.com')",
        [
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)",
            "INSERT INTO users VALUES (1, 'alice@example.com')",
        ],
    )

    oracle = {
        "expected_outcome_type": "error",
        "expected_error": "UNIQUE constraint failed",
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM users",
                "expected_scalar": 1,
            }
        ],
    }

    result = evaluate_independent_oracle(case, oracle)

    assert result["passed"] is True
    assert result["execution_successful"] is False
    assert result["operation_matched"] is True


def test_independent_oracle_detects_missing_error():
    case = make_test_case(
        "INSERT INTO users VALUES (2, 'bob@example.com')",
        [
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)",
            "INSERT INTO users VALUES (1, 'alice@example.com')",
        ],
    )

    oracle = {
        "expected_outcome_type": "error",
        "expected_error": "UNIQUE constraint failed",
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM users",
                "expected_scalar": 2,
            }
        ],
    }

    result = evaluate_independent_oracle(case, oracle)

    assert result["passed"] is False
    assert result["operation_matched"] is False


def test_independent_oracle_detects_missing_table():
    case = make_test_case(
        "SELECT 1",
        [],
    )

    oracle = {
        "expected_outcome_type": "database_state",
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM users",
                "expected_scalar": 0,
            }
        ],
    }

    result = evaluate_independent_oracle(case, oracle)

    assert result["passed"] is False
    assert result["assertions_passed"] is False


def test_independent_oracle_rejects_empty_assertions():
    case = make_test_case(
        "SELECT 1",
        [],
    )

    oracle = {
        "expected_outcome_type": "database_state",
        "verification_assertions": [],
    }

    result = evaluate_independent_oracle(case, oracle)

    assert result["passed"] is False
