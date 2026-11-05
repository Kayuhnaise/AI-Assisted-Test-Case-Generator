from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.dbms_coverage import analyze_lcov_report
from app.dbms_sql_execution import _execute_package
from app.dbms_sql_validation import validate_dbms_sql_tests
from app.main import app
from app.models import (
    DBMSRefinementRequest,
    DBMSSQLTestPackage,
    DBMSScenario,
    GeneratedDBMSSQLScenarios,
    GeneratedDBMSSQLTests,
)


client = TestClient(app)


def _package(
    *,
    test_sql: str = "INSERT INTO users VALUES (2, 'a@example.com');",
    expected_outcome: str = "error",
    expected_sqlstate: str | None = "23505",
) -> DBMSSQLTestPackage:
    return DBMSSQLTestPackage(
        test_id="SQL-001",
        scenario_id="DB-001",
        setup_sql=(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE);"
        ),
        data_sql="INSERT INTO users VALUES (1, 'a@example.com');",
        test_sql=test_sql,
        expected_outcome=expected_outcome,
        expected_sqlstate=expected_sqlstate,
        cleanup_sql="DROP TABLE users;",
    )


def _scenario() -> DBMSScenario:
    return DBMSScenario(
        id="DB-001",
        category="negative",
        precondition="The users table contains one email address.",
        behavior_under_test="Insert a duplicate email.",
        expected_result="The insert is rejected with SQLSTATE 23505.",
    )


def _ollama_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


def test_validator_accepts_complete_unique_constraint_package():
    response = validate_dbms_sql_tests([_package()])
    assert response.valid is True
    assert response.results[0].scenario_id == "DB-001"


def test_validator_rejects_syntax_errors_and_privileged_statements():
    invalid = _package(test_sql="DROP DATABASE postgres;")
    response = validate_dbms_sql_tests([invalid])
    assert response.valid is False
    assert "not allowed" in response.results[0].errors[0]


def test_validator_rejects_cross_schema_object_references():
    response = validate_dbms_sql_tests(
        [_package(test_sql="SELECT * FROM public.users;")]
    )
    assert response.valid is False
    assert "schema-qualified" in response.results[0].errors[0]


def test_validator_rejects_non_allowlisted_functions():
    response = validate_dbms_sql_tests(
        [
            _package(
                test_sql="SELECT pg_sleep(30);",
                expected_outcome="success",
                expected_sqlstate=None,
            )
        ]
    )
    assert response.valid is False
    assert "pg_sleep" in response.results[0].errors[0]


def test_validator_rejects_schema_qualified_functions():
    response = validate_dbms_sql_tests(
        [
            _package(
                test_sql="SELECT public.generate_series(1, 2);",
                expected_outcome="success",
                expected_sqlstate=None,
            )
        ]
    )
    assert response.valid is False
    assert "schema-qualified function" in response.results[0].errors[0]


