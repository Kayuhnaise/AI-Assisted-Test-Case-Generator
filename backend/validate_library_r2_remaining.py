import json
import os
from pathlib import Path

from dotenv import load_dotenv

from app.models import DBMSSQLTestCase
from app.dbms_postgres_executor import validate_postgres_sql_test

load_dotenv(dotenv_path=Path(".env"))

source = Path("benchmark_results/library_r2_claude_generated_10.json")
output = Path("benchmark_results/library_r2_postgres_remaining_2.json")

data = json.loads(source.read_text(encoding="utf-8"))

target_ids = {
    "SRS-010-dbms_4",
    "SRS-013-dbms_4",
}

results = []

for item in data["test_cases"]:
    if item["scenario_id"] not in target_ids:
        continue

    case = DBMSSQLTestCase.model_validate(item)

    # Both reviewed test cases contain two SQL statements.
    # Wrap them in one PostgreSQL statement.
    sql = case.test_sql.strip().rstrip(";")

    case = case.model_copy(
        update={
            "test_sql": "DO $dbtestgen$ BEGIN\n"
            + sql
            + ";\nEND $dbtestgen$;"
        }
    )

    print(f"Testing {case.id}...", flush=True)

    result = validate_postgres_sql_test(
        case,
        trusted_sql=True,
        database_url=os.environ["DBTESTGEN_POSTGRES_URL"],
    )

    results.append(result.model_dump(mode="json"))

    print(f"  Status: {result.status}")

    for error in result.errors:
        print(f"  {error}")

output.write_text(
    json.dumps(results, indent=2) + "\n",
    encoding="utf-8",
)

print("\n=== REMAINING TESTS ===")
print("Executed:", len(results))
print("Passed:", sum(r["status"] == "passed" for r in results))
print("Failed:", sum(r["status"] == "failed" for r in results))
print("Errors:", sum(r["status"] == "error" for r in results))
print("Saved to:", output)
