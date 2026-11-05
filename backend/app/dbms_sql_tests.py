import ollama

from app.generator import MODEL_NAME
from app.models import (
    DBMSSQLTestPackage,
    DBMSScenario,
    GeneratedDBMSSQLTests,
)
from app.prompts import (
    DBMS_SQL_TEST_SYSTEM_PROMPT,
    build_dbms_sql_test_prompt,
)


def generate_dbms_sql_tests(
    scenarios: list[DBMSScenario],
    postgres_version: str = "17",
) -> list[DBMSSQLTestPackage]:
    """Generate one structured PostgreSQL test package per scenario."""
    if not scenarios:
        raise ValueError("At least one DBMS scenario is required")

    scenario_by_id = {scenario.id: scenario for scenario in scenarios}
    if len(scenario_by_id) != len(scenarios):
        raise ValueError("Scenario IDs must be unique")

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": DBMS_SQL_TEST_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_dbms_sql_test_prompt(
                    scenarios, postgres_version
                ),
            },
        ],
        format=GeneratedDBMSSQLTests.model_json_schema(),
        options={"temperature": 0.2},
    )
    generated = GeneratedDBMSSQLTests.model_validate_json(
        response.message.content
    )

    tests_by_scenario_id = {
        test.scenario_id: test for test in generated.tests
    }
    if len(tests_by_scenario_id) != len(generated.tests):
        raise ValueError(
            "Each generated SQL test must cover a unique scenario"
        )
    if set(tests_by_scenario_id) != set(scenario_by_id):
        raise ValueError(
            "Generated SQL tests must cover every supplied scenario exactly once"
        )
    return generated.tests
