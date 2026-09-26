import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from app.models import PytestExecutionResult


TEST_TIMEOUT_SECONDS = 15
OUTPUT_LIMIT_CHARACTERS = 10_000


def _truncate_output(output: str) -> str:
    if len(output) <= OUTPUT_LIMIT_CHARACTERS:
        return output
    return output[:OUTPUT_LIMIT_CHARACTERS] + "\n... output truncated ..."


def run_pytest(pytest_code: str) -> PytestExecutionResult:
    """Run a generated pytest module in a temporary directory.

    This is intended for trusted, local development inputs only. A subprocess
    timeout is not a security sandbox for arbitrary Python source code.
    """
    with tempfile.TemporaryDirectory(prefix="generated-pytest-") as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test_generated.py"
        report_file = temp_path / "pytest-report.xml"
        test_file.write_text(pytest_code, encoding="utf-8")

        env = os.environ.copy()
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            f"--junitxml={report_file}",
            str(test_file),
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=temp_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            return PytestExecutionResult(
                status="timeout",
                exit_code=None,
                tests_run=0,
                passed=0,
                failed=0,
                errors=0,
                skipped=0,
                stdout=_truncate_output(stdout),
                stderr=_truncate_output(stderr),
            )
        except OSError as exc:
            return PytestExecutionResult(
                status="error",
                exit_code=None,
                tests_run=0,
                passed=0,
                failed=0,
                errors=1,
                skipped=0,
                stdout="",
                stderr=str(exc),
            )

        tests_run = passed = failed = errors = skipped = 0
        if report_file.exists():
            try:
                report = ET.parse(report_file).getroot()
                test_cases = report.findall(".//testcase")
                tests_run = len(test_cases)
                for test_case in test_cases:
                    if test_case.find("failure") is not None:
                        failed += 1
                    elif test_case.find("error") is not None:
                        errors += 1
                    elif test_case.find("skipped") is not None:
                        skipped += 1
                passed = tests_run - failed - errors - skipped
            except ET.ParseError:
                errors = 1

        if completed.returncode == 0:
            status = "passed"
        elif failed:
            status = "failed"
        else:
            status = "error"

        return PytestExecutionResult(
            status=status,
            exit_code=completed.returncode,
            tests_run=tests_run,
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            stdout=_truncate_output(completed.stdout),
            stderr=_truncate_output(completed.stderr),
        )