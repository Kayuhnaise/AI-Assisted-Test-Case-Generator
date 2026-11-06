"""Claude-based R1 scenario extraction for DBMS requirements."""

import os

import anthropic
from dotenv import load_dotenv

from app.dbms_chunking import chunk_by_requirement
from app.dbms_scenarios import MAX_CHUNK_CHARS, MAX_CONTEXT_CHARS
from app.models import DBMSScenario, GeneratedDBMSScenarios
from app.prompts import (
    DBMS_SCENARIO_SYSTEM_PROMPT,
    build_dbms_scenario_prompt,
)

load_dotenv()

CLAUDE_R1_MODEL = os.getenv(
    "CLAUDE_R1_MODEL",
    "claude-sonnet-4-5",
)


def identify_dbms_scenarios_claude(
    requirement_document: str,
) -> list[DBMSScenario]:
    """Extract structured DBMS test scenarios using Claude."""

    chunks = chunk_by_requirement(
        requirement_document,
        max_chars=MAX_CHUNK_CHARS,
        max_context_chars=MAX_CONTEXT_CHARS,
    )

    if not chunks:
        raise ValueError("Requirement document cannot be empty")

    client = anthropic.Anthropic()
    collected = []

    for chunk in chunks:
        document = chunk.text

        if chunk.context:
            document = (
                f"Shared document context:\n{chunk.context}\n\n"
                f"Requirements to analyze:\n{chunk.text}"
            )

        response = client.messages.create(
            model=CLAUDE_R1_MODEL,
            max_tokens=8192,
            system=(
                DBMS_SCENARIO_SYSTEM_PROMPT
                + "\n\nOutput a single raw JSON object only. "
                + "Do not use Markdown code fences, XML tags, "
                + "tool calls, or explanatory text. "
                + "The response must begin with { and end with }."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        build_dbms_scenario_prompt(document)
                        + "\n\nReturn only valid JSON matching this schema:\n"
                        + str(GeneratedDBMSScenarios.model_json_schema())
                    ),
                }
            ],
        )

        if response.stop_reason == "max_tokens":
            raise ValueError(
                "Claude R1 response was truncated. "
                "Reduce the chunk size before retrying."
            )

        content = "".join(
            block.text
            for block in response.content
            if block.type == "text"
        )

        content = content.strip()

        if content.startswith("```"):
            lines = content.splitlines()
            if lines[-1].strip() != "```":
                raise ValueError("Incomplete Markdown JSON code block")
            content = "\n".join(lines[1:-1]).strip()

        generated = GeneratedDBMSScenarios.model_validate_json(
            content
        )

        collected.extend(generated.scenarios)

    unique = {}

    for scenario in collected:
        key = (
            " ".join(scenario.precondition.lower().split()),
            " ".join(scenario.behavior_under_test.lower().split()),
            " ".join(scenario.expected_result.lower().split()),
        )
        unique.setdefault(key, scenario)

    if not unique:
        raise ValueError("No DBMS test scenarios were identified")

    return [
        scenario.model_copy(update={"id": f"dbms_{index}"})
        for index, scenario in enumerate(unique.values(), start=1)
    ]
