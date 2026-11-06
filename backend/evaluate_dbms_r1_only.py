
"""Evaluate R1 scenario extraction without running R2 or PostgreSQL."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.dbms_scenarios import (
    evaluate_dbms_scenario_coverage,
    identify_dbms_scenarios,
)
from app.dbms_coverage_experimental import evaluate_coverage_batched
from app.generator import MODEL_NAME
from app.models import DBMSScenario
from evaluate_dbms_r1_r2_postgres import load_benchmark


OUTPUT_DIR = Path(__file__).resolve().parent / "benchmark_results"


def evaluate_case(case):
    expert = DBMSScenario(
        id=case["id"],
        category=case["category"],
        precondition=case["precondition"],
        behavior_under_test=case["behavior_under_test"],
        expected_result=case["expected_result"],
    )

    result = {
        "case_id": case["id"],
        "requirement_document": case["requirement_document"],
        "expert_scenario": expert.model_dump(mode="json"),
    }

    start = time.perf_counter()

    try:
        scenarios = identify_dbms_scenarios(
            case["requirement_document"]
        )
    except Exception as exc:
        result["extraction_status"] = "failed"
        result["extraction_error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        result["extraction_seconds"] = round(
            time.perf_counter() - start, 2
        )
        return result

    result["extraction_status"] = "passed"
    result["extraction_seconds"] = round(
        time.perf_counter() - start, 2
    )
    result["extracted_scenario_count"] = len(scenarios)
    result["extracted_scenarios"] = [
        scenario.model_dump(mode="json")
        for scenario in scenarios
    ]

    for name, evaluator in (
        ("original", evaluate_dbms_scenario_coverage),
        ("batched", evaluate_coverage_batched),
    ):
        start = time.perf_counter()

        try:
            coverage = evaluator([expert], scenarios)
            result[f"{name}_coverage"] = coverage.model_dump(
                mode="json"
            )
        except Exception as exc:
            result[f"{name}_coverage_error"] = (
                f"{type(exc).__name__}: {exc}"
            )

        result[f"{name}_coverage_seconds"] = round(
            time.perf_counter() - start, 2
        )

    return result


def main():
    cases = load_benchmark()

    # Start with two cases to validate the evaluation process.
    cases = cases[:2]

    results = []

    for index, case in enumerate(cases, start=1):
        print(
            f"\n[{index}/{len(cases)}] Evaluating {case['id']}",
            flush=True,
        )

        result = evaluate_case(case)
        results.append(result)

        print(
            "Extraction:",
            result["extraction_status"],
            "| Scenarios:",
            result.get("extracted_scenario_count", 0),
            "| Time:",
            result["extraction_seconds"],
            "seconds",
            flush=True,
        )

        for name in ("original", "batched"):
            coverage = result.get(f"{name}_coverage")

            if coverage:
                print(
                    f"{name.capitalize()} coverage:",
                    coverage["coverage_percentage"],
                    "%",
                    flush=True,
                )
            else:
                print(
                    f"{name.capitalize()} coverage:",
                    result.get(f"{name}_coverage_error", "not run"),
                    flush=True,
                )

    OUTPUT_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    output_path = (
        OUTPUT_DIR / f"dbms_r1_pilot_{timestamp}.json"
    )

    output_path.write_text(
        json.dumps(
            {
                "model": MODEL_NAME,
                "evaluated_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
