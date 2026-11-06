import json
from datetime import datetime, timezone
from pathlib import Path

from app.dbms_scenarios import identify_dbms_scenarios

INPUT_PATH = Path(
    "tests/fixtures/external/library_management_r1_input.md"
)
REFERENCE_PATH = Path(
    "tests/fixtures/external/library_management_r1_reference.json"
)
OUTPUT_DIR = Path("benchmark_results")


def main():
    document = INPUT_PATH.read_text(encoding="utf-8-sig")
    reference = json.loads(
        REFERENCE_PATH.read_text(encoding="utf-8-sig")
    )

    print("Library Management System R1 Benchmark")
    print("--------------------------------------")
    print(f"Input characters: {len(document)}")
    print(f"Reference scenarios: {len(reference['scenarios'])}")
    print()
    print("Running R1 extraction using local Ollama...", flush=True)

    scenarios = identify_dbms_scenarios(document)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    output_path = OUTPUT_DIR / f"library_r1_extraction_{timestamp}.json"

    result = {
        "benchmark_id": reference["benchmark_id"],
        "source_document": str(INPUT_PATH),
        "extraction_model": "local_ollama",
        "extracted_at_utc": timestamp,
        "reference_scenario_count": len(reference["scenarios"]),
        "extracted_scenario_count": len(scenarios),
        "scenarios": [
            scenario.model_dump(mode="json")
            for scenario in scenarios
        ],
    }

    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Extracted scenarios: {len(scenarios)}")
    print(f"Saved results: {output_path}")

    print("\nExtracted scenarios:")
    for scenario in scenarios:
        print(f"\n{scenario.id}")
        print(f"  Precondition: {scenario.precondition}")
        print(f"  Behavior: {scenario.behavior_under_test}")
        print(f"  Expected: {scenario.expected_result}")


if __name__ == "__main__":
    main()
