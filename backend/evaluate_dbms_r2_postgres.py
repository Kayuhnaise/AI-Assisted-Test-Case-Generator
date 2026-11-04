"""Two-stage PostgreSQL benchmark: generate, manually review, then evaluate.

Do not run generated SQL against a non-disposable database.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.dbms_sql_generator import CLAUDE_MODEL, generate_dbms_sql_tests
from app.dbms_postgres_executor import validate_postgres_sql_test
from app.dbms_postgres_oracle import evaluate_postgres_oracle
from app.models import DBMSScenario, DBMSSQLTestCase

ROOT = Path(__file__).resolve().parent
BENCHMARK = ROOT / "tests" / "fixtures" / "dbms_r2_benchmark.json"
OUTPUT = ROOT / "benchmark_results"
ERROR_MAP = {
    "UNIQUE constraint failed": "duplicate key value",
    "NOT NULL constraint failed": "null value",
    "FOREIGN KEY constraint failed": "violates foreign key constraint",
    "CHECK constraint failed": "violates check constraint",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_benchmark():
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8-sig"))
    for case in benchmark["cases"]:
        oracle = case["oracle"]
        if oracle["expected_outcome_type"] == "error":
            old = oracle.get("expected_error")
            if old not in ERROR_MAP:
                raise ValueError(f"Unknown SQLite oracle error {old!r}; review manually")
            oracle["expected_error"] = ERROR_MAP[old]
    return benchmark


def generate():
    benchmark = load_benchmark()
    results = []
    for i, case in enumerate(benchmark["cases"], 1):
        print(f"Generating {i}/{len(benchmark['cases'])}: {case['id']}")
        scenario = DBMSScenario(**{key: case[key] for key in (
            "id", "category", "precondition", "behavior_under_test", "expected_result")})
        entry = {"scenario_id": case["id"], "category": case["category"]}
        try:
            tests = generate_dbms_sql_tests(case["requirement_document"], [scenario], dialect="postgresql")
            entry["generated_test"] = tests[0].model_dump(mode="json")
            entry["generation_successful"] = True
        except Exception as exc:
            entry["generation_successful"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
        results.append(entry)
    OUTPUT.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUTPUT / f"postgres_review_{timestamp}.json"
    path.write_text(json.dumps({"model": CLAUDE_MODEL, "benchmark_id": benchmark["benchmark_id"],
                                "results": results}, indent=2), encoding="utf-8")
    print(f"Review ALL setup_sql, test_sql and verification_assertions before executing: {path}")
    print(f"SHA256: {digest(path)}")


def evaluate(path, approved_hash):
    if digest(path).lower() != approved_hash.lower():
        raise SystemExit("Review-file SHA256 mismatch; review the exact file again")
    if not __import__('os').getenv('DBTESTGEN_POSTGRES_URL'):
        raise SystemExit("DBTESTGEN_POSTGRES_URL must point to a disposable PostgreSQL instance")
    benchmark = load_benchmark()
    reviewed = json.loads(path.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in benchmark["cases"]}
    results = []
    for entry in reviewed["results"]:
        result = {"scenario_id": entry["scenario_id"], "generation_successful": entry["generation_successful"]}
        if not entry["generation_successful"]:
            result["error"] = entry.get("error")
        else:
            case = DBMSSQLTestCase.model_validate(entry["generated_test"])
            if case.sql_dialect != "postgresql" or case.scenario_id != entry["scenario_id"]:
                raise ValueError("Invalid reviewed test dialect or scenario ID")
            oracle = by_id[entry["scenario_id"]]["oracle"]
            try:
                validation = validate_postgres_sql_test(case, trusted_sql=True)
                independent = evaluate_postgres_oracle(case, oracle)
                expected = case.expected_outcome
                result.update({"validation_status": validation.status,
                               "validation_errors": validation.errors,
                               "oracle_match": expected.outcome_type == oracle["expected_outcome_type"] and (
                                   oracle["expected_outcome_type"] != "error" or (
                                       expected.expected_error is not None and
                                       oracle["expected_error"].lower() in expected.expected_error.lower())),
                               "independent_oracle_passed": independent["passed"],
                               "independent_oracle_result": independent})
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
        results.append(result)
        print(result["scenario_id"], result.get("validation_status", "error"),
              "independent:", result.get("independent_oracle_passed", False))
    total = len(results)
    valid = sum(r.get("validation_status") == "passed" and r.get("independent_oracle_passed", False)
                for r in results)
    summary = {"total": total, "generated": sum(r["generation_successful"] for r in results),
               "validated": sum(r.get("validation_status") == "passed" for r in results),
               "oracle_matched": sum(r.get("oracle_match", False) for r in results),
               "independently_valid": valid,
               "independent_validity_percentage": round(100 * valid / total, 2) if total else 0.0}
    OUTPUT.mkdir(exist_ok=True)
    report = OUTPUT / f"postgres_evaluation_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    report.write_text(json.dumps({"model": reviewed["model"], "summary": summary, "results": results}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Saved:", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed-file", type=Path)
    parser.add_argument("--approved-sha256")
    args = parser.parse_args()
    if args.reviewed_file or args.approved_sha256:
        if not args.reviewed_file or not args.approved_sha256:
            parser.error("Both --reviewed-file and --approved-sha256 are required")
        evaluate(args.reviewed_file, args.approved_sha256)
    else:
        generate()
