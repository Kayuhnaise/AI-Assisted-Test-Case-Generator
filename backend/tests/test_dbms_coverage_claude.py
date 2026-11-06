
"""Mocked tests for the experimental Claude coverage evaluator."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.dbms_coverage_claude import evaluate_coverage_claude
from app.models import DBMSScenario


def scenario(scenario_id, behavior="Insert a valid record"):
    return DBMSScenario(
        id=scenario_id,
        category="positive",
        precondition="The database table exists.",
        behavior_under_test=behavior,
        expected_result="The operation succeeds.",
    )


def mock_response(judgments, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(
                type="text",
                text=json.dumps({"judgments": judgments}),
            )
        ],
    )


def judgment(expert_id, extracted_id, matches=True):
    return {
        "expert_scenario_id": expert_id,
        "extracted_scenario_id": extracted_id,
        "precondition_matches": matches,
        "behavior_matches": matches,
        "expected_result_matches": matches,
    }


@patch("app.dbms_coverage_claude.anthropic.Anthropic")
def test_matching_scenarios_are_covered(mock_client):
    mock_client.return_value.messages.create.return_value = (
        mock_response([judgment("EX-1", "GEN-1")])
    )

    result = evaluate_coverage_claude(
        [scenario("EX-1")],
        [scenario("GEN-1")],
    )

    assert result.coverage_percentage == 100.0
    assert result.covered_scenario_count == 1
    assert result.target_met is True


@patch("app.dbms_coverage_claude.anthropic.Anthropic")
def test_nonmatching_scenarios_are_uncovered(mock_client):
    mock_client.return_value.messages.create.return_value = (
        mock_response([judgment("EX-1", "GEN-1", False)])
    )

    result = evaluate_coverage_claude(
        [scenario("EX-1")],
        [scenario("GEN-1", "Delete all records")],
    )

    assert result.coverage_percentage == 0.0
    assert result.uncovered_expert_scenario_ids == ["EX-1"]


@patch("app.dbms_coverage_claude.anthropic.Anthropic")
def test_missing_pair_is_rejected(mock_client):
    mock_client.return_value.messages.create.return_value = (
        mock_response([])
    )

    with pytest.raises(ValueError, match="every"):
        evaluate_coverage_claude(
            [scenario("EX-1")],
            [scenario("GEN-1")],
        )


@patch("app.dbms_coverage_claude.anthropic.Anthropic")
def test_duplicate_pair_is_rejected(mock_client):
    pair = judgment("EX-1", "GEN-1")

    mock_client.return_value.messages.create.return_value = (
        mock_response([pair, pair])
    )

    with pytest.raises(ValueError, match="duplicate"):
        evaluate_coverage_claude(
            [scenario("EX-1")],
            [scenario("GEN-1")],
        )


@patch("app.dbms_coverage_claude.anthropic.Anthropic")
def test_truncated_response_is_rejected(mock_client):
    mock_client.return_value.messages.create.return_value = (
        mock_response([], stop_reason="max_tokens")
    )

    with pytest.raises(ValueError, match="truncated"):
        evaluate_coverage_claude(
            [scenario("EX-1")],
            [scenario("GEN-1")],
        )


@patch("app.dbms_coverage_claude.anthropic.Anthropic")
def test_api_errors_propagate(mock_client):
    mock_client.return_value.messages.create.side_effect = (
        RuntimeError("API unavailable")
    )

    with pytest.raises(RuntimeError, match="API unavailable"):
        evaluate_coverage_claude(
            [scenario("EX-1")],
            [scenario("GEN-1")],
        )


@patch("app.dbms_coverage_claude.anthropic.Anthropic")
def test_empty_extracted_scenarios_skip_api(mock_client):
    result = evaluate_coverage_claude(
        [scenario("EX-1")],
        [],
    )

    assert result.coverage_percentage == 0.0
    mock_client.assert_not_called()
