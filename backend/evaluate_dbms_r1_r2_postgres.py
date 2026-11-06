"""Repeated, review-gated R1-to-R2 PostgreSQL benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import httpx
import ollama
import psycopg
from pydantic import ValidationError

from app.dbms_postgres_executor import validate_postgres_sql_test
from app.dbms_postgres_oracle import evaluate_postgres_oracle
from app.dbms_scenarios import (
    COVERAGE_TARGET_PERCENTAGE,
    evaluate_dbms_scenario_coverage,
    identify_dbms_scenarios,
)
from app.dbms_sql_generator import (
    CLAUDE_MODEL,
    generate_dbms_sql_tests,
)
from app.disposable_postgres import disposable_postgres
from app.generator import MODEL_NAME
from app.models import DBMSScenario, DBMSSQLTestCase


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "tests" / "fixtures"
BASE_BENCHMARK = FIXTURES / "dbms_r2_benchmark.json"
SUPPLEMENTAL_BENCHMARK = FIXTURES / "dbms_r1_r2_supplemental.json"
OUTPUT = ROOT / "benchmark_results"
ERROR_MAP = {
    "UNIQUE constraint failed": "duplicate key value",
    "NOT NULL constraint failed": "null value",
    "FOREIGN KEY constraint failed": "foreign key constraint",
    "CHECK constraint failed": "check constraint",
}

GENERATION_ERRORS = (
    anthropic.APIError,
    httpx.HTTPError,
    TimeoutError,
    ValidationError,
    ValueError,
)
EXTRACTION_ERRORS = (
    httpx.HTTPError,
    ollama.ResponseError,
    TimeoutError,
    ValidationError,
    ValueError,
)
EXECUTION_ERRORS = (
    OSError,
    psycopg.Error,
    RuntimeError,
    subprocess.TimeoutExpired,
)


def _source_digest() -> str:
    digest = hashlib.sha256()
    for path in (BASE_BENCHMARK, SUPPLEMENTAL_BENCHMARK):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_benchmark() -> list[dict]:
    cases = []
    for path in (BASE_BENCHMARK, SUPPLEMENTAL_BENCHMARK):
        benchmark = json.loads(path.read_text(encoding="utf-8-sig"))
        cases.extend(benchmark["cases"])

    for case in cases:
        oracle = case["oracle"]
        if oracle["expected_outcome_type"] == "error":
            old_error = oracle.get("expected_error")
            if old_error in ERROR_MAP:
                oracle["expected_error"] = ERROR_MAP[old_error]
            if not oracle.get("expected_error"):
                raise ValueError(
                    f"Benchmark case {case['id']} needs a PostgreSQL "
                    "expected_error oracle"
                )
    case_ids = [case["id"] for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Benchmark case IDs must be unique")
    return cases


def _stage(status: str, **details) -> dict:
    return {"status": status, **details}


def run_case(case: dict, trial: int) -> dict:
    expert = DBMSScenario(
        id=case["id"],
        category=case["category"],
        precondition=case["precondition"],
        behavior_under_test=case["behavior_under_test"],
        expected_result=case["expected_result"],
    )
    entry = {
        "case_id": case["id"],
        "trial": trial,
        "requirement_document": case["requirement_document"],
        "expert_scenario": expert.model_dump(mode="json"),
        "oracle": case["oracle"],
        "stages": {},
    }

    try:
        scenarios = identify_dbms_scenarios(case["requirement_document"])
    except EXTRACTION_ERRORS as exc:
        entry["stages"]["extraction"] = _stage(
            "failed",
            error=f"{type(exc).__name__}: {exc}",
        )
        entry["stages"]["coverage"] = _stage(
            "blocked",
            reason="R1 extraction did not produce scenarios",
        )
        entry["stages"]["sql_generation"] = _stage(
            "blocked",
            reason="R1 extraction did not produce scenarios",
        )
        entry["stages"]["review"] = _stage("not_applicable")
        return entry

    entry["stages"]["extraction"] = _stage(
        "passed",
        scenarios=[
            scenario.model_dump(mode="json")
            for scenario in scenarios
        ],
    )

    try:
        coverage = evaluate_dbms_scenario_coverage(
            [expert],
            scenarios,
        )
    except EXTRACTION_ERRORS as exc:
        entry["stages"]["coverage"] = _stage(
            "failed",
            error=f"{type(exc).__name__}: {exc}",
        )
    else:
        entry["stages"]["coverage"] = _stage(
            "passed",
            result=coverage.model_dump(mode="json"),
        )

    try:
        test_cases = generate_dbms_sql_tests(
            requirement_document=case["requirement_document"],
            scenarios=scenarios,
            dialect="postgresql",
        )
    except GENERATION_ERRORS as exc:
        entry["stages"]["sql_generation"] = _stage(
            "failed",
            error=f"{type(exc).__name__}: {exc}",
        )
        entry["stages"]["review"] = _stage("not_applicable")
    else:
        entry["stages"]["sql_generation"] = _stage(
            "passed",
            test_cases=[
                test_case.model_dump(mode="json")
                for test_case in test_cases
            ],
        )
        entry["stages"]["review"] = _stage("pending")
    return entry


def generate_review(trials: int) -> Path:
    if trials < 1:
        raise ValueError("trials must be at least 1")

    cases = load_benchmark()
    results = []
    for trial in range(1, trials + 1):
        for index, case in enumerate(cases, start=1):
            print(
                f"Trial {trial}/{trials}, case {index}/{len(cases)}: "
                f"{case['id']}"
            )
            result = run_case(case, trial)
            results.append(result)
            stages = result["stages"]
            print(
                "  extraction:",
                stages["extraction"]["status"],
                "| coverage:",
                stages["coverage"]["status"],
                "| SQL generation:",
                stages["sql_generation"]["status"],
            )

    OUTPUT.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = OUTPUT / f"dbms_r1_r2_review_{timestamp}.json"
    report_path.write_text(
        json.dumps(
            {
                "benchmark_id": "DBMS-R1-R2-001",
                "benchmark_sha256": _source_digest(),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "trials": trials,
                "models": {
                    "r1": MODEL_NAME,
                    "r2": CLAUDE_MODEL,
                },
                "review_required": True,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Review every generated SQL statement before execution: {report_path}")
    print(f"SHA256: {file_digest(report_path)}")
    return report_path


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_reviewed_cases(entry: dict) -> list[DBMSSQLTestCase]:
    stages = entry["stages"]
    if stages["sql_generation"]["status"] != "passed":
        return []

    scenarios = [
        DBMSScenario.model_validate(item)
        for item in stages["extraction"]["scenarios"]
    ]
    scenario_by_id = {scenario.id: scenario for scenario in scenarios}
    if len(scenario_by_id) != len(scenarios):
        raise ValueError(
            f"{entry['case_id']} trial {entry['trial']} has duplicate "
            "extracted scenario IDs"
        )
    generated = [
        DBMSSQLTestCase.model_validate(item)
        for item in stages["sql_generation"]["test_cases"]
    ]
    if len(generated) != len(scenarios):
        raise ValueError(
            f"{entry['case_id']} trial {entry['trial']} must have exactly "
            "one SQL test per extracted scenario"
        )

    test_scenario_ids = [case.scenario_id for case in generated]
    if (
        len(set(test_scenario_ids)) != len(test_scenario_ids)
        or set(test_scenario_ids) != set(scenario_by_id)
    ):
        raise ValueError(
            f"{entry['case_id']} trial {entry['trial']} has invalid "
            "scenario traceability"
        )

    for test_case in generated:
        source = scenario_by_id[test_case.scenario_id]
        if test_case.category != source.category:
            raise ValueError(
                f"Category mismatch for scenario {source.id}"
            )
        if test_case.sql_dialect != "postgresql":
            raise ValueError(
                f"Test {test_case.id} must use PostgreSQL"
            )
    return generated


def _coverage_match_for_case(entry: dict) -> dict[str, str]:
    stage = entry["stages"]["coverage"]
    if stage["status"] != "passed":
        return {}
    coverage = stage["result"]
    return {
        match["extracted_scenario_id"]: match["expert_scenario_id"]
        for match in coverage["matches"]
    }


def evaluate_review(review_path: Path, approved_sha256: str) -> Path:
    actual_digest = file_digest(review_path)
    if actual_digest.lower() != approved_sha256.lower():
        raise ValueError(
            "Review-file SHA256 mismatch; review the exact file again"
        )

    reviewed = json.loads(review_path.read_text(encoding="utf-8"))
    if reviewed.get("benchmark_sha256") != _source_digest():
        raise ValueError(
            "Benchmark fixture changed since the review file was generated"
        )
    cases = load_benchmark()
    case_by_id = {case["id"]: case for case in cases}
    trial_count = reviewed.get("trials")
    if type(trial_count) is not int or trial_count < 1:
        raise ValueError("Review file must specify a positive trial count")
    if reviewed.get("benchmark_id") != "DBMS-R1-R2-001":
        raise ValueError("Review file has an unsupported benchmark ID")
    expected_runs = {
        (case_id, trial)
        for case_id in case_by_id
        for trial in range(1, trial_count + 1)
    }
    actual_runs = [
        (entry["case_id"], entry["trial"])
        for entry in reviewed["results"]
    ]
    if (
        len(set(actual_runs)) != len(actual_runs)
        or set(actual_runs) != expected_runs
    ):
        raise ValueError(
            "Review file must contain exactly one entry for every "
            "benchmark case and trial"
        )

    test_results = []
    review_results = []
    reviewed_sql_test_cases = 0
    approved_sql_test_cases = 0
    rejected_sql_test_cases = 0
    for entry in reviewed["results"]:
        case = case_by_id.get(entry["case_id"])
        if case is None:
            raise ValueError(f"Unknown benchmark case {entry['case_id']!r}")

        generated = _validate_reviewed_cases(entry)
        review_status = entry["stages"]["review"]["status"]
        if generated and review_status not in ("approved", "rejected"):
            raise ValueError(
                f"Set the review status to approved or rejected for "
                f"{entry['case_id']} trial {entry['trial']} before execution"
            )
        if not generated and review_status != "not_applicable":
            raise ValueError(
                f"Review must be not_applicable when SQL generation did not "
                f"succeed for {entry['case_id']} trial {entry['trial']}"
            )
        reviewed_sql_test_cases += len(generated)
        if review_status == "rejected":
            reason = entry["stages"]["review"].get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(
                    f"Provide a review rejection reason for "
                    f"{entry['case_id']} trial {entry['trial']}"
                )
            rejected_sql_test_cases += len(generated)
            review_results.append({
                "case_id": entry["case_id"],
                "trial": entry["trial"],
                "status": "rejected",
                "reason": reason,
                "test_case_count": len(generated),
            })
            continue

        approved_sql_test_cases += len(generated)
        if generated:
            review_results.append({
                "case_id": entry["case_id"],
                "trial": entry["trial"],
                "status": "approved",
                "test_case_count": len(generated),
            })
        matched_scenario_to_expert = _coverage_match_for_case(entry)
        for test_case in generated:
            expert_id = matched_scenario_to_expert.get(test_case.scenario_id)
            oracle = case["oracle"] if expert_id == case["case_id"] else {
                "expected_outcome_type": "database_state",
                "verification_assertions": [],
            }
            result = {
                "case_id": entry["case_id"],
                "trial": entry["trial"],
                "test_case_id": test_case.id,
                "scenario_id": test_case.scenario_id,
                "oracle_applicable": expert_id == case["case_id"],
            }
            try:
                with disposable_postgres() as database_url:
                    validation = validate_postgres_sql_test(
                        test_case,
                        trusted_sql=True,
                        database_url=database_url,
                    )
                result["validation"] = validation.model_dump(mode="json")
            except EXECUTION_ERRORS as exc:
                result["validation"] = {
                    "status": "error",
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
                result["independent_oracle"] = {
                    "passed": False,
                    "errors": ["Skipped because PostgreSQL validation failed"],
                }
                test_results.append(result)
                continue

            if result["oracle_applicable"]:
                try:
                    with disposable_postgres() as database_url:
                        result["independent_oracle"] = (
                            evaluate_postgres_oracle(
                                test_case,
                                oracle,
                                database_url=database_url,
                            )
                        )
                except EXECUTION_ERRORS as exc:
                    result["independent_oracle"] = {
                        "passed": False,
                        "errors": [f"{type(exc).__name__}: {exc}"],
                    }
            test_results.append(result)

    expert_total = len(reviewed["results"])
    stage_counts = Counter()
    for entry in reviewed["results"]:
        for stage_name, stage in entry["stages"].items():
            stage_counts[f"{stage_name}:{stage['status']}"] += 1
    stage_success_percentages = {
        stage_name: (
            100.0
            * sum(
                entry["stages"][stage_name]["status"] == "passed"
                for entry in reviewed["results"]
            )
            / expert_total
            if expert_total
            else 0.0
        )
        for stage_name in ("extraction", "coverage", "sql_generation")
    }
    review_eligible = reviewed_sql_test_cases
    stage_success_percentages["review"] = (
        100.0 * approved_sql_test_cases / review_eligible
        if review_eligible
        else 0.0
    )
    validation_passed = sum(
        item["validation"]["status"] == "passed"
        for item in test_results
    )
    oracle_results = [
        item for item in test_results if item["oracle_applicable"]
    ]
    oracle_passed = sum(
        item["independent_oracle"].get("passed", False)
        for item in oracle_results
    )

    covered_total = sum(
        entry["stages"]["coverage"]["result"]["covered_scenario_count"]
        for entry in reviewed["results"]
        if entry["stages"]["coverage"]["status"] == "passed"
    )
    summary = {
        "requirement_trials": expert_total,
        "distinct_expert_scenarios": len(case_by_id),
        "expert_scenarios_by_category": dict(sorted(Counter(
            case["category"] for case in cases
        ).items())),
        "r1_coverage_target_percentage": COVERAGE_TARGET_PERCENTAGE,
        "r1_covered_expert_scenarios": covered_total,
        "r1_coverage_percentage": (
            100.0 * covered_total / expert_total if expert_total else 0.0
        ),
        "r1_coverage_target_met": (
            100.0 * covered_total / expert_total
            >= COVERAGE_TARGET_PERCENTAGE
            if expert_total
            else False
        ),
        "stage_outcomes": dict(sorted(stage_counts.items())),
        "stage_success_percentages": stage_success_percentages,
        "generated_sql_test_cases": reviewed_sql_test_cases,
        "review_approved_sql_test_cases": approved_sql_test_cases,
        "review_rejected_sql_test_cases": rejected_sql_test_cases,
        "postgres_validation_passed": validation_passed,
        "postgres_validation_failures": len(test_results) - validation_passed,
        "postgres_validation_percentage": (
            100.0 * validation_passed / len(test_results)
            if test_results
            else 0.0
        ),
        "independent_oracle_applicable": len(oracle_results),
        "independent_oracle_passed": oracle_passed,
        "independent_oracle_percentage": (
            100.0 * oracle_passed / len(oracle_results)
            if oracle_results
            else 0.0
        ),
    }
    OUTPUT.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = OUTPUT / f"dbms_r1_r2_evaluation_{timestamp}.json"
    report_path.write_text(
        json.dumps(
            {
                "review_file": str(review_path),
                "review_sha256": actual_digest,
                "benchmark_sha256": reviewed["benchmark_sha256"],
                "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
                "review_results": review_results,
                "results": test_results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    print(f"Saved evaluation: {report_path}")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--reviewed-file", type=Path)
    parser.add_argument("--approved-sha256")
    args = parser.parse_args()

    if args.reviewed_file or args.approved_sha256:
        if not args.reviewed_file or not args.approved_sha256:
            parser.error(
                "Both --reviewed-file and --approved-sha256 are required"
            )
        evaluate_review(args.reviewed_file, args.approved_sha256)
        return
    generate_review(args.trials)


if __name__ == "__main__":
    main()
