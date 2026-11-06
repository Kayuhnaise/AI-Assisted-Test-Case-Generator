"""Evaluate Claude R1 on the external Library Management SRS."""

import json
from pathlib import Path

from dotenv import load_dotenv

from app.dbms_chunking import chunk_document
from app.dbms_scenarios_claude import identify_dbms_scenarios_claude

load_dotenv(dotenv_path=Path(".env"))

source = Path("tests/fixtures/external/library_management_r1_input.md")
output = Path("benchmark_results/library_r1_claude_extraction_improved.json")

document = source.read_text(encoding="utf-8-sig")

chunks = chunk_document(
    document,
    max_chars=800,
    max_context_chars=500,
)

requirement_ids = [
    "SRS-001",
    "SRS-005",
    "SRS-008",
    "SRS-009",
    "SRS-010",
    "SRS-013",
]

shared_context = (
    "## Data Requirements\n"
    + document.split("## Data Requirements", 1)[1]
)

results = {}

if output.exists():
    results = json.loads(output.read_text(encoding="utf-8"))

for chunk in chunks:
    matching = [
        req_id
        for req_id in requirement_ids
        if req_id in chunk.text
    ]

    if len(matching) != 1:
        continue

    req_id = matching[0]

    if req_id in results:
        print(f"Skipping {req_id}: already saved")
        continue

    print(f"\nClaude extracting {req_id}...", flush=True)

    requirement_input = (
        f"Shared document context:\n{shared_context}\n\n"
        f"Requirements to analyze:\n{chunk.text}"
    )

    scenarios = identify_dbms_scenarios_claude(
        requirement_input
    )

    results[req_id] = [
        scenario.model_dump(mode="json")
        for scenario in scenarios
    ]

    output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"Saved {len(scenarios)} scenarios for {req_id}",
        flush=True,
    )

print("\n=== CLAUDE R1 EXTRACTION SUMMARY ===")

total = 0

for req_id in requirement_ids:
    count = len(results.get(req_id, []))
    total += count
    print(f"{req_id}: {count} scenarios")

print(f"\nTotal extracted: {total}")
print(f"Saved to: {output}")
