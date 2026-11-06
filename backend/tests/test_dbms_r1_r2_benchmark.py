import json
from unittest.mock import patch

import pytest

from app.models import (
    DBMSCoverageMatch,
    DBMSCoverageResponse,
    DBMSScenario,
    DBMSSQLTestCase,
)
import evaluate_dbms_r1_r2_postgres as benchmark


from evaluate_dbms_r1_r2_postgres import load_benchmark, run_case


def test_benchmark_includes_supplemental_transaction_scenario():
    cases = load_benchmark()
    by_id = {case["id"]: case for case in cases}

    assert len(cases) == 16
    assert "R2-015" in by_id
    assert "savepoint" in by_id["R2-015"]["behavior_under_test"]
    assert by_id["R2-015"]["oracle"]["verification_assertions"]


def test_repeated_pipeline_case_preserves_r1_scenario_id():
    case = load_benchmark()[0]
    extracted = DBMSScenario(
        id="R1-EXTRACTED-001",
        category=case["category"],
        precondition=case["precondition"],
        behavior_under_test=case["behavior_under_test"],
        expected_result=case["expected_result"],
    )
    generated = DBMSSQLTestCase.model_validate({
        "id": "SQL-001",
        "scenario_id": extracted.id,
        "title": "Generated test",
        "category": extracted.category,
        "sql_dialect": "postgresql",
        "preconditions": [],
        "constraints": [],
        "setup_sql": [],
        "test_sql": "SELECT 1",
        "expected_outcome": {
            "outcome_type": "scalar",
            "expected_value": 1,
            "assertion_description": "Returns one",
        },
    })
    coverage = DBMSCoverageResponse(
        expert_scenario_count=1,
        extracted_scenario_count=1,
        covered_scenario_count=1,
        coverage_percentage=100,
        target_percentage=90,
        target_met=True,
        matches=[
            DBMSCoverageMatch(
                expert_scenario_id=case["id"],
                extracted_scenario_id=extracted.id,
            )
        ],
        uncovered_expert_scenario_ids=[],
    )

    with (
        patch(
            "evaluate_dbms_r1_r2_postgres.identify_dbms_scenarios",
            return_value=[extracted],
        ),
        patch(
            "evaluate_dbms_r1_r2_postgres.evaluate_dbms_scenario_coverage",
            return_value=coverage,
        ),
        patch(
            "evaluate_dbms_r1_r2_postgres.generate_dbms_sql_tests",
            return_value=[generated],
        ) as generate,
    ):
        result = run_case(case, trial=2)

    assert result["trial"] == 2
    assert result["stages"]["extraction"]["status"] == "passed"
    assert result["stages"]["coverage"]["result"]["covered_scenario_count"] == 1
    assert result["stages"]["sql_generation"]["test_cases"][0][
        "scenario_id"
    ] == extracted.id
    assert result["stages"]["review"]["status"] == "pending"
    generate.assert_called_once_with(
        requirement_document=case["requirement_document"],
        scenarios=[extracted],
        dialect="postgresql",
    )


def test_extraction_error_is_recorded_at_the_correct_stage():
    case = load_benchmark()[0]
    with patch(
        "evaluate_dbms_r1_r2_postgres.identify_dbms_scenarios",
        side_effect=ValueError("model output was invalid"),
    ):
        result = run_case(case, trial=1)

    assert result["stages"]["extraction"]["status"] == "failed"
    assert "model output was invalid" in result["stages"]["extraction"]["error"]
    assert result["stages"]["coverage"]["status"] == "blocked"
    assert result["stages"]["sql_generation"]["status"] == "blocked"
    assert result["stages"]["review"]["status"] == "not_applicable"


def test_review_must_be_explicitly_approved_before_execution(tmp_path):
    scenario = DBMSScenario(
        id="R1-001",
        category="positive",
        precondition="The users table exists.",
        behavior_under_test="Read a user.",
        expected_result="The user is returned.",
    )
    test_case = DBMSSQLTestCase.model_validate({
        "id": "SQL-001",
        "scenario_id": scenario.id,
        "title": "Read user",
        "category": scenario.category,
        "sql_dialect": "postgresql",
        "preconditions": [],
        "constraints": [],
        "setup_sql": [],
        "test_sql": "SELECT 1",
        "expected_outcome": {
            "outcome_type": "scalar",
            "expected_value": 1,
            "assertion_description": "One is returned",
        },
    })
    case = {
        "id": "R2-001",
        "category": "positive",
        "requirement_document": "Users can be read.",
        "precondition": scenario.precondition,
        "behavior_under_test": scenario.behavior_under_test,
        "expected_result": scenario.expected_result,
        "oracle": {
            "expected_outcome_type": "scalar",
            "verification_assertions": [],
        },
    }
    review_file = tmp_path / "review.json"
    review_file.write_text(
        json.dumps({
            "benchmark_id": "DBMS-R1-R2-001",
            "benchmark_sha256": "fixture",
            "trials": 1,
            "results": [{
                "case_id": case["id"],
                "trial": 1,
                "stages": {
                    "extraction": {
                        "status": "passed",
                        "scenarios": [scenario.model_dump(mode="json")],
                    },
                    "coverage": {
                        "status": "passed",
                        "result": {
                            "matches": [{
                                "expert_scenario_id": case["id"],
                                "extracted_scenario_id": scenario.id,
                            }],
                            "covered_scenario_count": 1,
                        },
                    },
                    "sql_generation": {
                        "status": "passed",
                        "test_cases": [test_case.model_dump(mode="json")],
                    },
                    "review": {"status": "pending"},
                },
            }],
        }),
        encoding="utf-8",
    )

    with (
        patch.object(benchmark, "load_benchmark", return_value=[case]),
        patch.object(benchmark, "_source_digest", return_value="fixture"),
        patch.object(benchmark, "disposable_postgres") as start_container,
        pytest.raises(ValueError, match="review status"),
    ):
        benchmark.evaluate_review(
            review_file,
            benchmark.file_digest(review_file),
        )

    start_container.assert_not_called()
