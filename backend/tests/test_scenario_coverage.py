import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models import (
    Scenario,
    ScenarioPairJudgment,
    ScenarioPairJudgments,
)
from app.scenario_coverage import (
    evaluate_scenario_coverage,
    is_requirement_aligned,
    validate_pair_judgments,
)


REQUIREMENT = (
    "The system shall compute the result of dividing two numbers and "
    "shall reject division by zero."
)


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


def _scenario(**overrides) -> Scenario:
    fields = {
        "id": "neg_1",
        "category": "negative",
        "requirement_clause": "shall reject division by zero",
        "precondition": "denominator is exactly 0",
        "behavior_under_test": "call divide",
        "expected_result": "raises ValueError",
        "expected_outcome_kind": "error",
        "example_inputs": [
            {"name": "numerator", "value": 10},
            {"name": "denominator", "value": 0},
        ],
    }
    fields.update(overrides)
    return Scenario(**fields)


def _judgments(*pairs: tuple[str, str, bool]) -> SimpleNamespace:
    return _response(
        ScenarioPairJudgments(
            judgments=[
                ScenarioPairJudgment(
                    expert_scenario_id=reference_id,
                    extracted_scenario_id=generated_id,
                    precondition_matches=ok,
                    behavior_matches=ok,
                    expected_result_matches=ok,
                )
                for reference_id, generated_id, ok in pairs
            ]
        ).model_dump_json()
    )


def test_exact_example_inputs_match_without_calling_judge():
    reference = _scenario()
    generated = _scenario(
        id="gen_a",
        precondition="zero denominator",
        example_inputs=[
            {"name": "denominator", "value": 0.0},
            {"name": "numerator", "value": 10.0},
        ],
    )

    with patch("app.scenario_coverage.ollama.chat") as chat:
        result = evaluate_scenario_coverage(
            REQUIREMENT, [reference], [generated]
        )

    chat.assert_not_called()
    assert result.coverage_percentage == 100.0
    assert result.matches[0].generated_scenario_id == "gen_a"
    assert result.matches[0].matched_by == "example_inputs"


def test_gate_excludes_pairs_with_different_category_or_outcome_kind():
    reference = _scenario()
    wrong_category = _scenario(id="gen_a", category="boundary")
    wrong_kind = _scenario(id="gen_b", expected_outcome_kind="success")

    with patch("app.scenario_coverage.ollama.chat") as chat:
        result = evaluate_scenario_coverage(
            REQUIREMENT, [reference], [wrong_category, wrong_kind]
        )

    chat.assert_not_called()
    assert result.covered_scenario_count == 0
    assert result.uncovered_reference_scenario_ids == ["neg_1"]


def test_judge_decides_candidates_with_different_inputs():
    reference = _scenario(
        id="pos_1",
        category="positive",
        requirement_clause="compute the result of dividing two numbers",
        expected_outcome_kind="success",
        expected_result="returns the quotient",
        example_inputs=[
            {"name": "numerator", "value": 10},
            {"name": "denominator", "value": 2},
        ],
    )
    matching = reference.model_copy(update={
        "id": "gen_a",
        "example_inputs": [],
    })
    other = reference.model_copy(update={"id": "gen_b"})
    other = other.model_copy(update={
        "example_inputs": other.example_inputs[:1],
    })

    with patch(
        "app.scenario_coverage.ollama.chat",
        return_value=_judgments(
            ("pos_1", "gen_a", True),
            ("pos_1", "gen_b", False),
        ),
    ) as chat:
        result = evaluate_scenario_coverage(
            REQUIREMENT, [reference], [matching, other]
        )

    assert chat.call_count == 1
    prompt = chat.call_args.kwargs["messages"][1]["content"]
    payload = json.loads(prompt.split("to judge:\n", 1)[1].rsplit("\n\nReturn", 1)[0])
    assert len(payload) == 2
    assert "requirement_clause" not in payload[0]["reference"]
    assert result.matches[0].generated_scenario_id == "gen_a"
    assert result.matches[0].matched_by == "judge"


def test_judge_must_return_every_pair():
    with pytest.raises(ValueError, match="every expert/extracted"):
        validate_pair_judgments([], {("a", "b")})


def test_requirement_alignment_is_scored_deterministically():
    aligned = _scenario(id="gen_a", requirement_clause='"Shall  reject DIVISION by zero."')
    misquoted = _scenario(id="gen_b", requirement_clause="shall refuse division by zero")

    assert is_requirement_aligned(REQUIREMENT, aligned)
    assert not is_requirement_aligned(REQUIREMENT, misquoted)

    with patch("app.scenario_coverage.ollama.chat") as chat:
        result = evaluate_scenario_coverage(
            REQUIREMENT, [_scenario()], [aligned, misquoted]
        )

    chat.assert_not_called()
    assert result.aligned_scenario_count == 1
    assert result.alignment_percentage == 50.0
    assert result.misaligned_scenario_ids == ["gen_b"]
