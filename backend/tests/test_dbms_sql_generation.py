
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    DBMSSQLTestCase,
    GeneratedDBMSSQLTests,
    SQLExpectedOutcome,
    SQLVerificationAssertion,
)


client = TestClient(app)


def test_dbms_sql_generation():
    generated_case = DBMSSQLTestCase(
        id="SQL-001",
        scenario_id="DBMS-001",
        title="Reject duplicate primary key",
        category="negative",
        sql_dialect="sqlite",
        preconditions=["A users table exists"],
        constraints=["id is a primary key"],
        setup_sql=[
            "CREATE TABLE users (id INTEGER PRIMARY KEY);",
            "INSERT INTO users VALUES (1);",
        ],
        test_sql="INSERT INTO users VALUES (1);",
        verification_sql=[],
        verification_assertions=[
            SQLVerificationAssertion(
                query="SELECT COUNT(*) FROM users",
                expected_scalar=1,
            )
        ],
        expected_outcome=SQLExpectedOutcome(
            outcome_type="error",
            expected_error="UNIQUE constraint failed",
            assertion_description=(
                "Duplicate primary key insertion is rejected"
            ),
        ),
        cleanup_sql=["DROP TABLE users;"],
    )

    mock_response = SimpleNamespace(
        message=SimpleNamespace(
            content=GeneratedDBMSSQLTests(
                test_cases=[generated_case]
            ).model_dump_json()
        )
    )

    request = {
        "requirement_document": (
            "The database shall reject duplicate primary keys."
        ),
        "scenarios": [
            {
                "id": "DBMS-001",
                "category": "negative",
                "precondition": "A row already exists.",
                "behavior_under_test": (
                    "Insert another row with the same key."
                ),
                "expected_result": (
                    "The insertion is rejected."
                ),
            }
        ],
    }

    with patch(
        "app.dbms_sql_generator.ollama.chat",
        return_value=mock_response,
    ):
        response = client.post(
            "/dbms/generate",
            json=request,
        )

    assert response.status_code == 200

    result = response.json()
    assert len(result["test_cases"]) == 1

    test_case = result["test_cases"][0]

    assert test_case["scenario_id"] == "DBMS-001"
    assert test_case["category"] == "negative"
    assert test_case["sql_dialect"] == "sqlite"
    assert test_case["expected_outcome"]["outcome_type"] == "error"
