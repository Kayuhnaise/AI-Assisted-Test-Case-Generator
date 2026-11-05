"""Measure DBMS scenario-extraction coverage (R1) over repeated trials.

Run from the backend/ directory with Ollama running and qwen3:4b pulled:

    python ../evaluation/run_dbms_benchmark.py ../evaluation/dbms_benchmark.json --trials 5

Benchmark file format (you label the expert scenarios by hand):

    {
      "document": "<long DBMS requirement document, Markdown or text>",
      "expert_scenarios": [
        {"id": "expert_1", "category": "positive",
         "precondition": "...", "behavior_under_test": "...",
         "expected_result": "..."}
      ]
    }
"""

import argparse
import json
import statistics
from pathlib import Path

from app.dbms_scenarios import (
    evaluate_dbms_scenario_coverage,
    identify_dbms_scenarios,
)
from app.models import DBMSScenario


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--out", type=Path, default=Path("dbms_benchmark_result.json"))
    args = parser.parse_args()

    data = json.loads(args.benchmark.read_text(encoding="utf-8"))
    expert = [DBMSScenario(**s) for s in data["expert_scenarios"]]

    trials = []
    for number in range(1, args.trials + 1):
        extracted = identify_dbms_scenarios(data["document"])
        result = evaluate_dbms_scenario_coverage(expert, extracted)
        trials.append(
            {
                "trial": number,
                "extracted": len(extracted),
                "coverage_percentage": result.coverage_percentage,
                "target_met": result.target_met,
                "uncovered": result.uncovered_expert_scenario_ids,
            }
        )
        print(
            f"trial {number}: {result.coverage_percentage:.1f}% "
            f"({len(extracted)} extracted, uncovered={result.uncovered_expert_scenario_ids})"
        )

    scores = [t["coverage_percentage"] for t in trials]
    summary = {
        "expert_scenarios": len(expert),
        "document_chars": len(data["document"]),
        "trials": trials,
        "mean": statistics.mean(scores),
        "min": min(scores),
        "max": max(scores),
        "trials_meeting_90": sum(t["target_met"] for t in trials),
    }
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"mean {summary['mean']:.1f}%  min {summary['min']:.1f}%  max {summary['max']:.1f}%")


if __name__ == "__main__":
    main()
