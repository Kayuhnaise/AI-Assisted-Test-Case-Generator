import ollama
from pydantic import BaseModel, Field
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

from app.dbms_chunking import (
    chunk_by_requirement,
    chunk_document,
    split_text,
)

COVERAGE_TARGET_PERCENTAGE = 90.0

MAX_CHUNK_CHARS = 6000
MAX_CONTEXT_CHARS = 2000
MAX_SPLIT_DEPTH = 3
MIN_SPLIT_CHARS = 200


class DBMSChunkResponse(BaseModel):
    scenarios: list[DBMSScenario] = Field(default_factory=list)



def _extract_dbms_chunk(
    text: str,
    context: str = "",
    depth: int = 0,
) -> list[DBMSScenario]:
    """Extract scenarios, splitting and retrying truncated responses."""
    document = text

    if context:
        document = (
            "Shared document context:\n"
            f"{context}\n\n"
            "Requirements to analyze:\n"
            f"{text}"
        )

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": DBMS_SCENARIO_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": build_dbms_scenario_prompt(document),
            },
        ],
        format=DBMSChunkResponse.model_json_schema(),
        options={"temperature": 0.2},
    )

    if getattr(response, "done_reason", None) == "length":
        if depth >= MAX_SPLIT_DEPTH or len(text) < 400:
            raise ValueError(
                "DBMS scenario extraction remained truncated "
                "after splitting and retrying"
            )

        smaller_chunks = split_text(
            text,
            max(len(text) // 2, MIN_SPLIT_CHARS),
        )

        # Avoid retrying the same unsplittable input.
        if (
            len(smaller_chunks) < 2
            or any(part == text for part in smaller_chunks)
        ):
            raise ValueError(
                "DBMS scenario extraction cannot be split further"
            )

        scenarios = []

        for part in smaller_chunks:
            scenarios.extend(
                _extract_dbms_chunk(
                    text=part,
                    context=context,
                    depth=depth + 1,
                )
            )

        return scenarios

    result = DBMSChunkResponse.model_validate_json(
        response.message.content
    )
    return result.scenarios


def identify_dbms_scenarios(
    requirement_document: str,
) -> list[DBMSScenario]:
    chunks = chunk_by_requirement(
        requirement_document,
        max_chars=MAX_CHUNK_CHARS,
        max_context_chars=MAX_CONTEXT_CHARS,
    )

    if not chunks:
        raise ValueError("Requirement document cannot be empty")

    # Preserve the existing behavior for short documents.
    if len(chunks) == 1 and not chunks[0].context:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": DBMS_SCENARIO_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_dbms_scenario_prompt(
                        requirement_document
                    ),
                },
            ],
            format=GeneratedDBMSScenarios.model_json_schema(),
            options={"temperature": 0.2},
        )

        if getattr(response, "done_reason", None) == "length":
            recovered = _extract_dbms_chunk(
                text=requirement_document,
            )

            if not recovered:
                raise ValueError(
                    "No DBMS test scenarios were identified"
                )

            recovered_ids = [scenario.id for scenario in recovered]

            if len(set(recovered_ids)) != len(recovered_ids):
                recovered = [
                    scenario.model_copy(update={"id": f"dbms_{i}"})
                    for i, scenario in enumerate(recovered, start=1)
                ]

            return recovered

        generated = GeneratedDBMSScenarios.model_validate_json(
            response.message.content
        )

        scenario_ids = [
            scenario.id for scenario in generated.scenarios
        ]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError(
                "Identified DBMS scenario IDs must be unique"
            )

        return generated.scenarios

    # Extract scenarios independently from longer documents.
    collected = []

    for chunk in chunks:
        scenarios = _extract_dbms_chunk(
            text=chunk.text,
            context=chunk.context,
        )
        collected.extend(scenarios)

    # Deduplicate scenarios across overlapping document chunks.
    unique = {}

    for scenario in collected:
        key = (
            " ".join(scenario.precondition.lower().split()),
            " ".join(scenario.behavior_under_test.lower().split()),
            " ".join(scenario.expected_result.lower().split()),
        )
        unique.setdefault(key, scenario)

    if not unique:
        raise ValueError(
            "No DBMS test scenarios were identified"
        )

    # Assign unique IDs after combining chunk results.
    return [
        scenario.model_copy(update={"id": f"dbms_{index}"})
        for index, scenario in enumerate(unique.values(), start=1)
    ]

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