def test_lcov_analysis_reports_postgres_modules_and_uncovered_features():
    report_text = "\n".join(
        [
            "TN:",
            "SF:/postgres/src/backend/parser/gram.y",
            "FN:1:raw_parser",
            "FNDA:2,raw_parser",
            "DA:1,2",
            "DA:2,0",
            "BRDA:2,0,0,1",
            "BRDA:2,0,1,0",
            "end_of_record",
            "TN:",
            "SF:/postgres/src/backend/optimizer/path/pathkeys.c",
            "FN:3:build_path",
            "FNDA:0,build_path",
            "DA:3,0",
            "DA:4,1",
            "end_of_record",
        ]
    )
    response = client.post(
        "/dbms/coverage/analyze",
        json={"lcov_report": report_text},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["files_analyzed"] == 2
    assert report["line_coverage"]["covered"] == 2
    assert report["line_coverage"]["total"] == 4
    assert {hint["feature"] for hint in report["feature_hints"]} == {
        "SQL parsing and syntax",
        "Query planning and optimization",
    }


def test_lcov_parser_rejects_counters_outside_a_file_record():
    with pytest.raises(ValueError, match="outside a record"):
        analyze_lcov_report("DA:1,1")


def test_lcov_feature_hint_includes_branch_only_coverage_gaps():
    report = analyze_lcov_report(
        "\n".join(
            [
                "SF:/postgres/src/backend/parser/gram.y",
                "DA:1,1",
                "BRDA:1,0,0,1",
                "BRDA:1,0,1,0",
                "end_of_record",
            ]
        )
    )
    assert report.line_coverage.percentage == 100
    assert report.branch_coverage.percentage == 50
    assert report.feature_hints[0].feature == "SQL parsing and syntax"


def test_coverage_guided_generation_uses_report_feature_hints():
    report = analyze_lcov_report(
        "SF:/postgres/src/backend/parser/gram.y\nDA:1,0\nend_of_record\n"
    )
    generated = GeneratedDBMSSQLScenarios(
        scenarios=[
            _scenario().model_copy(
                update={
                    "id": "ignored",
                    "behavior_under_test": (
                        "Parse a valid nested SELECT expression."
                    ),
                }
            )
        ]
    )
    with patch(
        "app.dbms_refinement.ollama.chat",
        return_value=_ollama_response(generated.model_dump_json()),
    ) as chat:
        result = client.post(
            "/dbms/coverage/generate",
            json={
                "requirement_document": "PostgreSQL parses SELECT statements.",
                "coverage_report": report.model_dump(mode="json"),
            },
        )

    assert result.status_code == 200
    body = result.json()
    assert body["targeted_features"] == ["SQL parsing and syntax"]
    assert body["scenarios"][0]["id"] == "coverage_1"
    assert "SQL parsing and syntax" in (
        chat.call_args.kwargs["messages"][1]["content"]
    )


def test_refinement_preserves_expected_oracle_and_test_context():
    package = _package()
    repaired = package.model_copy(
        update={"test_sql": "INSERT INTO users (id, email) VALUES (2, 'a@example.com');"}
    )
    generated = GeneratedDBMSSQLTests(tests=[repaired])
    with patch(
        "app.dbms_refinement.ollama.chat",
        return_value=_ollama_response(generated.model_dump_json()),
    ):
        response = client.post(
            "/dbms/refine",
            json=DBMSRefinementRequest(
                scenario=_scenario(),
                failed_test=package,
                error_message="column count mismatch",
                actual_sqlstate="42601",
            ).model_dump(mode="json"),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["oracle_preserved"] is True
    assert body["repaired_test"]["expected_sqlstate"] == "23505"
    assert body["repaired_test"]["setup_sql"] == package.setup_sql


def test_refinement_rejects_a_repair_that_changes_the_oracle():
    package = _package()
    invalid_repair = package.model_copy(
        update={"expected_outcome": "success", "expected_sqlstate": None}
    )
    with patch(
        "app.dbms_refinement.ollama.chat",
        return_value=_ollama_response(
            GeneratedDBMSSQLTests(tests=[invalid_repair]).model_dump_json()
        ),
    ):
        response = client.post(
            "/dbms/refine",
            json={
                "scenario": _scenario().model_dump(),
                "failed_test": package.model_dump(),
                "error_message": "test failed",
            },
        )

    assert response.status_code == 502
    assert "expected oracle" in response.json()["detail"]


def test_execute_endpoint_requires_a_configured_database():
    with patch.dict("os.environ", {}, clear=False):
        from os import environ

        environ.pop("DBMS_TEST_DATABASE_URL", None)
        response = client.post(
            "/dbms/sql-tests/execute",
            json={"tests": [_package().model_dump()]},
        )
    assert response.status_code == 503
    assert "DBMS_TEST_DATABASE_URL" in response.json()["detail"]


def test_invalid_sql_is_not_sent_to_the_executor():
    package = _package(test_sql="DROP DATABASE postgres;")
    with patch("app.main.execute_dbms_sql_tests") as execute:
        response = client.post(
            "/dbms/sql-tests/execute",
            json={"tests": [package.model_dump()]},
        )
    assert response.status_code == 422
    execute.assert_not_called()


def test_expected_unique_violation_counts_as_a_pass():
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    parsed = {
        "setup_sql": [],
        "data_sql": [],
        "test_sql": [],
        "cleanup_sql": [],
    }
    with (
        patch("app.dbms_sql_execution.psycopg.connect", return_value=connection),
        patch(
            "app.dbms_sql_execution._execute_statements",
            side_effect=[
                None,
                None,
                psycopg.errors.UniqueViolation("duplicate key"),
                None,
            ],
        ),
    ):
        result = _execute_package("postgresql://test", _package(), parsed, 0)

    assert result.status == "passed"
    assert result.expected_sqlstate == result.actual_sqlstate == "23505"
    connection.rollback.assert_called_once()


def test_unexpected_sqlstate_reports_error_feedback_for_refinement():
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    parsed = {
        "setup_sql": [],
        "data_sql": [],
        "test_sql": [],
        "cleanup_sql": [],
    }
    with (
        patch("app.dbms_sql_execution.psycopg.connect", return_value=connection),
        patch(
            "app.dbms_sql_execution._execute_statements",
            side_effect=[
                None,
                None,
                psycopg.errors.CheckViolation("check constraint failed"),
                None,
            ],
        ),
    ):
        result = _execute_package("postgresql://test", _package(), parsed, 0)

    assert result.status == "failed"
    assert result.actual_sqlstate == "23514"
    assert "check constraint failed" in result.detail
