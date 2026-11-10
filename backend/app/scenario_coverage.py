"""
Automated scoring of Python-pipeline scenarios against reference scenarios.

Scenario-Type Coverage uses a hybrid method:
1. Deterministic gate: a reference/generated pair is a candidate only when
   category and expected_outcome_kind are identical.
2. Deterministic input match: a candidate whose example_inputs exactly
   equal the reference's covers it without any LLM call.
3. LLM judge: remaining candidates are judged only on their free-text
   fields (input condition and expected result).

Requirement Alignment is fully deterministic: a scenario is aligned when its
requirement_clause appears verbatim (ignoring case and whitespace) in the
requirement.
"""

from collections.abc import Iterable

import ollama

from app.generator import MODEL_NAME
from app.models import (
    Scenario,
    ScenarioCoverageMatch,
    ScenarioCoverageResponse,
    ScenarioPairJudgment,
    ScenarioPairJudgments,
)
from app.prompts import (
    SCENARIO_COVERAGE_SYSTEM_PROMPT,
    build_scenario_coverage_prompt,
)


def validate_pair_judgments(
    judgments: list[ScenarioPairJudgment],
    expected_pairs: set[tuple[str, str]],
) -> None:
    """Ensure a judge returned exactly one judgment per requested pair."""
    judged_pairs = [
        (item.expert_scenario_id, item.extracted_scenario_id)
        for item in judgments
    ]
    if len(set(judged_pairs)) != len(judged_pairs):
        raise ValueError("Coverage evaluator returned duplicate scenario pairs")
    if set(judged_pairs) != expected_pairs:
        raise ValueError(
            "Coverage evaluator must judge every expert/extracted scenario pair"
        )


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _normalize_clause(clause: str) -> str:
    return _normalize(clause).strip(" \"'“”‘’").rstrip(".").strip()


def is_requirement_aligned(requirement: str, scenario: Scenario) -> bool:
    clause = _normalize_clause(scenario.requirement_clause)
    return bool(clause) and clause in _normalize(requirement)


def _inputs_key(scenario: Scenario) -> dict[str, object] | None:
    if not scenario.example_inputs:
        return None
    return {
        argument.name: argument.value
        for argument in scenario.example_inputs
    }


def _inputs_equal(reference: Scenario, generated: Scenario) -> bool:
    reference_inputs = _inputs_key(reference)
    generated_inputs = _inputs_key(generated)
    if reference_inputs is None or generated_inputs is None:
        return False
    if reference_inputs.keys() != generated_inputs.keys():
        return False
    for name, value in reference_inputs.items():
        other = generated_inputs[name]
        # Treat 10 and 10.0 as equal, but never True and 1.
        if isinstance(value, bool) or isinstance(other, bool):
            if value is not other:
                return False
        elif value != other:
            return False
    return True


def _judge_pairs(
    requirement: str,
    pairs: list[tuple[Scenario, Scenario]],
) -> set[tuple[str, str]]:
    """Return the (reference_id, generated_id) pairs the judge accepts."""
    if not pairs:
        return set()

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SCENARIO_COVERAGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_scenario_coverage_prompt(requirement, pairs),
            },
        ],
        format=ScenarioPairJudgments.model_json_schema(),
        options={"temperature": 0},
    )
    judgments = ScenarioPairJudgments.model_validate_json(
        response.message.content
    ).judgments
    validate_pair_judgments(
        judgments,
        {(reference.id, generated.id) for reference, generated in pairs},
    )
    return {
        (judgment.expert_scenario_id, judgment.extracted_scenario_id)
        for judgment in judgments
        if judgment.precondition_matches
        and judgment.behavior_matches
        and judgment.expected_result_matches
    }


def _require_unique_ids(scenarios: Iterable[Scenario], label: str) -> list[str]:
    ids = [scenario.id for scenario in scenarios]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{label} scenario IDs must be unique")
    return ids


def evaluate_scenario_coverage(
    requirement: str,
    reference_scenarios: list[Scenario],
    generated_scenarios: list[Scenario],
) -> ScenarioCoverageResponse:
    if not reference_scenarios:
        raise ValueError("At least one reference scenario is required")

    reference_ids = _require_unique_ids(reference_scenarios, "Reference")
    _require_unique_ids(generated_scenarios, "Generated")

    match_for_reference: dict[str, ScenarioCoverageMatch] = {}
    judge_pairs: list[tuple[Scenario, Scenario]] = []

    for reference in reference_scenarios:
        candidates = [
            generated for generated in generated_scenarios
            if generated.category == reference.category
            and generated.expected_outcome_kind
            == reference.expected_outcome_kind
        ]
        exact = next(
            (
                generated for generated in candidates
                if _inputs_equal(reference, generated)
            ),
            None,
        )
        if exact is not None:
            match_for_reference[reference.id] = ScenarioCoverageMatch(
                reference_scenario_id=reference.id,
                generated_scenario_id=exact.id,
                matched_by="example_inputs",
            )
        else:
            judge_pairs.extend(
                (reference, generated) for generated in candidates
            )

    accepted = _judge_pairs(requirement, judge_pairs)
    for reference, generated in judge_pairs:
        if (
            reference.id not in match_for_reference
            and (reference.id, generated.id) in accepted
        ):
            match_for_reference[reference.id] = ScenarioCoverageMatch(
                reference_scenario_id=reference.id,
                generated_scenario_id=generated.id,
                matched_by="judge",
            )

    matches = [
        match_for_reference[reference_id]
        for reference_id in reference_ids
        if reference_id in match_for_reference
    ]
    misaligned = [
        scenario.id for scenario in generated_scenarios
        if not is_requirement_aligned(requirement, scenario)
    ]
    aligned_count = len(generated_scenarios) - len(misaligned)

    return ScenarioCoverageResponse(
        reference_scenario_count=len(reference_scenarios),
        generated_scenario_count=len(generated_scenarios),
        covered_scenario_count=len(matches),
        coverage_percentage=100 * len(matches) / len(reference_scenarios),
        matches=matches,
        uncovered_reference_scenario_ids=[
            reference_id for reference_id in reference_ids
            if reference_id not in match_for_reference
        ],
        aligned_scenario_count=aligned_count,
        alignment_percentage=(
            100 * aligned_count / len(generated_scenarios)
            if generated_scenarios else 0.0
        ),
        misaligned_scenario_ids=misaligned,
    )
