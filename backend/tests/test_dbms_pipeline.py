from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import DBMSScenario, DBMSSQLTestCase


client = TestClient(app)


def test_pipeline_connects_extraction_to_postgres_sql_generation():
    scenario = DBMSScenario(
        id="DOC-001",
        category="boundary",
        precondition="The inventory table is empty.",
        behavior_under_test="Insert an item with quantity zero.",
        expected_result="The insert is rejected.",
    )
    test_case = DBMSSQLTestCase.model_validate({
        "id": "SQL-001",
        "scenario_id": "DOC-001",
        "title": "Reject zero quantity",
        "category": "boundary",
        "sql_dialect": "postgresql",
        "preconditions": [],
        "constraints": [],
        "setup_sql": ["CREATE TABLE inventory (quantity INTEGER CHECK (quantity > 0))"],
        "test_sql": "INSERT INTO inventory VALUES (0)",
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM inventory",
                "expected_scalar": 0,
            }
        ],
        "expected_outcome": {
            "outcome_type": "error",
            "expected_error": "check constraint",
            "assertion_description": "Zero quantity is rejected",
        },
    })

    with (
        patch(
            "app.main.identify_dbms_scenarios",
            return_value=[scenario],
        ) as extract,
        patch(
            "app.main.generate_dbms_sql_tests",
            return_value=[test_case],
        ) as generate,
    ):
        response = client.post(
            "/dbms/pipeline/generate",
            json={
                "requirement_document": (
                    "Inventory quantities must be positive."
                )
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["review_required"] is True
    assert result["sql_dialect"] == "postgresql"
    assert [item["id"] for item in result["scenarios"]] == ["DOC-001"]
    assert [item["scenario_id"] for item in result["test_cases"]] == [
        "DOC-001"
    ]
    extract.assert_called_once_with(
        "Inventory quantities must be positive."
    )
    generate.assert_called_once_with(
        requirement_document="Inventory quantities must be positive.",
        scenarios=[scenario],
        dialect="postgresql",
    )


def test_pipeline_accepts_explicit_sqlite_dialect():
    scenario = DBMSScenario(
        id="DOC-002",
        category="positive",
        precondition="A table exists.",
        behavior_under_test="Read a row.",
        expected_result="The row is returned.",
    )

    with (
        patch(
            "app.main.identify_dbms_scenarios",
            return_value=[scenario],
        ),
        patch(
            "app.main.generate_dbms_sql_tests",
            return_value=[],
        ) as generate,
    ):
        response = client.post(
            "/dbms/pipeline/generate",
            json={
                "requirement_document": "Rows are readable.",
                "sql_dialect": "sqlite",
            },
        )

    assert response.status_code == 200
    assert response.json()["sql_dialect"] == "sqlite"
    generate.assert_called_once_with(
        requirement_document="Rows are readable.",
        scenarios=[scenario],
        dialect="sqlite",
    )
