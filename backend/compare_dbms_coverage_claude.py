
"""Compare Claude coverage with saved Ollama pilot results."""

import json
import time
from pathlib import Path

from app.dbms_coverage_claude import (
    CLAUDE_COVERAGE_MODEL,
    evaluate_coverage_claude,
)
from app.models import DBMSScenario


def main():
    pilot_path = Path(
        "benchmark_results/dbms_r1_pilot_20261105T194556Z.json"
    )

    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))

    results = []

    for entry in pilot["results"]:
        expert = DBMSScenario.model_validate(
            entry["expert_scenario"]
        )
        extracted = [
            DBMSScenario.model_validate(item)
            for item in entry["extracted_scenarios"]
        ]

        print(f"\nEvaluating {entry['case_id']}...", flush=True)

        start = time.perf_counter()

        try:
            coverage = evaluate_coverage_claude(
                [expert], extracted
            )
            claude_result = coverage.model_dump(mode="json")
            error = None
        except Exception as exc:
            claude_result = None
            error = f"{type(exc).__name__}: {exc}"

        elapsed = round(time.perf_counter() - start, 2)

        result = {
            "case_id": entry["case_id"],
            "ollama_original_coverage": entry[
                "original_coverage"
            ]["coverage_percentage"],
            "ollama_batched_coverage": entry[
                "batched_coverage"
            ]["coverage_percentage"],
            "claude_coverage": claude_result,
            "claude_error": error,
            "claude_seconds": elapsed,
        }

        results.append(result)

        print(
            "Ollama coverage:",
            result["ollama_original_coverage"],
            "%",
        )

        if claude_result:
            print(
                "Claude coverage:",
                claude_result["coverage_percentage"],
                "%",
            )
            print("Matches:", claude_result["matches"])
        else:
            print("Claude error:", error)

        print("Claude time:", elapsed, "seconds")

    output_path = Path(
        "benchmark_results/dbms_r1_claude_comparison.json"
    )

    output_path.write_text(
        json.dumps(
            {
                "claude_model": CLAUDE_COVERAGE_MODEL,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
