"""
Improvement 4 evaluation: structured scenario representation.

For each reference requirement in ../evaluation/reference this script runs
the full /generate pipeline (scenario identification, test generation,
pytest execution), saves the run, and scores it automatically:

- Scenario-Type Coverage: hybrid deterministic gate + LLM judge
  (app/scenario_coverage.py)
- Requirement Alignment: deterministic verbatim-clause check

Usage (from backend/, with Ollama running):
    python evaluate_python_scenarios.py              # generate + score
    python evaluate_python_scenarios.py --score-only # re-score saved runs
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.generator import (
    MODEL_NAME,
    generate_test_cases,
    identify_scenarios,
)
from app.models import Scenario
from app.scenario_coverage import evaluate_scenario_coverage
from app.test_runner import run_pytest


ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = ROOT / "evaluation" / "reference"
OUTPUT_DIR = ROOT / "evaluation" / "improvement4"


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _run_pipeline(reference: dict) -> dict:
    """Run the /generate pipeline; record failures instead of aborting."""
    run: dict = {
        "requirement": reference["requirement"],
        "model": MODEL_NAME,
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        ),
        "scenarios": [],
        "untested_scenario_ids": [],
        "test_cases": [],
        "pytest_code": None,
        "pytest_result": None,
        "pipeline_error": None,
    }
    try:
        scenarios = identify_scenarios(
            reference["requirement"], reference["source_code"]
        )
        run["scenarios"] = [s.model_dump(mode="json") for s in scenarios]
        run["untested_scenario_ids"] = [
            s.id for s in scenarios
            if s.expected_outcome_kind == "unspecified"
        ]
        test_cases, pytest_code = generate_test_cases(
            reference["requirement"], reference["source_code"], scenarios
        )
        run["test_cases"] = [t.model_dump(mode="json") for t in test_cases]
        run["pytest_code"] = pytest_code
        if test_cases:
            run["pytest_result"] = run_pytest(pytest_code).model_dump(
                mode="json"
            )
    except ValueError as exc:
        run["pipeline_error"] = str(exc)
    return run


def _score(reference: dict, run: dict) -> dict:
    references = [
        Scenario.model_validate(item)
        for item in reference["reference_scenarios"]
    ]
    generated = [Scenario.model_validate(item) for item in run["scenarios"]]
    if not generated:
        return {
            "coverage_percentage": 0.0,
            "covered_scenario_count": 0,
            "reference_scenario_count": len(references),
            "alignment_percentage": None,
            "note": "no scenarios generated",
        }
    return evaluate_scenario_coverage(
        reference["requirement"], references, generated
    ).model_dump(mode="json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--score-only",
        action="store_true",
        help="re-score saved runs without calling the generator",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    total_reference = total_covered = 0
    total_generated = total_aligned = 0

    for reference_path in sorted(REFERENCE_DIR.glob("*.json")):
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        result_path = OUTPUT_DIR / f"{reference['id']}_result.json"
        print(f"\n== {reference['id']}", flush=True)

        if args.score_only:
            run = json.loads(result_path.read_text(encoding="utf-8"))
        else:
            print("  running pipeline...", flush=True)
            run = _run_pipeline(reference)

        run["evaluation"] = _score(reference, run)
        _write_json(result_path, run)

        evaluation = run["evaluation"]
        pytest_result = run.get("pytest_result") or {}
        row = {
            "requirement_id": reference["id"],
            "pipeline_error": run.get("pipeline_error"),
            "reference_scenarios": evaluation["reference_scenario_count"],
            "generated_scenarios": len(run["scenarios"]),
            "covered": evaluation["covered_scenario_count"],
            "coverage_percentage": evaluation["coverage_percentage"],
            "alignment_percentage": evaluation["alignment_percentage"],
            "untested_scenarios": len(run.get("untested_scenario_ids", [])),
            "tests_run": pytest_result.get("tests_run", 0),
            "tests_passed": pytest_result.get("passed", 0),
        }
        rows.append(row)

        total_reference += row["reference_scenarios"]
        total_covered += row["covered"]
        total_generated += row["generated_scenarios"]
        total_aligned += evaluation.get("aligned_scenario_count", 0)

        print(
            f"  coverage {row['covered']}/{row['reference_scenarios']} "
            f"({row['coverage_percentage']:.1f}%), "
            f"alignment {row['alignment_percentage']}, "
            f"tests passed {row['tests_passed']}/{row['tests_run']}"
            + (f", ERROR: {row['pipeline_error']}" if row["pipeline_error"] else "")
        )

    summary = {
        "stage": "improvement4_structured_scenarios",
        "model": MODEL_NAME,
        "scored_at_utc": datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        ),
        "overall_coverage_percentage": (
            100 * total_covered / total_reference if total_reference else 0.0
        ),
        "overall_alignment_percentage": (
            100 * total_aligned / total_generated if total_generated else None
        ),
        "covered_reference_scenarios": total_covered,
        "total_reference_scenarios": total_reference,
        "requirements": rows,
    }
    _write_json(OUTPUT_DIR / "summary.json", summary)

    print(
        f"\nOverall coverage: {total_covered}/{total_reference} "
        f"({summary['overall_coverage_percentage']:.1f}%)"
    )
    print(f"Overall alignment: {summary['overall_alignment_percentage']}")
    print(f"Saved: {OUTPUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
