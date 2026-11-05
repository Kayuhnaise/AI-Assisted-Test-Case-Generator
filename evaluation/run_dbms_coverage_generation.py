"""Analyze an LCOV report and request coverage-guided DBMS scenarios.

Run from the repository root with the API and Ollama available:

    .venv/bin/python evaluation/run_dbms_coverage_generation.py \
        --requirements README_DB.md
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def post_json(base_url: str, path: str, payload: dict[str, object]) -> object:
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code} from {path}:\n{body}", file=sys.stderr)
        raise SystemExit(1) from error
    except TimeoutError as error:
        print(
            f"Timed out waiting for {path}; the API may still be waiting on Ollama.",
            file=sys.stderr,
        )
        raise SystemExit(1) from error
    except URLError as error:
        print(f"Could not reach {base_url}: {error.reason}", file=sys.stderr)
        raise SystemExit(1) from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lcov",
        type=Path,
        default=REPOSITORY_ROOT / "postgres-coverage.info",
        help="Path to the LCOV report (default: postgres-coverage.info)",
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        required=True,
        help="Path to the DBMS requirement document",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DBMS_API_BASE_URL", "http://127.0.0.1:8002"),
        help="API base URL (default: DBMS_API_BASE_URL or localhost:8002)",
    )
    args = parser.parse_args()

    try:
        lcov_report = args.lcov.read_text(encoding="utf-8")
        requirement_document = args.requirements.read_text(encoding="utf-8")
    except OSError as error:
        parser.error(str(error))

    print(f"Analyzing {args.lcov} against {args.base_url} ...")
    coverage_report = post_json(
        args.base_url,
        "/dbms/coverage/analyze",
        {"lcov_report": lcov_report},
    )
    if not isinstance(coverage_report, dict):
        raise SystemExit("Coverage analysis returned an unexpected response.")

    hints = coverage_report.get("feature_hints", [])
    print(
        f"Analyzed {coverage_report.get('files_analyzed', 0)} source files; "
        f"found {len(hints)} uncovered feature hints."
    )
    print("Requesting coverage-guided scenarios ...")
    result = post_json(
        args.base_url,
        "/dbms/coverage/generate",
        {
            "requirement_document": requirement_document,
            "coverage_report": coverage_report,
        },
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
