import json
from pathlib import Path

from app.dbms_chunking import chunk_document
from app.dbms_scenarios import _extract_dbms_chunk

source = Path("tests/fixtures/external/library_management_r1_input.md")
output = Path("benchmark_results/library_r1_requirement_chunks.json")

document = source.read_text(encoding="utf-8-sig")
chunks = chunk_document(document, max_chars=800, max_context_chars=500)

requirement_ids = [
    "SRS-001", "SRS-005", "SRS-008",
    "SRS-009", "SRS-010", "SRS-013"
]

shared_context = document.split("## Data Requirements", 1)[1]
shared_context = "## Data Requirements\n" + shared_context

results = {}

if output.exists():
    results = json.loads(output.read_text(encoding="utf-8"))

for chunk in chunks:
    matching = [
        req for req in requirement_ids
        if req in chunk.text
    ]

    if len(matching) != 1:
        continue

    req_id = matching[0]

    if req_id in results:
        print(f"Skipping {req_id}: already saved")
        continue

    print(f"\nExtracting {req_id}...", flush=True)

    scenarios = _extract_dbms_chunk(
        text=chunk.text,
        context=shared_context,
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

    print(f"Saved {len(scenarios)} scenarios for {req_id}", flush=True)

print("\n=== EXTRACTION SUMMARY ===")

for req_id in requirement_ids:
    print(f"{req_id}: {len(results.get(req_id, []))} scenarios")

print(f"\nSaved to: {output}")
