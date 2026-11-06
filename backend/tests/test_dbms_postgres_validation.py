
import pytest

from app.dbms_postgres_executor import validate_postgres_sql_test
from app.models import DBMSSQLTestCase


def test_postgres_insert_validation():
    test_case = DBMSSQLTestCase.model_validate({
        "id": "PG-001",
        "scenario_id": "PG-SC-001",
        "title": "Insert valid customer",
        "category": "positive",
        "sql_dialect": "postgresql",
        "preconditions": [],
        "constraints": [],
        "setup_sql": [
            "CREATE TABLE customers ("
            "id INTEGER PRIMARY KEY, "
            "name TEXT NOT NULL)"
        ],
        "test_sql": (
            "INSERT INTO customers (id, name) "
            "VALUES (1, 'Alice')"
        ),
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM customers",
                "expected_scalar": 1
            }
        ],
        "expected_outcome": {
            "outcome_type": "database_state",
            "assertion_description": (
                "One customer should exist after insertion"
            )
        }
    })

    result = validate_postgres_sql_test(
        test_case,
        trusted_sql=True,
    )

    assert result.status == "passed"
    assert result.setup_successful
    assert result.execution_successful
    assert result.assertion_passed


def test_postgres_rejects_untrusted_execution():
    with pytest.raises(ValueError, match="trusted_sql"):
        validate_postgres_sql_test(
            DBMSSQLTestCase.model_validate({
                "id": "PG-002",
                "scenario_id": "PG-SC-002",
                "title": "Untrusted SQL rejection",
                "category": "negative",
                "sql_dialect": "postgresql",
                "preconditions": [],
                "constraints": [],
                "setup_sql": [],
                "test_sql": "SELECT 1",
                "expected_outcome": {
                    "outcome_type": "scalar",
                    "expected_value": 1,
                    "assertion_description": "Return 1"
                }
            })
        )


def test_postgres_expected_not_null_error():
    test_case = DBMSSQLTestCase.model_validate({
        "id": "PG-003",
        "scenario_id": "PG-SC-003",
        "title": "Reject customer without a name",
        "category": "negative",
        "sql_dialect": "postgresql",
        "preconditions": [],
        "constraints": ["name must not be NULL"],
        "setup_sql": [
            "CREATE TABLE customers ("
            "id INTEGER PRIMARY KEY, "
            "name TEXT NOT NULL)"
        ],
        "test_sql": (
            "INSERT INTO customers (id, name) "
            "VALUES (1, NULL)"
        ),
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM customers",
                "expected_scalar": 0
            }
        ],
        "expected_outcome": {
            "outcome_type": "error",
            "expected_error": "null value",
            "assertion_description": (
                "PostgreSQL rejects a NULL customer name"
            )
        }
    })

    result = validate_postgres_sql_test(
        test_case,
        trusted_sql=True,
    )

    assert result.status == "passed"
    assert result.setup_successful
    assert not result.execution_successful
    assert result.assertion_passed


def test_postgres_detects_incorrect_expected_state():
    test_case = DBMSSQLTestCase.model_validate({
        "id": "PG-004",
        "scenario_id": "PG-SC-004",
        "title": "Detect incorrect row count",
        "category": "negative",
        "sql_dialect": "postgresql",
        "preconditions": [],
        "constraints": [],
        "setup_sql": [
            "CREATE TABLE customers ("
            "id INTEGER PRIMARY KEY)"
        ],
        "test_sql": (
            "INSERT INTO customers (id) VALUES (1)"
        ),
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM customers",
                "expected_scalar": 2
            }
        ],
        "expected_outcome": {
            "outcome_type": "database_state",
            "assertion_description": (
                "Two customers should exist"
            )
        }
    })

    result = validate_postgres_sql_test(
        test_case,
        trusted_sql=True,
    )

    assert result.status == "failed"
    assert not result.assertion_passed


def test_postgres_savepoint_rollback_keeps_prior_transaction_work():
    test_case = DBMSSQLTestCase.model_validate({
        "id": "PG-TX-001",
        "scenario_id": "PG-TX-SC-001",
        "title": "Roll back only work after a savepoint",
        "category": "edge",
        "sql_dialect": "postgresql",
        "preconditions": [],
        "constraints": [],
        "setup_sql": [
            "CREATE TABLE audit_log ("
            "id INTEGER PRIMARY KEY, message TEXT NOT NULL)"
        ],
        "test_sql": (
            "INSERT INTO audit_log VALUES (1, 'before savepoint'); "
            "SAVEPOINT transaction_work; "
            "INSERT INTO audit_log VALUES (2, 'after savepoint'); "
            "ROLLBACK TO SAVEPOINT transaction_work; "
            "RELEASE SAVEPOINT transaction_work"
        ),
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM audit_log",
                "expected_scalar": 1,
            },
            {
                "query": "SELECT message FROM audit_log",
                "expected_scalar": "before savepoint",
            },
        ],
        "expected_outcome": {
            "outcome_type": "database_state",
            "assertion_description": (
                "Work before the savepoint remains and later work is rolled back"
            ),
        },
    })

    result = validate_postgres_sql_test(
        test_case,
        trusted_sql=True,
    )

    assert result.status == "passed"
    assert result.setup_successful
    assert result.execution_successful
    assert result.assertion_passed


def test_postgres_rejects_sqlite_dialect():
    test_case = DBMSSQLTestCase.model_validate({
        "id": "PG-005",
        "scenario_id": "PG-SC-005",
        "title": "Reject SQLite dialect",
        "category": "negative",
        "sql_dialect": "sqlite",
        "preconditions": [],
        "constraints": [],
        "setup_sql": [],
        "test_sql": "SELECT 1",
        "expected_outcome": {
            "outcome_type": "scalar",
            "expected_value": 1,
            "assertion_description": "Return one"
        }
    })

    with pytest.raises(ValueError, match="postgresql"):
        validate_postgres_sql_test(
            test_case,
            trusted_sql=True,
        )
