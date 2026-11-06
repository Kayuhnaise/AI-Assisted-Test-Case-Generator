
"""Experimental bounded-candidate DBMS scenario coverage evaluator.

Does not replace the production R1 coverage evaluator.
"""

import re

import ollama

from app.generator import MODEL_NAME
from app.models import (
    DBMSCoverageMatch,
    DBMSScenario,
    ScenarioPairJudgments,
)
from app.prompts import (
    DBMS_COVERAGE_SYSTEM_PROMPT,
    build_dbms_coverage_prompt,
)
from app.dbms_scenarios import _coverage_response


DEFAULT_CANDIDATES = 15
MAX_ATTEMPTS = 2


def _tokens(scenario: DBMSScenario) -> set[str]:
    content = " ".join((
        scenario.precondition,
        scenario.behavior_under_test,
        scenario.expected_result,
    ))
    return set(re.findall(r"[a-z0-9_]+", content.lower()))


def select_candidates(
    expert: DBMSScenario,
    extracted: list[DBMSScenario],
    limit: int = DEFAULT_CANDIDATES,
) -> list[DBMSScenario]:
    if limit < 1:
        raise ValueError("Candidate limit must be positive")

    if len(extracted) <= limit:
        return list(extracted)

    expert_tokens = _tokens(expert)

    def similarity(candidate: DBMSScenario) -> float:
        candidate_tokens = _tokens(candidate)
        union = expert_tokens | candidate_tokens
        return (
            len(expert_tokens & candidate_tokens) / len(union)
            if union else 0.0
        )

    return sorted(
        extracted,
        key=similarity,
        reverse=True,
    )[:limit]


def _judge_expert(
    expert: DBMSScenario,
    candidates: list[DBMSScenario],
) -> str | None:
    expected_pairs = {
        (expert.id, candidate.id)
        for candidate in candidates
    }

    for attempt in range(MAX_ATTEMPTS):
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": DBMS_COVERAGE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_dbms_coverage_prompt(
                        [expert], candidates
                    ),
                },
            ],
            format=ScenarioPairJudgments.model_json_schema(),
            options={"temperature": 0},
        )

        try:
            judgments = ScenarioPairJudgments.model_validate_json(
                response.message.content
            ).judgments

            actual_pairs = [
                (item.expert_scenario_id, item.extracted_scenario_id)
                for item in judgments
            ]

            if (
                len(actual_pairs) != len(set(actual_pairs))
                or set(actual_pairs) != expected_pairs
            ):
                raise ValueError("Incomplete or duplicate judgments")

        except ValueError:
            if attempt + 1 == MAX_ATTEMPTS:
                raise
            continue

        by_id = {
            judgment.extracted_scenario_id: judgment
            for judgment in judgments
        }

        for candidate in candidates:
            judgment = by_id[candidate.id]

            if (
                judgment.precondition_matches
                and judgment.behavior_matches
                and judgment.expected_result_matches
            ):
                return candidate.id

        return None

    return None


def evaluate_coverage_experimental(
    expert_scenarios: list[DBMSScenario],
    extracted_scenarios: list[DBMSScenario],
    candidate_limit: int = DEFAULT_CANDIDATES,
):
    if not expert_scenarios:
        raise ValueError("At least one expert scenario is required")

    if candidate_limit < 1:
        raise ValueError("Candidate limit must be positive")

    for name, scenarios in (
        ("Expert", expert_scenarios),
        ("Extracted", extracted_scenarios),
    ):
        ids = [scenario.id for scenario in scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{name} scenario IDs must be unique")

    matches = []

    if extracted_scenarios:
        for expert in expert_scenarios:
            candidates = select_candidates(
                expert, extracted_scenarios, candidate_limit
            )
            matched_id = _judge_expert(expert, candidates)

            if matched_id is not None:
                matches.append(
                    DBMSCoverageMatch(
                        expert_scenario_id=expert.id,
                        extracted_scenario_id=matched_id,
                    )
                )

    return _coverage_response(
        expert_scenarios,
        extracted_scenarios,
        matches,
    )


def evaluate_coverage_batched(
    expert_scenarios: list[DBMSScenario],
    extracted_scenarios: list[DBMSScenario],
    batch_size: int = 15,
):
    """Evaluate all scenario pairs using bounded Ollama requests."""
    if not expert_scenarios:
        raise ValueError("At least one expert scenario is required")

    if batch_size < 1:
        raise ValueError("Batch size must be positive")

    for name, scenarios in (
        ("Expert", expert_scenarios),
        ("Extracted", extracted_scenarios),
    ):
        ids = [scenario.id for scenario in scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{name} scenario IDs must be unique")

    matches = []

    for expert in expert_scenarios:
        matched_id = None

        for start in range(0, len(extracted_scenarios), batch_size):
            candidates = extracted_scenarios[start:start + batch_size]
            matched_id = _judge_expert(expert, candidates)

            if matched_id is not None:
                break

        if matched_id is not None:
            matches.append(
                DBMSCoverageMatch(
                    expert_scenario_id=expert.id,
                    extracted_scenario_id=matched_id,
                )
            )

    return _coverage_response(
        expert_scenarios,
        extracted_scenarios,
        matches,
    )
