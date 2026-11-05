from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.dbms_scenarios import evaluate_dbms_scenario_coverage
from app.main import app
from app.models import (
    DBMSScenario,
    GeneratedDBMSScenarios,
    ScenarioPairJudgment,
    ScenarioPairJudgments,
)


client = TestClient(app)


def _ollama_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


def _scenario(scenario_id: str) -> DBMSScenario:
    return DBMSScenario(
        id=scenario_id,
        category="positive",
        precondition="The database contains a committed account row.",
        behavior_under_test="Select the account by its primary key.",
        expected_result="The query returns the matching account row.",
    )


def _judgment(
    expert_id: str,
    extracted_id: str,
    *,
    precondition: bool = True,
    behavior: bool = True,
    expected_result: bool = True,
) -> ScenarioPairJudgment:
    return ScenarioPairJudgment(
        expert_scenario_id=expert_id,
        extracted_scenario_id=extracted_id,
        precondition_matches=precondition,
        behavior_matches=behavior,
        expected_result_matches=expected_result,
    )


def test_dbms_scenarios_extracts_three_scenario_parts_from_document():
    scenarios = GeneratedDBMSScenarios(scenarios=[_scenario("dbms_1")])
    with patch(
        "app.dbms_scenarios.ollama.chat",
        return_value=_ollama_response(scenarios.model_dump_json()),
    ) as chat:
        response = client.post(
            "/dbms/scenarios",
            json={
                "requirement_document": (
                    "# Account lookup\n"
                    "Given an account row, selecting by its primary key "
                    "returns that row."
                )
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["scenarios"][0]["precondition"] == (
        "The database contains a committed account row."
    )
    assert result["scenarios"][0]["behavior_under_test"] == (
        "Select the account by its primary key."
    )
    assert result["scenarios"][0]["expected_result"] == (
        "The query returns the matching account row."
    )
    assert "Markdown" in chat.call_args.kwargs["messages"][1]["content"]


@pytest.mark.parametrize(
    "false_field",
    [
        "precondition_matches",
        "behavior_matches",
        "expected_result_matches",
    ],
)
def test_coverage_requires_all_three_parts_to_match(false_field: str):
    judgment_values = {
        "precondition_matches": True,
        "behavior_matches": True,
        "expected_result_matches": True,
    }
    judgment_values[false_field] = False
    judgments = ScenarioPairJudgments(
        judgments=[
            ScenarioPairJudgment(
                expert_scenario_id="expert_1",
                extracted_scenario_id="extracted_1",
                **judgment_values,
            )
        ]
    )
    with patch(
        "app.dbms_scenarios.ollama.chat",
        return_value=_ollama_response(judgments.model_dump_json()),
    ):
        response = client.post(
            "/dbms/coverage",
            json={
                "expert_scenarios": [_scenario("expert_1").model_dump()],
                "extracted_scenarios": [_scenario("extracted_1").model_dump()],
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["coverage_percentage"] == 0
    assert result["target_met"] is False
    assert result["uncovered_expert_scenario_ids"] == ["expert_1"]


def test_coverage_target_is_met_at_ninety_percent():
    expert_scenarios = [_scenario(f"expert_{index}") for index in range(10)]
    extracted_scenarios = [
        _scenario(f"extracted_{index}") for index in range(9)
    ]
    # The judge is called once per expert scenario. Expert i matches
    # extracted i; expert 9 has no equivalent extracted scenario.
    responses = [
        _ollama_response(
            ScenarioPairJudgments(
                judgments=[
                    _judgment(
                        expert.id,
                        extracted.id,
                        precondition=i == j,
                        behavior=i == j,
                        expected_result=i == j,
                    )
                    for j, extracted in enumerate(extracted_scenarios)
                ]
            ).model_dump_json()
        )
        for i, expert in enumerate(expert_scenarios)
    ]
    with patch("app.dbms_scenarios.ollama.chat", side_effect=responses):
        result = evaluate_dbms_scenario_coverage(
            expert_scenarios, extracted_scenarios
        )

    assert result.covered_scenario_count == 9
    assert result.coverage_percentage == 90
    assert result.target_met is True
    assert result.uncovered_expert_scenario_ids == ["expert_9"]


def test_coverage_can_use_an_extracted_scenario_for_each_expert_match():
    responses = [
        _ollama_response(
            ScenarioPairJudgments(
                judgments=[_judgment(expert_id, "extracted_1")]
            ).model_dump_json()
        )
        for expert_id in ("expert_1", "expert_2")
    ]
    with patch("app.dbms_scenarios.ollama.chat", side_effect=responses):
        result = evaluate_dbms_scenario_coverage(
            [_scenario("expert_1"), _scenario("expert_2")],
            [_scenario("extracted_1")],
        )

    assert result.covered_scenario_count == 2
    assert result.coverage_percentage == 100
    assert len(result.matches) == 2


def test_empty_extracted_set_has_zero_coverage_without_calling_model():
    with patch("app.dbms_scenarios.ollama.chat") as chat:
        result = evaluate_dbms_scenario_coverage(
            [_scenario("expert_1")], []
        )

    assert result.coverage_percentage == 0
    assert result.target_met is False
    chat.assert_not_called()


def test_coverage_rejects_an_incomplete_judgment_matrix():
    judgments = ScenarioPairJudgments(
        judgments=[_judgment("expert_1", "extracted_1")]
    )
    with patch(
        "app.dbms_scenarios.ollama.chat",
        return_value=_ollama_response(judgments.model_dump_json()),
    ) as chat:
        with pytest.raises(ValueError, match="judge every"):
            evaluate_dbms_scenario_coverage(
                [_scenario("expert_1")],
                [_scenario("extracted_1"), _scenario("extracted_2")],
            )

    assert chat.call_count == 2  # one bounded retry, then fail loudly


def test_judge_is_limited_to_the_most_similar_candidates():
    expert = _scenario("expert_1")
    expert.behavior_under_test = "Rollback an uncommitted transaction."
    extracted = [_scenario(f"extracted_{i}") for i in range(30)]
    extracted[17].behavior_under_test = "Rollback an uncommitted transaction."

    def fake_chat(**kwargs):
        prompt = kwargs["messages"][1]["content"]
        ids = [f"extracted_{i}" for i in range(30) if f'"extracted_{i}"' in prompt]
        assert len(ids) == 5 and "extracted_17" in ids
        return _ollama_response(
            ScenarioPairJudgments(
                judgments=[_judgment("expert_1", i, precondition=False) for i in ids]
            ).model_dump_json()
        )

    with patch("app.dbms_scenarios.ollama.chat", side_effect=fake_chat):
        result = evaluate_dbms_scenario_coverage(
            [expert], extracted, judge_candidates=5
        )
    assert result.coverage_percentage == 0


def test_long_document_is_extracted_chunk_by_chunk_and_deduplicated():
    from app.dbms_scenarios import identify_dbms_scenarios

    document = "\n\n".join(
        f"## Feature {i}\n" + "Behavior text. " * 120 for i in range(12)
    )
    assert len(document) > 6000
    same = GeneratedDBMSScenarios(scenarios=[_scenario("x")])
    with patch(
        "app.dbms_scenarios.ollama.chat",
        return_value=_ollama_response(same.model_dump_json()),
    ) as chat:
        scenarios = identify_dbms_scenarios(document)

    assert chat.call_count > 1  # more than one model call for a long document
    assert chat.call_args.kwargs["options"]["num_ctx"] == 8192
    assert len(scenarios) == 1 and scenarios[0].id == "dbms_1"  # deduped


def test_truncated_extraction_output_is_split_and_retried():
    from app.dbms_scenarios import identify_dbms_scenarios

    ok = GeneratedDBMSScenarios(scenarios=[_scenario("x")])
    truncated = SimpleNamespace(
        message=SimpleNamespace(content="{"), done_reason="length"
    )
    document = "## A\n" + "Behavior text. " * 100

    def fake_chat(**kwargs):
        del kwargs
        if fake_chat.calls == 0:
            fake_chat.calls += 1
            return truncated
        fake_chat.calls += 1
        return _ollama_response(ok.model_dump_json())

    fake_chat.calls = 0
    with patch(
        "app.dbms_scenarios.ollama.chat",
        side_effect=fake_chat,
    ) as chat:
        scenarios = identify_dbms_scenarios(document)

    assert chat.call_count > 1
    assert len(scenarios) == 1
