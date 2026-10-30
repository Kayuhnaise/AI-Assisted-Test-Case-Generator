import ollama

from app.generator import MODEL_NAME
from app.models import (
    DBMSCoverageMatch,
    DBMSCoverageResponse,
    DBMSScenario,
    GeneratedDBMSScenarios,
    ScenarioPairJudgments,
)
from app.prompts import (
    DBMS_COVERAGE_SYSTEM_PROMPT,
    DBMS_SCENARIO_SYSTEM_PROMPT,
    build_dbms_coverage_prompt,
    build_dbms_scenario_prompt,
)


COVERAGE_TARGET_PERCENTAGE = 90.0


def identify_dbms_scenarios(requirement_document: str) -> list[DBMSScenario]:
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": DBMS_SCENARIO_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": build_dbms_scenario_prompt(requirement_document),
            },
        ],
        format=GeneratedDBMSScenarios.model_json_schema(),
        options={"temperature": 0.2},
    )
    generated = GeneratedDBMSScenarios.model_validate_json(
        response.message.content
    )
    scenario_ids = [scenario.id for scenario in generated.scenarios]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("Identified DBMS scenario IDs must be unique")
    return generated.scenarios


def evaluate_dbms_scenario_coverage(
    expert_scenarios: list[DBMSScenario],
    extracted_scenarios: list[DBMSScenario],
) -> DBMSCoverageResponse:
    if not expert_scenarios:
        raise ValueError("At least one expert scenario is required")

    expert_ids = [scenario.id for scenario in expert_scenarios]
    extracted_ids = [scenario.id for scenario in extracted_scenarios]
    if len(set(expert_ids)) != len(expert_ids):
        raise ValueError("Expert scenario IDs must be unique")
    if len(set(extracted_ids)) != len(extracted_ids):
        raise ValueError("Extracted scenario IDs must be unique")

    if not extracted_scenarios:
        return _coverage_response(expert_scenarios, extracted_scenarios, [])

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
                    expert_scenarios, extracted_scenarios
                ),
            },
        ],
        format=ScenarioPairJudgments.model_json_schema(),
        options={"temperature": 0},
    )
    judgments = ScenarioPairJudgments.model_validate_json(
        response.message.content
    ).judgments
    expected_pairs = {
        (expert_id, extracted_id)
        for expert_id in expert_ids
        for extracted_id in extracted_ids
    }
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

    match_for_expert: dict[str, str] = {}
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
    return _coverage_response(expert_scenarios, extracted_scenarios, matches)


def _coverage_response(
    expert_scenarios: list[DBMSScenario],
    extracted_scenarios: list[DBMSScenario],
    matches: list[DBMSCoverageMatch],
) -> DBMSCoverageResponse:
    expert_ids = [scenario.id for scenario in expert_scenarios]
    covered_ids = {match.expert_scenario_id for match in matches}
    covered_count = len(matches)
    coverage_percentage = 100 * covered_count / len(expert_scenarios)
    return DBMSCoverageResponse(
        expert_scenario_count=len(expert_scenarios),
        extracted_scenario_count=len(extracted_scenarios),
        covered_scenario_count=covered_count,
        coverage_percentage=coverage_percentage,
        target_percentage=COVERAGE_TARGET_PERCENTAGE,
        target_met=coverage_percentage >= COVERAGE_TARGET_PERCENTAGE,
        matches=matches,
        uncovered_expert_scenario_ids=[
            expert_id for expert_id in expert_ids if expert_id not in covered_ids
        ],
    )
