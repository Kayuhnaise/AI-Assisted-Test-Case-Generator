from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.generator import (
    MAX_SCENARIO_ATTEMPTS,
    function_parameter_names,
    generate_test_cases,
    identify_scenarios,
)
from app.models import (
    DBMSScenario,
    GeneratedScenarios,
    GeneratedTestCases,
    Scenario,
    ScenarioCore,
    TestCase as GeneratedCase,
)


SOURCE = (
    "def divide(numerator: float, denominator: float) -> float:\n"
    "    if denominator == 0:\n"
    "        raise ValueError('Cannot divide by zero')\n"
    "    return numerator / denominator\n"
)
REQUIREMENT = (
    "The system shall compute the result of dividing two numbers and "
    "shall reject division by zero."
)


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


def _scenario(**overrides) -> Scenario:
    fields = {
        "id": "neg_1",
        "category": "negative",
        "requirement_clause": "shall reject division by zero",
        "precondition": "denominator is exactly 0",
        "behavior_under_test": "call divide",
        "expected_result": "raises ValueError",
        "expected_outcome_kind": "error",
        "example_inputs": [
            {"name": "numerator", "value": 10},
            {"name": "denominator", "value": 0},
        ],
    }
    fields.update(overrides)
    return Scenario(**fields)


def _case(scenario_id: str, pytest_code: str, test_type="negative"):
    return GeneratedCase(
        id=f"tc_{scenario_id}",
        scenario_id=scenario_id,
        title="t",
        test_type=test_type,
        preconditions=[],
        steps=[],
        expected_result="r",
        pytest_code=pytest_code,
    )


def test_python_and_dbms_scenarios_share_core_schema():
    assert issubclass(Scenario, ScenarioCore)
    assert issubclass(DBMSScenario, ScenarioCore)
    core_fields = set(ScenarioCore.model_fields)
    assert core_fields == set(DBMSScenario.model_fields)
    assert core_fields < set(Scenario.model_fields)
    assert "description" not in Scenario.model_fields


def test_function_parameter_names_reads_all_functions():
    assert function_parameter_names(SOURCE) == {"numerator", "denominator"}


def test_identify_scenarios_retries_on_unknown_parameter_name():
    bad = _scenario(example_inputs=[{"name": "divisor", "value": 0}])
    good = _scenario()
    responses = [
        _response(GeneratedScenarios(scenarios=[bad]).model_dump_json()),
        _response(GeneratedScenarios(scenarios=[good]).model_dump_json()),
    ]

    with patch("app.generator.ollama.chat", side_effect=responses) as chat:
        scenarios = identify_scenarios(REQUIREMENT, SOURCE)

    assert scenarios == [good]
    assert chat.call_count == 2
    feedback = chat.call_args_list[1].kwargs["messages"][-1]["content"]
    assert "divisor" in feedback


def test_identify_scenarios_retries_on_schema_violation_then_fails():
    invalid = '{"scenarios": [{"id": "x", "category": "positive"}]}'
    with patch(
        "app.generator.ollama.chat",
        return_value=_response(invalid),
    ) as chat:
        with pytest.raises(ValueError, match="failed after"):
            identify_scenarios(REQUIREMENT, SOURCE)

    assert chat.call_count == MAX_SCENARIO_ATTEMPTS


def test_identify_scenarios_does_not_enforce_requirement_alignment():
    misquoted = _scenario(requirement_clause="never divide anything")
    with patch(
        "app.generator.ollama.chat",
        return_value=_response(
            GeneratedScenarios(scenarios=[misquoted]).model_dump_json()
        ),
    ) as chat:
        scenarios = identify_scenarios(REQUIREMENT, SOURCE)

    assert scenarios == [misquoted]
    assert chat.call_count == 1


def test_error_scenario_requires_pytest_raises():
    case = _case(
        "neg_1",
        "def test_neg_1():\n    assert divide(10, 0) is None\n",
    )
    with patch(
        "app.generator.ollama.chat",
        return_value=_response(
            GeneratedTestCases(test_cases=[case]).model_dump_json()
        ),
    ):
        with pytest.raises(ValueError, match="pytest.raises"):
            generate_test_cases(REQUIREMENT, SOURCE, [_scenario()])


def test_error_scenario_with_pytest_raises_is_accepted():
    case = _case(
        "neg_1",
        "def test_neg_1():\n"
        "    with pytest.raises(ValueError):\n"
        "        divide(10, 0)\n",
    )
    with patch(
        "app.generator.ollama.chat",
        return_value=_response(
            GeneratedTestCases(test_cases=[case]).model_dump_json()
        ),
    ):
        test_cases, pytest_code = generate_test_cases(
            REQUIREMENT, SOURCE, [_scenario()]
        )

    assert [item.scenario_id for item in test_cases] == ["neg_1"]
    assert "import pytest" in pytest_code


def test_unspecified_scenarios_are_not_sent_for_test_generation():
    unspecified = _scenario(
        id="edge_1",
        category="edge",
        expected_outcome_kind="unspecified",
        expected_result="The requirement does not define NaN handling.",
        example_inputs=[],
    )
    case = _case(
        "neg_1",
        "import pytest\n\n"
        "def test_neg_1():\n"
        "    with pytest.raises(ValueError):\n"
        "        divide(10, 0)\n",
    )
    with patch(
        "app.generator.ollama.chat",
        return_value=_response(
            GeneratedTestCases(test_cases=[case]).model_dump_json()
        ),
    ) as chat:
        test_cases, _ = generate_test_cases(
            REQUIREMENT, SOURCE, [_scenario(), unspecified]
        )

    assert [item.scenario_id for item in test_cases] == ["neg_1"]
    prompt = chat.call_args.kwargs["messages"][1]["content"]
    assert "edge_1" not in prompt


def test_only_unspecified_scenarios_skip_the_model():
    unspecified = _scenario(expected_outcome_kind="unspecified")
    with patch("app.generator.ollama.chat") as chat:
        test_cases, pytest_code = generate_test_cases(
            REQUIREMENT, SOURCE, [unspecified]
        )

    chat.assert_not_called()
    assert test_cases == []
    assert pytest_code.startswith("def divide")
