from collections import defaultdict
from dataclasses import dataclass, field

from app.models import (
    DBMSFeatureHint,
    DBMSCoverageMetric,
    DBMSCoverageModule,
    DBMSCoverageReport,
)


_MODULE_RULES = {
    "parser": (
        ("parser", "gram.y", "scan.l"),
        "SQL parsing and syntax",
    ),
    "analysis": (
        ("analyze", "analyzer", "parse_expr", "parse_func"),
        "Name resolution and semantic analysis",
    ),
    "optimizer": (
        ("optimizer", "plan", "path", "costsize"),
        "Query planning and optimization",
    ),
    "executor": (
        ("executor", "execnodes", "node"),
        "Query execution",
    ),
    "storage": (
        ("storage", "heapam", "nbtree", "bufmgr", "tableam"),
        "Table, index, and constraint operations",
    ),
    "transactions": (
        ("transam", "xact", "procarray", "twophase", "tcop"),
        "Transactions and statement execution",
    ),
}


@dataclass
class _FileCoverage:
    lines: dict[int, int] = field(default_factory=dict)
    branches: dict[tuple[str, str, str], int] = field(default_factory=dict)
    functions: dict[str, int] = field(default_factory=dict)


def analyze_lcov_report(report: str) -> DBMSCoverageReport:
    """Parse LCOV line, branch, and function counters into feature hints."""
    files: dict[str, _FileCoverage] = {}
    source: str | None = None
    current: _FileCoverage | None = None

    for line_number, raw_line in enumerate(report.splitlines(), 1):
        if raw_line.startswith("SF:"):
            source = raw_line[3:].strip()
            if not source:
                raise ValueError(f"LCOV line {line_number} has an empty SF path")
            current = files.setdefault(source, _FileCoverage())
        elif raw_line == "end_of_record":
            source = None
            current = None
        elif raw_line.startswith(("DA:", "BRDA:", "FNDA:")):
            if current is None:
                raise ValueError(
                    f"LCOV line {line_number} contains counters outside a record"
                )
            try:
                if raw_line.startswith("DA:"):
                    parts = raw_line[3:].split(",")
                    current.lines[int(parts[0])] = int(parts[1])
                elif raw_line.startswith("BRDA:"):
                    parts = raw_line[5:].split(",")
                    current.branches[(parts[0], parts[1], parts[2])] = (
                        0 if parts[3] == "-" else int(parts[3])
                    )
                else:
                    count, name = raw_line[5:].split(",", 1)
                    current.functions[name] = int(count)
            except (IndexError, ValueError) as exc:
                raise ValueError(
                    f"Malformed LCOV counter at line {line_number}"
                ) from exc

    if not files:
        raise ValueError("LCOV report contains no source-file records")

    module_files: dict[str, list[tuple[str, _FileCoverage]]] = defaultdict(list)
    for path, coverage in files.items():
        module = _classify_module(path)
        if module is not None:
            module_files[module].append((path, coverage))

    modules: list[DBMSCoverageModule] = []
    feature_hints: list[DBMSFeatureHint] = []
    for module_name, module_file_records in sorted(module_files.items()):
        line_counts = _count_lines(module_file_records)
        branch_counts = _count_branches(module_file_records)
        function_counts = _count_functions(module_file_records)
        uncovered = sorted(
            path
            for path, coverage in module_file_records
            if (
                any(count == 0 for count in coverage.lines.values())
                or any(count == 0 for count in coverage.branches.values())
                or any(count == 0 for count in coverage.functions.values())
            )
        )
        feature = _MODULE_RULES[module_name][1]
        modules.append(
            DBMSCoverageModule(
                name=module_name,
                line_coverage=_metric(*line_counts),
                branch_coverage=_metric(*branch_counts),
                function_coverage=_metric(*function_counts),
                uncovered_files=uncovered,
                feature_hints=[feature] if uncovered else [],
            )
        )
        if uncovered:
            feature_hints.append(
                DBMSFeatureHint(
                    feature=feature,
                    module=module_name,
                    uncovered_files=uncovered,
                )
            )

    return DBMSCoverageReport(
        files_analyzed=len(files),
        line_coverage=_metric(*_count_lines(list(files.items()))),
        branch_coverage=_metric(*_count_branches(list(files.items()))),
        function_coverage=_metric(*_count_functions(list(files.items()))),
        modules=modules,
        feature_hints=feature_hints,
    )


def _classify_module(path: str) -> str | None:
    normalized = path.lower().replace("\\", "/")
    for module, (markers, _) in _MODULE_RULES.items():
        if any(marker in normalized for marker in markers):
            return module
    return None


def _count_lines(
    file_records: list[tuple[str, _FileCoverage]],
) -> tuple[int, int]:
    counters = [
        count
        for _, coverage in file_records
        for count in coverage.lines.values()
    ]
    return sum(count > 0 for count in counters), len(counters)


def _count_branches(
    file_records: list[tuple[str, _FileCoverage]],
) -> tuple[int, int]:
    counters = [
        count
        for _, coverage in file_records
        for count in coverage.branches.values()
    ]
    return sum(count > 0 for count in counters), len(counters)


def _count_functions(
    file_records: list[tuple[str, _FileCoverage]],
) -> tuple[int, int]:
    counters = [
        count
        for _, coverage in file_records
        for count in coverage.functions.values()
    ]
    return sum(count > 0 for count in counters), len(counters)


def _metric(covered: int, total: int) -> DBMSCoverageMetric:
    return DBMSCoverageMetric(
        covered=covered,
        total=total,
        percentage=100 * covered / total if total else 0.0,
    )
