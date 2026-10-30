
import ollama

from app.generator import MODEL_NAME
from app.models import (
    DBMSScenario,
    DBMSSQLTestCase,
    GeneratedDBMSSQLTests,
)
from app.prompts import (
    DBMS_SQL_GENERATION_SYSTEM_PROMPT,
    build_dbms_sql_generation_prompt,
)


def generate_dbms_sql_tests(
    requirement_document: str,
    scenarios: list[DBMSScenario],
) -> list[DBMSSQLTestCase]:
    """
    Generate scenario-traceable SQL test cases
    from structured DBMS scenarios.
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

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": DBMS_SQL_GENERATION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": build_dbms_sql_generation_prompt(
                    requirement_document,
                    scenarios,
                ),
            },
        ],
        format=GeneratedDBMSSQLTests.model_json_schema(),
        options={"temperature": 0.2},
    )

    generated = GeneratedDBMSSQLTests.model_validate_json(
        response.message.content
    )

    test_cases = generated.test_cases

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
        
        
        # Require a specific expected SQLite error.
        if (
            case.expected_outcome.outcome_type == "error"
            and not case.expected_outcome.expected_error
        ):
            raise ValueError(
                f"SQL test {case.id} is missing "
                "the expected SQL error"
            )

        # Reject legacy verification queries that
        # cannot establish expected database state.
        if case.verification_sql:
            raise ValueError(
                f"SQL test {case.id} uses verification_sql "
                "without expected results"
            )

        # Require database-state assertions for
        # mutation and expected-error scenarios.
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


    return test_cases
