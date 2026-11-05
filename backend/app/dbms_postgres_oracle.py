"""Independent PostgreSQL checks against the benchmark's expert assertions.

Only use on reviewed SQL in a disposable PostgreSQL environment.
"""
import psycopg
from app.dbms_postgres_executor import postgres_test_connection


def evaluate_postgres_oracle(test_case, oracle):
    result = {"passed": False, "operation_matched": False,
              "assertions_passed": False, "assertion_results": [], "errors": []}
    try:
        with postgres_test_connection() as conn:
            with conn.cursor() as cur:
                for statement in test_case.setup_sql:
                    cur.execute(statement, prepare=False)
                cur.execute("SAVEPOINT oracle_operation")
                operation_error = None
                try:
                    cur.execute(test_case.test_sql, prepare=False)
                    cur.execute("RELEASE SAVEPOINT oracle_operation")
                except psycopg.Error as exc:
                    operation_error = str(exc)
                    cur.execute("ROLLBACK TO SAVEPOINT oracle_operation")
                    cur.execute("RELEASE SAVEPOINT oracle_operation")

                expected_type = oracle["expected_outcome_type"]
                if expected_type == "error":
                    expected_error = oracle.get("expected_error", "")
                    result["operation_matched"] = bool(operation_error and expected_error and
                        expected_error.lower() in operation_error.lower())
                else:
                    result["operation_matched"] = operation_error is None
                if not result["operation_matched"]:
                    result["errors"].append(f"Operation mismatch: {operation_error!r}")

                assertions = oracle.get("verification_assertions", [])
                for assertion in assertions:
                    try:
                        cur.execute(assertion["query"], prepare=False)
                        rows = cur.fetchall()
                        expected = assertion["expected_scalar"]
                        actual = rows[0][0] if len(rows) == 1 and len(rows[0]) == 1 else rows
                        passed = type(actual) is type(expected) and actual == expected
                        result["assertion_results"].append({
                            "query": assertion["query"], "expected": expected,
                            "actual": actual, "passed": passed})
                    except psycopg.Error as exc:
                        result["assertion_results"].append({
                            "query": assertion["query"], "passed": False, "error": str(exc)})
                result["assertions_passed"] = bool(assertions) and all(
                    item["passed"] for item in result["assertion_results"])
                result["passed"] = result["operation_matched"] and result["assertions_passed"]
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    return result
