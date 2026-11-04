
import os
import json

import anthropic

from pydantic import ValidationError

from app.models import (
    DBMSScenario,
    DBMSSQLTestCase,
    GeneratedDBMSSQLTests,
)
from app.prompts import (
    DBMS_SQL_GENERATION_SYSTEM_PROMPT,
    build_dbms_sql_generation_prompt,
)


MAX_GENERATION_ATTEMPTS = 3
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-fable-5-1")


def _validate_generated_tests(
    test_cases: list[DBMSSQLTestCase],
    scenario_by_id: dict[str, DBMSScenario],
) -> None:
    """Validate generated SQL test structure and traceability."""

    test_ids = [case.id for case in test_cases]
    scenario_ids = [case.scenario_id for case in test_cases]

    if len(set(test_ids)) != len(test_ids):
        raise ValueError(
            "Generated SQL test IDs must be unique"
        )

    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError(
            "Each scenario must have exactly one SQL test"
        )

    if set(scenario_ids) != set(scenario_by_id):
        raise ValueError(
            "Generated SQL tests must cover every scenario"
        )

    for case in test_cases:
        source_scenario = scenario_by_id[case.scenario_id]

        if case.category != source_scenario.category:
            raise ValueError(
                f"Category mismatch for {case.scenario_id}"
            )

        if case.sql_dialect != "sqlite":
            raise ValueError(
                f"Unsupported SQL dialect: {case.sql_dialect}"
            )

        if (
            case.expected_outcome.outcome_type == "error"
            and not case.expected_outcome.expected_error
        ):
            raise ValueError(
                f"SQL test {case.id} is missing "
                "the expected SQL error"
            )

        if case.verification_sql:
            raise ValueError(
                f"SQL test {case.id} uses verification_sql "
                "without expected results"
            )

        sql_operation = case.test_sql.lstrip().upper()

        requires_state_verification = (
            case.expected_outcome.outcome_type
            in ("error", "database_state")
            or sql_operation.startswith(
                ("INSERT", "UPDATE", "DELETE", "REPLACE")
            )
        )

        if (
            requires_state_verification
            and not case.verification_assertions
        ):
            raise ValueError(
                f"SQL test {case.id} requires "
                "verification_assertions"
            )

        if (
            sql_operation.startswith(
                ("INSERT", "UPDATE", "DELETE", "REPLACE")
            )
            and case.expected_outcome.outcome_type == "scalar"
        ):
            raise ValueError(
                f"SQL test {case.id} uses scalar outcome "
                "for a state-changing operation"
            )


def generate_dbms_sql_tests(
    requirement_document: str,
    scenarios: list[DBMSScenario],
) -> list[DBMSSQLTestCase]:
    """
    Generate scenario-traceable SQL tests, retrying
    invalid model output up to two additional times.
    """

    if not scenarios:
        raise ValueError(
            "At least one DBMS scenario is required"
        )

    scenario_by_id = {
        scenario.id: scenario
        for scenario in scenarios
    }

    if len(scenario_by_id) != len(scenarios):
        raise ValueError(
            "DBMS scenario IDs must be unique"
        )

    messages = [
        {
            "role": "user",
            "content": build_dbms_sql_generation_prompt(
                requirement_document,
                scenarios,
            ) + "\n\nReturn only JSON matching this schema:\n"
            + json.dumps(GeneratedDBMSSQLTests.model_json_schema()),
        },
    ]

    client = anthropic.Anthropic()
    last_error = None

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            system=DBMS_SQL_GENERATION_SYSTEM_PROMPT,
            messages=messages,
        )

        content = "".join(
            block.text for block in response.content
            if block.type == "text"
        ).strip()

        if response.stop_reason == "max_tokens":
            raise ValueError("Claude response was truncated; increase max_tokens")

        try:
            generated = GeneratedDBMSSQLTests.model_validate_json(
                content
            )

            test_cases = generated.test_cases

            _validate_generated_tests(
                test_cases,
                scenario_by_id,
            )

            return test_cases

        except (ValidationError, ValueError) as exc:
            last_error = exc

            if attempt == MAX_GENERATION_ATTEMPTS - 1:
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                }
            )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous SQL test generation "
                        "response failed validation.\n\n"
                        f"Validation error:\n{exc}\n\n"
                        "Correct the response while preserving "
                        "the original requirements, scenario IDs, "
                        "categories, and intended database behavior. "
                        "Return the complete corrected JSON object "
                        "with exactly one test case per scenario. "
                        "Use verification_assertions with correctly "
                        "typed expected results, and keep "
                        "verification_sql empty."
                    ),
                }
            )

    raise ValueError(
        "SQL test generation failed after "
        f"{MAX_GENERATION_ATTEMPTS} attempts. "
        f"Last validation error: {last_error}"
    ) from last_error
