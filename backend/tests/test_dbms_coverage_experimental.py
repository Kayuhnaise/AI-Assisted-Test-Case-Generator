
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models import DBMSScenario
from app.dbms_coverage_experimental import (
    evaluate_coverage_batched,
    evaluate_coverage_experimental,
    select_candidates,
)


def scenario(sid, behavior):
    return DBMSScenario(
        id=sid,
        category="positive",
        precondition="A customer table exists",
        behavior_under_test=behavior,
        expected_result="The operation succeeds",
    )


def response_for(expert, candidates, matching_ids=()):
    judgments = [
        {
            "expert_scenario_id": expert.id,
            "extracted_scenario_id": candidate.id,
            "precondition_matches": candidate.id in matching_ids,
            "behavior_matches": candidate.id in matching_ids,
            "expected_result_matches": candidate.id in matching_ids,
        }
        for candidate in candidates
    ]
    return SimpleNamespace(
        message=SimpleNamespace(
            content=json.dumps({"judgments": judgments})
        )
    )


def test_small_candidate_set_is_not_filtered():
    expert = scenario("E1", "Insert a customer")
    extracted = [
        scenario("X1", "Delete a customer"),
        scenario("X2", "Insert a customer"),
    ]

    selected = select_candidates(expert, extracted, limit=5)

    assert [s.id for s in selected] == ["X1", "X2"]


def test_candidate_limit_is_respected():
    expert = scenario("E1", "Insert a customer")
    extracted = [
        scenario(f"X{i}", f"Operation {i}")
        for i in range(30)
    ]

    selected = select_candidates(expert, extracted, limit=15)

    assert len(selected) == 15


def test_experimental_coverage_identifies_match():
    expert = [scenario("E1", "Insert a customer")]
    extracted = [
        scenario("X1", "Delete a customer"),
        scenario("X2", "Insert a customer"),
    ]

    mocked = response_for(expert[0], extracted, {"X2"})

    with patch(
        "app.dbms_coverage_experimental.ollama.chat",
        return_value=mocked,
    ) as chat:
        result = evaluate_coverage_experimental(
            expert, extracted
        )

    assert result.coverage_percentage == 100.0
    assert result.covered_scenario_count == 1
    assert result.matches[0].extracted_scenario_id == "X2"
    assert chat.call_count == 1


def test_experimental_coverage_detects_no_match():
    expert = [scenario("E1", "Insert a customer")]
    extracted = [scenario("X1", "Delete a customer")]

    mocked = response_for(expert[0], extracted)

    with patch(
        "app.dbms_coverage_experimental.ollama.chat",
        return_value=mocked,
    ):
        result = evaluate_coverage_experimental(
            expert, extracted
        )

    assert result.coverage_percentage == 0.0
    assert result.uncovered_expert_scenario_ids == ["E1"]


def test_empty_extracted_scenarios_need_no_model_call():
    expert = [scenario("E1", "Insert a customer")]

    with patch(
        "app.dbms_coverage_experimental.ollama.chat"
    ) as chat:
        result = evaluate_coverage_experimental(expert, [])

    assert result.coverage_percentage == 0.0
    chat.assert_not_called()


def test_duplicate_expert_ids_are_rejected():
    expert = [
        scenario("E1", "Insert a customer"),
        scenario("E1", "Delete a customer"),
    ]

    with pytest.raises(ValueError, match="unique"):
        evaluate_coverage_experimental(expert, [])


def test_invalid_candidate_limit_is_rejected():
    expert = [scenario("E1", "Insert a customer")]

    with pytest.raises(ValueError, match="positive"):
        evaluate_coverage_experimental(expert, [], candidate_limit=0)


def test_semantic_match_can_be_excluded_by_candidate_filter():
    expert = DBMSScenario(
        id="E1",
        category="negative",
        precondition="A row already uses the primary key",
        behavior_under_test="Insert another row with the same primary key",
        expected_result="The database rejects the duplicate",
    )

    equivalent = DBMSScenario(
        id="X_MATCH",
        category="negative",
        precondition="An identifier has already been assigned",
        behavior_under_test="Create a second record using that identifier",
        expected_result="The operation is refused",
    )

    distractors = [
        DBMSScenario(
            id=f"X{i}",
            category="positive",
            precondition="A row already uses the primary key",
            behavior_under_test=f"Inspect primary key metadata for case {i}",
            expected_result="The database returns metadata",
        )
        for i in range(20)
    ]

    extracted = distractors + [equivalent]

    selected = select_candidates(
        expert, extracted, limit=15
    )

    # The semantic match may be excluded because its wording differs.
    assert "X_MATCH" not in [item.id for item in selected]

