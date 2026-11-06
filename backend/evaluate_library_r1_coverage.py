import csv
import json
from collections import Counter
from pathlib import Path

REFERENCE_PATH = Path(
    "tests/fixtures/external/library_management_r1_reference.json"
)
EXTRACTION_PATH = Path(
    "benchmark_results/library_r1_requirement_chunks.json"
)
OUTPUT_DIR = Path("benchmark_results")

# Manually reviewed semantic matches.
# These map reference scenario IDs to extracted scenario IDs.
MATCHES = {
    "REF-001": "reg_pos_001",
    "REF-002": "reg_neg_003",
    "REF-003": "reg_neg_005",
    "REF-004": "reg_neg_001",
    "REF-005": "reg_neg_006",
    "REF-006": "srs005_pos_1",
    "REF-007": "srs005_neg_4",
    "REF-008": None,
    "REF-009": "srs005_neg_1",
    "REF-010": "srs005_neg_3",
    "REF-011": "copies_positive",
    "REF-012": "copies_negative",
    "REF-013": "srs009_pos_1",
    "REF-014": "srs009_neg_2",
    "REF-015": "srs010_pos_01",
    "REF-016": "srs010_neg_02",
    "REF-017": "srs010_neg_03",
    "REF-018": "srs013_01",
    "REF-019": "srs013_04",
}

def main():
    references = json.loads(
        REFERENCE_PATH.read_text(encoding="utf-8-sig")
    )["scenarios"]

    extracted = json.loads(
        EXTRACTION_PATH.read_text(encoding="utf-8-sig")
    )

    extracted_by_requirement = {
        requirement_id: {
            scenario["id"]: scenario
            for scenario in scenarios
        }
        for requirement_id, scenarios in extracted.items()
    }

    rows = []

    for reference in references:
        ref_id = reference["id"]
        requirement_id = reference["requirement_id"]
        extracted_id = MATCHES.get(ref_id)

        matched = (
            extracted_id is not None
            and extracted_id in extracted_by_requirement.get(
                requirement_id, {}
            )
        )

        rows.append({
            "reference_id": ref_id,
            "requirement_id": requirement_id,
            "reference_behavior": reference["behavior_under_test"],
            "reference_expected": reference["expected_result"],
            "matched": matched,
            "extracted_id": extracted_id or "",
            "extracted_behavior": (
                extracted_by_requirement[requirement_id][extracted_id][
                    "behavior_under_test"
                ]
                if matched else ""
            ),
            "extracted_expected": (
                extracted_by_requirement[requirement_id][extracted_id][
                    "expected_result"
                ]
                if matched else ""
            ),
        })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUTPUT_DIR / "library_r1_traceability.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    matched = sum(row["matched"] for row in rows)

    print("=== R1 REFERENCE COVERAGE ===")
    print(f"Matched: {matched}/{total}")
    print(f"Recall: {matched / total:.1%}")

    print("\n=== COVERAGE BY REQUIREMENT ===")

    for requirement_id in sorted(set(
        row["requirement_id"] for row in rows
    )):
        subset = [
            row for row in rows
            if row["requirement_id"] == requirement_id
        ]
        count = sum(row["matched"] for row in subset)
        print(f"{requirement_id}: {count}/{len(subset)}")

    print("\n=== UNMATCHED REFERENCES ===")

    for row in rows:
        if not row["matched"]:
            print(
                f"{row['reference_id']}: "
                f"{row['reference_behavior']}"
            )

    print(f"\nTraceability matrix saved: {csv_path}")


if __name__ == "__main__":
    main()
