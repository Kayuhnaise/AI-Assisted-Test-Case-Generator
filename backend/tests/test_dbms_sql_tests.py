from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import DBMSSQLTestPackage, GeneratedDBMSSQLTests, DBMSScenario


client = TestClient(app)


def _scenario(scenario_id: str = "DB-001") -> DBMSScenario:
    return DBMSScenario(
        id=scenario_id,
        category="negative",
        precondition="The users table contains one email address.",
        behavior_under_test="Insert a second row with the same email address.",
        expected_result="PostgreSQL rejects the duplicate with SQLSTATE 23505.",
    )


def _package(scenario_id: str = "DB-001") -> DBMSSQLTestPackage:
    return DBMSSQLTestPackage(
        test_id="SQL-001",
        scenario_id=scenario_id,
        setup_sql=(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE);"
        ),
        data_sql="INSERT INTO users VALUES (1, 'a@example.com');",
        test_sql="INSERT INTO users VALUES (2, 'a@example.com');",
        expected_outcome="error",
        expected_sqlstate="23505",
        cleanup_sql="DROP TABLE users;",
    )


def _ollama_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


def test_generate_dbms_sql_tests_returns_traceable_package():
    generated = GeneratedDBMSSQLTests(tests=[_package()])
    with patch(
        "app.dbms_sql_tests.ollama.chat",
        return_value=_ollama_response(generated.model_dump_json()),
    ) as chat:
        response = client.post(
            "/dbms/sql-tests/generate",
            json={
                "postgres_version": "17",
                "scenarios": [_scenario().model_dump()],
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["postgres_version"] == "17"
    assert result["tests"][0]["scenario_id"] == "DB-001"
    assert result["tests"][0]["expected_sqlstate"] == "23505"
    assert "PostgreSQL major version: 17" in (
        chat.call_args.kwargs["messages"][1]["content"]
    )


def test_sql_test_generation_rejects_missing_scenario_package():
    response_content = GeneratedDBMSSQLTests(
        tests=[_package("unexpected-id")]
    ).model_dump_json()
    with patch(
        "app.dbms_sql_tests.ollama.chat",
        return_value=_ollama_response(response_content),
    ):
        response = client.post(
            "/dbms/sql-tests/generate",
            json={"scenarios": [_scenario().model_dump()]},
        )

    assert response.status_code == 502
    assert "every supplied scenario exactly once" in response.json()["detail"]


def test_error_package_requires_valid_postgres_sqlstate():
    values = _package().model_dump()
    values["expected_sqlstate"] = "not-a-code"
    with pytest.raises(ValueError):
        DBMSSQLTestPackage.model_validate(values)


def test_success_package_cannot_include_sqlstate():
    values = _package().model_dump()
    values["expected_outcome"] = "success"
    with pytest.raises(ValueError, match="must not include a SQLSTATE"):
        DBMSSQLTestPackage.model_validate(values)


def test_request_rejects_duplicate_scenario_ids_before_model_call():
    with patch("app.dbms_sql_tests.ollama.chat") as chat:
        response = client.post(
            "/dbms/sql-tests/generate",
            json={"scenarios": [_scenario().model_dump()] * 2},
        )

    assert response.status_code == 422
    chat.assert_not_called()
