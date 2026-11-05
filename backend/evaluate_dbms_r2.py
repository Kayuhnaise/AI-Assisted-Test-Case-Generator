
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.dbms_sql_generator import CLAUDE_MODEL, generate_dbms_sql_tests
from app.dbms_sql_validator import validate_sql_test
from app.models import DBMSScenario
from app.dbms_r2_oracle import evaluate_independent_oracle


BASE_DIR = Path(__file__).resolve().parent

BENCHMARK_PATH = (
    BASE_DIR / "tests" / "fixtures" / "dbms_r2_benchmark.json"
)

# Separate results by model and run timestamp to preserve prior benchmarks.
RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
SAFE_MODEL_NAME = "".join(
    char if char.isalnum() or char in "-_" else "_"
    for char in CLAUDE_MODEL
)
OUTPUT_PATH = BASE_DIR / f"dbms_r2_results_{SAFE_MODEL_NAME}_{RUN_TIMESTAMP}.json"


def evaluate_case(case):
    scenario = DBMSScenario(
        id=case["id"],
        category=case["category"],
        precondition=case["precondition"],
        behavior_under_test=case["behavior_under_test"],
        expected_result=case["expected_result"],
    )

    result = {
        "scenario_id": case["id"],
        "category": case["category"],
        "generation_successful": False,
        "validation_status": "not_run",
        "oracle_match": False,
        "error": None,
        "independent_oracle_passed": False,
        "independent_oracle_result": None,
    }

    try:
        generated = generate_dbms_sql_tests(
            requirement_document=case["requirement_document"],
            scenarios=[scenario],
        )

        test_case = generated[0]
        result["generation_successful"] = True

        # Compare generated expected behavior with the
        # independently specified benchmark oracle.
        oracle = case["oracle"]
        expected = test_case.expected_outcome

        outcome_matches = (
            expected.outcome_type
            == oracle["expected_outcome_type"]
        )

        error_matches = True
        if "expected_error" in oracle:
            error_matches = (
                expected.expected_error is not None
                and oracle["expected_error"].lower()
                in expected.expected_error.lower()
            )

        result["oracle_match"] = (
            outcome_matches and error_matches
        )

        validation = validate_sql_test(test_case)

        result["validation_status"] = validation.status
        result["validation_errors"] = validation.errors
        result["actual_outcome"] = validation.actual_outcome

        independent_result = evaluate_independent_oracle(
            test_case,
            case["oracle"],
        )

        result["independent_oracle_passed"] = (
            independent_result["passed"]
        )
        result["independent_oracle_result"] = independent_result
        result["generated_test"] = test_case.model_dump(
            mode="json"
        )

    except Exception as exc:
        result["error"] = (
            f"{type(exc).__name__}: {exc}"
        )

    return result


def main():
    with BENCHMARK_PATH.open(
        encoding="utf-8-sig"
    ) as file:
        benchmark = json.load(file)

    cases = benchmark["cases"]
    results = []

    print(f"Evaluating {len(cases)} DBMS scenarios...")

    for index, case in enumerate(cases, start=1):
        print(
            f"[{index}/{len(cases)}] "
            f"{case['id']} ({case['category']})"
        )

        result = evaluate_case(case)
        results.append(result)

        print(
            f"  Generation: "
            f"{result['generation_successful']}"
        )
        print(
            f"  Validation: "
            f"{result['validation_status']}"
        )
        print(
            f"  Oracle match: "
            f"{result['oracle_match']}"
        )

        print(
                f"  Independent oracle: "
                f"{result['independent_oracle_passed']}"
            )

        if result["error"]:
            print(f"  Error: {result['error']}")

    total = len(results)

    generated = sum(
        result["generation_successful"]
        for result in results
    )

    executed_and_passed = sum(
        result["validation_status"] == "passed"
        for result in results
    )

    oracle_matched = sum(
        result["oracle_match"]
        for result in results
    )

    independently_valid = sum(
        result["generation_successful"]
        and result["validation_status"] == "passed"
        and result["independent_oracle_passed"]
        for result in results
    )

    summary = {
        "total_scenarios": total,
        "generation_successful": generated,
        "validation_passed": executed_and_passed,
        "oracle_matched": oracle_matched,
        "independent_oracle_passed": sum(
            result["independent_oracle_passed"]
            for result in results
        ),
        "independently_valid": independently_valid,
        "independent_validity_percentage": round(
            100 * independently_valid / total, 2
        ) if total else 0.0,
        "category_counts": dict(
            Counter(r["category"] for r in results)
        ),
    }

    report = {
        "benchmark_id": benchmark["benchmark_id"],
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "model": CLAUDE_MODEL,
        "summary": summary,
        "results": results,
    }

    with OUTPUT_PATH.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(report, file, indent=2)

    print("\nEvaluation complete.")
    print(json.dumps(summary, indent=2))
    print(f"\nResults saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
