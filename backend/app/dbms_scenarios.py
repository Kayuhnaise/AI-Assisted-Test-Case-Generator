import re

import ollama
from pydantic import ValidationError

from app.dbms_chunking import Chunk, chunk_document, split_text
from app.generator import MODEL_NAME
from app.models import (
    DBMSCoverageMatch,
    DBMSCoverageResponse,
    DBMSScenario,
    GeneratedDBMSScenarios,
    ScenarioPairJudgments,
)
from app.prompts import (
    DBMS_CHUNK_SYSTEM_PROMPT,
    DBMS_COVERAGE_SYSTEM_PROMPT,
    build_dbms_chunk_prompt,
    build_dbms_coverage_prompt,
)


COVERAGE_TARGET_PERCENTAGE = 90.0

# Set the context window explicitly instead of relying on Ollama's default,
# and size chunks so that excerpt + shared context + prompt + output fit.
NUM_CTX = 8192
NUM_PREDICT = 3000
MAX_CHUNK_CHARS = 6000
MAX_CONTEXT_CHARS = 2000
MAX_SPLIT_DEPTH = 3

# Judge at most this many extracted scenarios per expert scenario.
JUDGE_CANDIDATES = 15
JUDGE_ATTEMPTS = 2


# ---------------------------------------------------------------- extraction

def identify_dbms_scenarios(requirement_document: str) -> list[DBMSScenario]:
    """Extract scenarios from a DBMS requirement document of any length.

    The document is split along headings into chunks that fit the context
    window; each chunk is extracted with a shared-context block, and the
    results are merged, de-duplicated and renumbered.
    """
    chunks = chunk_document(
        requirement_document,
        max_chars=MAX_CHUNK_CHARS,
        max_context_chars=MAX_CONTEXT_CHARS,
    )
    collected: list[DBMSScenario] = []
    seen: set[tuple[str, str, str]] = set()
    for chunk in chunks:
        for scenario in _extract_chunk(chunk, depth=0):
            key = _dedupe_key(scenario)
            if key in seen:
                continue
            seen.add(key)
            collected.append(scenario)
    return [
        scenario.model_copy(update={"id": f"dbms_{number}"})
        for number, scenario in enumerate(collected, 1)
    ]


def _extract_chunk(chunk: Chunk, depth: int) -> list[DBMSScenario]:
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": DBMS_CHUNK_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_dbms_chunk_prompt(
                    chunk.section_path, chunk.text, chunk.context
                ),
            },
        ],
        format=GeneratedDBMSScenarios.model_json_schema(),
        options={
            "temperature": 0.2,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
        },
    )

    # Output cut off at the token limit: split the chunk and retry rather
    # than silently losing scenarios.
    if getattr(response, "done_reason", None) == "length":
        if depth >= MAX_SPLIT_DEPTH or len(chunk.text) < 400:
            raise ValueError(
                f"Extraction output was truncated for section "
                f"'{chunk.section_path}' and cannot be split further"
            )
        scenarios: list[DBMSScenario] = []
        for part in split_text(chunk.text, max(len(chunk.text) // 2, 200)):
            scenarios.extend(
                _extract_chunk(
                    Chunk(
                        chunk.section_path,
                        part,
                        chunk.context,
                        chunk.section_indexes,
                    ),
                    depth + 1,
                )
            )
        return scenarios

    return GeneratedDBMSScenarios.model_validate_json(
        response.message.content
    ).scenarios


def _normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def _dedupe_key(scenario: DBMSScenario) -> tuple[str, str, str]:
    return (
        _normalize(scenario.precondition),
        _normalize(scenario.behavior_under_test),
        _normalize(scenario.expected_result),
    )


# ------------------------------------------------------------------ coverage

def evaluate_dbms_scenario_coverage(
    expert_scenarios: list[DBMSScenario],
    extracted_scenarios: list[DBMSScenario],
    judge_candidates: int = JUDGE_CANDIDATES,
) -> DBMSCoverageResponse:
    """Coverage per the spec: an expert scenario is covered only if one
    extracted scenario matches precondition, behavior and expected result.

    The judge is called once per expert scenario over a bounded candidate
    set, so no single call has to return hundreds of pair judgments.
    """
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

    matches: list[DBMSCoverageMatch] = []
    for expert in expert_scenarios:
        candidates = _select_candidates(
            expert, extracted_scenarios, judge_candidates
        )
        matched_id = _judge_expert(expert, candidates)
        if matched_id is not None:
            matches.append(
                DBMSCoverageMatch(
                    expert_scenario_id=expert.id,
                    extracted_scenario_id=matched_id,
                )
            )
    return _coverage_response(expert_scenarios, extracted_scenarios, matches)


def _tokens(scenario: DBMSScenario) -> set[str]:
    text = " ".join(
        (
            scenario.precondition,
            scenario.behavior_under_test,
            scenario.expected_result,
        )
    )
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _select_candidates(
    expert: DBMSScenario,
    extracted: list[DBMSScenario],
    limit: int,
) -> list[DBMSScenario]:
    """Return all extracted scenarios when few; otherwise the `limit` most
    lexically similar. Pre-filtering can only lower coverage (a missed
    candidate is never counted as a match), so it is conservative."""
    if len(extracted) <= limit:
        return list(extracted)
    expert_tokens = _tokens(expert)

    def similarity(candidate: DBMSScenario) -> float:
        tokens = _tokens(candidate)
        union = expert_tokens | tokens
        return len(expert_tokens & tokens) / len(union) if union else 0.0

    return sorted(extracted, key=similarity, reverse=True)[:limit]


def _judge_expert(
    expert: DBMSScenario, candidates: list[DBMSScenario]
) -> str | None:
    expected_pairs = {(expert.id, candidate.id) for candidate in candidates}
    last_error: Exception | None = None
    for _ in range(JUDGE_ATTEMPTS):
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": DBMS_COVERAGE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_dbms_coverage_prompt(
                        [expert], candidates
                    ),
                },
            ],
            format=ScenarioPairJudgments.model_json_schema(),
            options={"temperature": 0, "num_ctx": NUM_CTX},
        )
        try:
            judgments = ScenarioPairJudgments.model_validate_json(
                response.message.content
            ).judgments
            judged = [
                (item.expert_scenario_id, item.extracted_scenario_id)
                for item in judgments
            ]
            if len(set(judged)) != len(judged):
                raise ValueError(
                    "Coverage evaluator returned duplicate scenario pairs"
                )
            if set(judged) != expected_pairs:
                raise ValueError(
                    "Coverage evaluator must judge every "
                    "expert/extracted scenario pair"
                )
        except (ValueError, ValidationError) as exc:
            last_error = exc
            continue

        by_extracted = {j.extracted_scenario_id: j for j in judgments}
        for candidate in candidates:  # deterministic: first full match wins
            j = by_extracted[candidate.id]
            if (
                j.precondition_matches
                and j.behavior_matches
                and j.expected_result_matches
            ):
                return candidate.id
        return None

    raise ValueError(str(last_error))


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
