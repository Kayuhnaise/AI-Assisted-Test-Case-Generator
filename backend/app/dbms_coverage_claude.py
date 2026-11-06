
"""Experimental Claude-based DBMS scenario coverage evaluator."""

import os

import anthropic
from dotenv import load_dotenv

from app.dbms_scenarios import (
    COVERAGE_TARGET_PERCENTAGE,
    _coverage_response,
)
from app.models import (
    DBMSCoverageMatch,
    DBMSCoverageResponse,
    DBMSScenario,
    ScenarioPairJudgments,
)
from app.prompts import (
    DBMS_COVERAGE_SYSTEM_PROMPT,
    build_dbms_coverage_prompt,
)

load_dotenv()

CLAUDE_COVERAGE_MODEL = os.getenv(
    "CLAUDE_COVERAGE_MODEL",
    "claude-sonnet-4-5",
)


def evaluate_coverage_claude(
    expert_scenarios: list[DBMSScenario],
    extracted_scenarios: list[DBMSScenario],
) -> DBMSCoverageResponse:
    """Evaluate strict semantic coverage using Claude."""

    if not expert_scenarios:
        raise ValueError("At least one expert scenario is required")

    expert_ids = [s.id for s in expert_scenarios]
    extracted_ids = [s.id for s in extracted_scenarios]

    if len(set(expert_ids)) != len(expert_ids):
        raise ValueError("Expert scenario IDs must be unique")

    if len(set(extracted_ids)) != len(extracted_ids):
        raise ValueError("Extracted scenario IDs must be unique")

    if not extracted_scenarios:
        return _coverage_response(
            expert_scenarios, extracted_scenarios, []
        )

    client = anthropic.Anthropic()

    response = client.messages.create(
        model=CLAUDE_COVERAGE_MODEL,
        max_tokens=4096,
        system=DBMS_COVERAGE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    build_dbms_coverage_prompt(
                        expert_scenarios,
                        extracted_scenarios,
                    )
                    + "\n\nReturn only valid JSON matching this schema:\n"
                    + str(ScenarioPairJudgments.model_json_schema())
                ),
            }
        ],
    )

    if response.stop_reason == "max_tokens":
        raise ValueError("Claude coverage response was truncated")

    content = "".join(
        block.text
        for block in response.content
        if block.type == "text"
    )

    judgments = ScenarioPairJudgments.model_validate_json(
        content
    ).judgments

    expected_pairs = {
        (expert_id, extracted_id)
        for expert_id in expert_ids
        for extracted_id in extracted_ids
    }

    judged_pairs = [
        (j.expert_scenario_id, j.extracted_scenario_id)
        for j in judgments
    ]

    if len(set(judged_pairs)) != len(judged_pairs):
        raise ValueError("Claude returned duplicate scenario pairs")

    if set(judged_pairs) != expected_pairs:
        raise ValueError(
            "Claude must judge every expert/extracted scenario pair"
        )

    match_for_expert = {}

    for judgment in judgments:
        if (
            judgment.precondition_matches
            and judgment.behavior_matches
            and judgment.expected_result_matches
            and judgment.expert_scenario_id not in match_for_expert
        ):
            match_for_expert[judgment.expert_scenario_id] = (
                judgment.extracted_scenario_id
            )

    matches = [
        DBMSCoverageMatch(
            expert_scenario_id=expert_id,
            extracted_scenario_id=match_for_expert[expert_id],
        )
        for expert_id in expert_ids
        if expert_id in match_for_expert
    ]

    return _coverage_response(
        expert_scenarios,
        extracted_scenarios,
        matches,
    )
