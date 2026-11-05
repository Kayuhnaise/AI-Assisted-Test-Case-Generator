import ollama

from app.dbms_sql_validation import parse_and_validate_sql
from app.generator import MODEL_NAME
from app.models import (
    DBMSCoverageGenerationResponse,
    DBMSCoverageReport,
    DBMSRefinementResponse,
    DBMSSQLTestPackage,
    DBMSScenario,
    GeneratedDBMSSQLScenarios,
    GeneratedDBMSSQLTests,
)
from app.prompts import (
    DBMS_COVERAGE_GENERATION_SYSTEM_PROMPT,
    DBMS_SQL_REPAIR_SYSTEM_PROMPT,
    build_dbms_coverage_generation_prompt,
    build_dbms_sql_repair_prompt,
)


def generate_coverage_guided_scenarios(
    requirement_document: str,
    coverage_report: DBMSCoverageReport,
) -> DBMSCoverageGenerationResponse:
    features = list(
        dict.fromkeys(hint.feature for hint in coverage_report.feature_hints)
    )
    if not features:
        raise ValueError(
            "The coverage report has no recognized uncovered PostgreSQL features"
        )

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": DBMS_COVERAGE_GENERATION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": build_dbms_coverage_generation_prompt(
                    requirement_document, coverage_report
                ),
            },
        ],
        format=GeneratedDBMSSQLScenarios.model_json_schema(),
        options={"temperature": 0.2},
    )
    generated = GeneratedDBMSSQLScenarios.model_validate_json(
        response.message.content
    )
    if not generated.scenarios:
        raise ValueError("Coverage-guided generation returned no scenarios")

    scenarios = [
        scenario.model_copy(update={"id": f"coverage_{index}"})
        for index, scenario in enumerate(generated.scenarios, 1)
    ]
    return DBMSCoverageGenerationResponse(
        targeted_features=features,
        scenarios=scenarios,
    )


def refine_failed_dbms_test(
    scenario: DBMSScenario,
    failed_test: DBMSSQLTestPackage,
    error_message: str,
    actual_sqlstate: str | None,
) -> DBMSRefinementResponse:
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": DBMS_SQL_REPAIR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_dbms_sql_repair_prompt(
                    scenario,
                    failed_test,
                    error_message,
                    actual_sqlstate,
                ),
            },
        ],
        format=GeneratedDBMSSQLTests.model_json_schema(),
        options={"temperature": 0.1},
    )
    generated = GeneratedDBMSSQLTests.model_validate_json(
        response.message.content
    )
    if len(generated.tests) != 1:
        raise ValueError("Repair must return exactly one SQL test")

    repaired = generated.tests[0]
    if (
        repaired.test_id != failed_test.test_id
        or repaired.scenario_id != scenario.id
        or repaired.setup_sql != failed_test.setup_sql
        or repaired.data_sql != failed_test.data_sql
        or repaired.cleanup_sql != failed_test.cleanup_sql
        or repaired.expected_outcome != failed_test.expected_outcome
        or repaired.expected_sqlstate != failed_test.expected_sqlstate
    ):
        raise ValueError(
            "Repair changed test identity, setup, data, cleanup, or expected oracle"
        )
    _, errors = parse_and_validate_sql(repaired)
    if errors:
        raise ValueError("Repaired SQL failed validation: " + "; ".join(errors))

    return DBMSRefinementResponse(
        repaired_test=repaired,
        oracle_preserved=True,
    )
