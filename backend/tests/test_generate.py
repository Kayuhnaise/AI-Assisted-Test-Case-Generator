import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    GeneratedScenarios,
    GeneratedTestCases,
    Scenario,
    TestCase as GeneratedCase,
)
from app.test_runner import run_pytest


client = TestClient(app)


def _ollama_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


def test_generate_identifies_scenarios_then_executes_runnable_pytest():
    source_code = (
        "def check_login(attempts: int) -> str:\n"
        "    if attempts >= 5:\n"
        "        return 'locked'\n"
        "    return 'allowed'\n"
    )
    scenario = Scenario(
        id="bnd_1",
        category="boundary",
        description="Exactly five failed attempts locks the account.",
    )
    test_case = GeneratedCase(
        id="tc_1",
        scenario_id="bnd_1",
        title="Lock at the threshold",
        test_type="boundary",
        preconditions=[],
        steps=["Call check_login with five failed attempts."],
        expected_result="The account is locked.",
        pytest_code=(
            "def test_bnd_1_locks_at_threshold():\n"
            "    assert check_login(5) == 'locked'\n"
        ),
    )
    responses = [
        _ollama_response(
            GeneratedScenarios(scenarios=[scenario]).model_dump_json()
        ),
        _ollama_response(
            GeneratedTestCases(test_cases=[test_case]).model_dump_json()
        ),
    ]

    with patch("app.generator.ollama.chat", side_effect=responses) as chat:
        response = client.post(
            "/generate",
            json={
                "requirement": (
                    "The system shall lock an account after five "
                    "consecutive failed login attempts."
                ),
                "source_code": source_code,
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert [item["id"] for item in result["scenarios"]] == ["bnd_1"]
    assert result["test_cases"][0]["scenario_id"] == "bnd_1"
    assert "check_login(5) == 'locked'" in result["pytest_code"]
    assert result["pytest_result"]["status"] == "passed"
    assert result["pytest_result"]["tests_run"] == 1
    assert result["pytest_result"]["passed"] == 1
    assert chat.call_count == 2
    generation_prompt = chat.call_args_list[1].kwargs["messages"][1]["content"]
    assert "Exactly five failed attempts locks the account." in generation_prompt


def test_generate_returns_failed_pytest_result_for_failing_assertion():
    scenario = Scenario(
        id="pos_1",
        category="positive",
        description="The example returns true.",
    )
    test_case = GeneratedCase(
        id="tc_1",
        scenario_id="pos_1",
        title="Failing test",
        test_type="positive",
        preconditions=[],
        steps=[],
        expected_result="True",
        pytest_code="def test_failure():\n    assert example() is False\n",
    )
    responses = [
        _ollama_response(
            GeneratedScenarios(scenarios=[scenario]).model_dump_json()
        ),
        _ollama_response(
            GeneratedTestCases(test_cases=[test_case]).model_dump_json()
        ),
    ]

    with patch("app.generator.ollama.chat", side_effect=responses):
        response = client.post(
            "/generate",
            json={
                "requirement": "An example function returns true.",
                "source_code": "def example():\n    return True\n",
            },
        )

    assert response.status_code == 200
    result = response.json()["pytest_result"]
    assert result["status"] == "failed"
    assert result["tests_run"] == 1
    assert result["failed"] == 1


def test_pytest_runner_reports_timeout():
    with patch(
        "app.test_runner.subprocess.run",
        side_effect=subprocess.TimeoutExpired("pytest", 15, output="still running"),
    ):
        result = run_pytest("def test_example():\n    assert True\n")

    assert result.status == "timeout"
    assert result.exit_code is None
    assert result.stdout == "still running"


def test_generate_rejects_test_cases_that_do_not_cover_all_scenarios():
    from app.generator import generate_test_cases

    scenarios = [
        Scenario(id="pos_1", category="positive", description="A normal case."),
        Scenario(id="bnd_1", category="boundary", description="The limit case."),
    ]
    only_test_case = GeneratedCase(
        id="tc_1",
        scenario_id="pos_1",
        title="Normal case",
        test_type="positive",
        preconditions=[],
        steps=[],
        expected_result="It succeeds.",
        pytest_code="def test_pos_1():\n    assert True\n",
    )

    with patch(
        "app.generator.ollama.chat",
        return_value=_ollama_response(
            GeneratedTestCases(test_cases=[only_test_case]).model_dump_json()
        ),
    ):
        with pytest.raises(ValueError, match="cover every identified scenario"):
            generate_test_cases(
                "A valid example requirement.",
                "def example():\n    return True\n",
                scenarios,
            )


def test_generate_rejects_invalid_python_source_without_calling_model():
    with patch("app.generator.ollama.chat") as chat:
        response = client.post(
            "/generate",
            json={
                "requirement": "A valid example requirement.",
                "source_code": "def incomplete(:\n    pass\n",
            },
        )

    assert response.status_code == 422
    chat.assert_not_called()
