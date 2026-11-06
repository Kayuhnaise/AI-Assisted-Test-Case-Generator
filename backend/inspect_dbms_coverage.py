
"""Inspect individual R1 coverage judgments from a saved pilot."""

import json
from pathlib import Path

import ollama

from app.generator import MODEL_NAME
from app.models import DBMSScenario, ScenarioPairJudgments
from app.prompts import (
    DBMS_COVERAGE_SYSTEM_PROMPT,
    build_dbms_coverage_prompt,
)


def main():
    files = sorted(
        Path("benchmark_results").glob("dbms_r1_pilot_*.json")
    )

    if not files:
        raise FileNotFoundError("No R1 pilot results found")

    report = json.loads(files[-1].read_text(encoding="utf-8"))

    for entry in report["results"]:
        print(f"\n=== {entry['case_id']} ===", flush=True)

        expert = DBMSScenario.model_validate(
            entry["expert_scenario"]
        )
        extracted = [
            DBMSScenario.model_validate(item)
            for item in entry.get("extracted_scenarios", [])
        ]

        if not extracted:
            print("No extracted scenarios")
            continue

        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": DBMS_COVERAGE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_dbms_coverage_prompt(
                        [expert], extracted
                    ),
                },
            ],
            format=ScenarioPairJudgments.model_json_schema(),
            options={"temperature": 0},
        )

        judgments = ScenarioPairJudgments.model_validate_json(
            response.message.content
        ).judgments

        for judgment in judgments:
            print(
                f"\nExtracted: {judgment.extracted_scenario_id}"
            )
            print(
                "  Precondition:",
                judgment.precondition_matches,
            )
            print(
                "  Behavior:",
                judgment.behavior_matches,
            )
            print(
                "  Expected result:",
                judgment.expected_result_matches,
            )
            print(
                "  Overall:",
                (
                    judgment.precondition_matches
                    and judgment.behavior_matches
                    and judgment.expected_result_matches
                ),
            )


if __name__ == "__main__":
    main()
