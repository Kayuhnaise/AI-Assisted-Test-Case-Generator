import json
from pathlib import Path

from dotenv import load_dotenv

from app.dbms_sql_generator import generate_dbms_sql_tests
from app.models import DBMSScenario

load_dotenv(dotenv_path=Path(".env"))

requirements_path = Path(
    "tests/fixtures/external/library_management_r1_input.md"
)
scenarios_path = Path(
    "benchmark_results/library_r2_claude_selected_10.json"
)
output_path = Path(
    "benchmark_results/library_r2_claude_generated_10.json"
)

requirement_document = requirements_path.read_text(
    encoding="utf-8-sig"
)
selected_data = json.loads(
    scenarios_path.read_text(encoding="utf-8")
)

assert len(selected_data) == 10

if not output_path.exists():
    raise RuntimeError(
        "Expected the saved first batch, but the output file is missing."
    )

result = json.loads(output_path.read_text(encoding="utf-8"))

if result.get("completed_batches") != [1]:
    raise RuntimeError(
        "Unexpected batch state. Inspect the saved results before continuing."
    )

if len(result.get("test_cases", [])) != 5:
    raise RuntimeError(
        "Expected exactly five previously generated SQL tests."
    )

# Resume from the five completed scenarios.
remaining_batches = [
    selected_data[5:7],
    selected_data[7:9],
    selected_data[9:10],
]

for batch_number, batch_data in enumerate(
    remaining_batches,
    start=2,
):
    batch_ids = [item["id"] for item in batch_data]

    existing_ids = {
        case["scenario_id"]
        for case in result["test_cases"]
    }

    if all(scenario_id in existing_ids for scenario_id in batch_ids):
        print(f"Skipping completed batch {batch_number}")
        continue

    if any(scenario_id in existing_ids for scenario_id in batch_ids):
        raise RuntimeError(
            f"Batch {batch_number} is partially saved. "
            "Inspect the output before retrying."
        )

    print(
        f"Generating batch {batch_number}: "
        f"{len(batch_data)} scenarios...",
        flush=True,
    )

    scenarios = [
        DBMSScenario.model_validate(item)
        for item in batch_data
    ]

    test_cases = generate_dbms_sql_tests(
        requirement_document=requirement_document,
        scenarios=scenarios,
        dialect="postgresql",
    )

    generated_ids = {case.scenario_id for case in test_cases}

    if generated_ids != set(batch_ids):
        raise RuntimeError(
            f"Generated scenario IDs do not match batch {batch_number}. "
            f"Expected {batch_ids}; received {sorted(generated_ids)}"
        )

    result["test_cases"].extend(
        case.model_dump(mode="json")
        for case in test_cases
    )

    result["completed_batches"].append(batch_number)

    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"Saved batch {batch_number}: "
        f"{len(test_cases)} SQL tests",
        flush=True,
    )

print("\n=== R2 GENERATION SUMMARY ===")
print(f"Total SQL tests: {len(result['test_cases'])}")
print(f"Completed batches: {result['completed_batches']}")
print(f"Saved to: {output_path}")
