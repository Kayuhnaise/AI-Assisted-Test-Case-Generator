"""Sanity checks for the structured reference benchmark in evaluation/reference."""

import ast
import json
from pathlib import Path

import pytest

from app.generator import validate_scenarios
from app.models import Scenario
from app.scenario_coverage import is_requirement_aligned


REFERENCE_DIR = (
    Path(__file__).resolve().parents[2] / "evaluation" / "reference"
)
REFERENCE_FILES = sorted(REFERENCE_DIR.glob("*.json"))


def _load(path: Path) -> tuple[dict, list[Scenario]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    scenarios = [
        Scenario.model_validate(item)
        for item in document["reference_scenarios"]
    ]
    return document, scenarios


def test_reference_benchmark_has_21_scenarios():
    assert len(REFERENCE_FILES) == 4
    assert sum(len(_load(path)[1]) for path in REFERENCE_FILES) == 21


@pytest.mark.parametrize("path", REFERENCE_FILES, ids=lambda p: p.stem)
def test_reference_scenarios_are_structurally_valid_and_aligned(path):
    document, scenarios = _load(path)
    validate_scenarios(scenarios, document["source_code"])
    for scenario in scenarios:
        assert is_requirement_aligned(document["requirement"], scenario), (
            f"{path.stem}/{scenario.id} requirement_clause is not a "
            "verbatim quote of the requirement"
        )


@pytest.mark.parametrize("path", REFERENCE_FILES, ids=lambda p: p.stem)
def test_reference_outcome_kinds_match_the_source_code(path):
    document, scenarios = _load(path)
    namespace: dict = {}
    exec(compile(document["source_code"], path.name, "exec"), namespace)
    function_names = [
        node.name for node in ast.parse(document["source_code"]).body
        if isinstance(node, ast.FunctionDef)
    ]
    assert len(function_names) == 1
    function = namespace[function_names[0]]

    for scenario in scenarios:
        if scenario.expected_outcome_kind == "unspecified":
            continue
        kwargs = {item.name: item.value for item in scenario.example_inputs}
        if scenario.expected_outcome_kind == "error":
            with pytest.raises(Exception):
                function(**kwargs)
        else:
            function(**kwargs)