def test_batched_coverage_finds_match_outside_top_15():
    expert = DBMSScenario(
        id="E1",
        category="negative",
        precondition="A row already uses the primary key",
        behavior_under_test="Insert another row with the same primary key",
        expected_result="The database rejects the duplicate",
    )

    equivalent = DBMSScenario(
        id="X_MATCH",
        category="negative",
        precondition="An identifier has already been assigned",
        behavior_under_test="Create a second record using that identifier",
        expected_result="The operation is refused",
    )

    distractors = [
        DBMSScenario(
            id=f"X{i}",
            category="positive",
            precondition="A row already uses the primary key",
            behavior_under_test=f"Inspect primary key metadata for case {i}",
            expected_result="The database returns metadata",
        )
        for i in range(20)
    ]

    extracted = distractors + [equivalent]

    # Ensure the lexical filter excludes the valid candidate.
    filtered = select_candidates(expert, extracted, limit=15)
    assert "X_MATCH" not in [s.id for s in filtered]

    batches = [
        extracted[i:i + 15]
        for i in range(0, len(extracted), 15)
    ]

    mocked_responses = [
        response_for(expert, batch, {"X_MATCH"})
        for batch in batches
    ]

    with patch(
        "app.dbms_coverage_experimental.ollama.chat",
        side_effect=mocked_responses,
    ) as chat:
        result = evaluate_coverage_batched(
            [expert],
            extracted,
            batch_size=15,
        )

    assert result.coverage_percentage == 100.0
    assert result.matches[0].extracted_scenario_id == "X_MATCH"
    assert chat.call_count == 2


def test_original_and_batched_coverage_agree():
    from app.dbms_scenarios import evaluate_dbms_scenario_coverage

    experts = [
        scenario("E1", "Insert a customer"),
        scenario("E2", "Delete a customer"),
    ]

    extracted = [
        scenario("X1", "Insert a customer"),
        scenario("X2", "Update a customer"),
        scenario("X3", "Delete a customer"),
    ]

    matching_pairs = {
        ("E1", "X1"),
        ("E2", "X3"),
    }

    def mock_judgments(expert_group, extracted_group):
        judgments = [
            {
                "expert_scenario_id": expert.id,
                "extracted_scenario_id": candidate.id,
                "precondition_matches": (expert.id, candidate.id)
                in matching_pairs,
                "behavior_matches": (expert.id, candidate.id)
                in matching_pairs,
                "expected_result_matches": (expert.id, candidate.id)
                in matching_pairs,
            }
            for expert in expert_group
            for candidate in extracted_group
        ]
        return SimpleNamespace(
            message=SimpleNamespace(
                content=json.dumps({"judgments": judgments})
            )
        )

    def fake_chat(**kwargs):
        import re

        prompt = kwargs["messages"][1]["content"]

        expert_ids = re.findall(r'"id": "(E\d+)"', prompt)
        extracted_ids = re.findall(r'"id": "(X\d+)"', prompt)

        selected_experts = [
            item for item in experts if item.id in expert_ids
        ]
        selected_extracted = [
            item for item in extracted if item.id in extracted_ids
        ]

        return mock_judgments(
            selected_experts,
            selected_extracted,
        )

    with patch(
        "app.dbms_scenarios.ollama.chat",
        side_effect=fake_chat,
    ):
        original = evaluate_dbms_scenario_coverage(
            experts, extracted
        )

    with patch(
        "app.dbms_coverage_experimental.ollama.chat",
        side_effect=fake_chat,
    ):
        batched = evaluate_coverage_batched(
            experts, extracted, batch_size=2
        )

    assert original.covered_scenario_count == batched.covered_scenario_count
    assert original.coverage_percentage == batched.coverage_percentage
    assert original.uncovered_expert_scenario_ids == (
        batched.uncovered_expert_scenario_ids
    )
    assert original.matches == batched.matches
