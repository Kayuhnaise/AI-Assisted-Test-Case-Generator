import ast
import ollama
from pydantic import ValidationError

from app.models import (
    GeneratedScenarios,
    GeneratedTestCases,
    Scenario,
    TestCase,
)
from app.prompts import (
    SCENARIO_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_scenario_prompt,
)


MODEL_NAME = "qwen3:4b"
MAX_SCENARIO_ATTEMPTS = 3


def function_parameter_names(source_code: str) -> set[str]:
    """Return every parameter name of every function in the source."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source_code)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            for arg in (
                arguments.posonlyargs
                + arguments.args
                + arguments.kwonlyargs
            ):
                names.add(arg.arg)
            if arguments.vararg:
                names.add(arguments.vararg.arg)
            if arguments.kwarg:
                names.add(arguments.kwarg.arg)
    return names


def uses_pytest_raises(pytest_code: str) -> bool:
    """Return True when the code calls pytest.raises."""
    for node in ast.walk(ast.parse(pytest_code)):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "raises"
            and isinstance(node.value, ast.Name)
            and node.value.id == "pytest"
        ):
            return True
    return False


def validate_scenarios(
    scenarios: list[Scenario],
    source_code: str,
) -> None:
    """
    Structural checks on the scenario intermediate representation.

    Requirement alignment (requirement_clause) is deliberately not
    enforced here: it is measured during evaluation instead.
    """
    scenario_ids = [scenario.id for scenario in scenarios]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("Identified scenario IDs must be unique")

    parameters = function_parameter_names(source_code)
    for scenario in scenarios:
        unknown = sorted(
            {argument.name for argument in scenario.example_inputs}
            - parameters
        )
        if unknown:
            raise ValueError(
                f"Scenario {scenario.id} uses example_inputs names "
                f"{unknown} that are not parameters of any function in "
                f"the source code (available: {sorted(parameters)})"
            )

def ensure_pytest_import(pytest_code: str) -> str:
    """
    Add a pytest import when generated test code uses pytest
    but does not import it.
    """
    parsed = ast.parse(pytest_code)

    uses_pytest = any(
        isinstance(node, ast.Name) and node.id == "pytest"
        for node in ast.walk(parsed)
    )

    imports_pytest = any(
        (
            isinstance(node, ast.Import)
            and any(alias.name == "pytest" for alias in node.names)
        )
        or (
            isinstance(node, ast.ImportFrom)
            and node.module == "pytest"
        )
        for node in parsed.body
    )

    if uses_pytest and not imports_pytest:
        return f"import pytest\n\n{pytest_code}"

    return pytest_code


def generate_test_cases(
    requirement: str,
    source_code: str,
    scenarios: list[Scenario],
) -> tuple[list[TestCase], str]:
    """
    Generate scenario-traceable test cases and a runnable pytest module.
    """

    if not scenarios:
        raise ValueError("At least one identified scenario is required")

    # Scenarios whose outcome the requirement leaves undefined are
    # reported but not tested, so no expected result is invented.
    scenarios = [
        scenario for scenario in scenarios
        if scenario.expected_outcome_kind != "unspecified"
    ]
    if not scenarios:
        return [], f"{source_code.rstrip()}\n"

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": build_generation_prompt(
                    requirement, source_code, scenarios
                )
            }
        ],
        format=GeneratedTestCases.model_json_schema(),
        options={
            "temperature": 0.2
        }
    )

    generated = GeneratedTestCases.model_validate_json(
        response.message.content
    )

    scenario_by_id = {scenario.id: scenario for scenario in scenarios}
    case_by_scenario_id = {
        test_case.scenario_id: test_case for test_case in generated.test_cases
    }
    if len(scenario_by_id) != len(scenarios):
        raise ValueError("Identified scenario IDs must be unique")
    if len(case_by_scenario_id) != len(generated.test_cases):
        raise ValueError("Each generated test case must cover a unique scenario")
    if set(case_by_scenario_id) != set(scenario_by_id):
        raise ValueError("Generated test cases must cover every identified scenario")

    test_functions = []
    for test_case in generated.test_cases:
        scenario = scenario_by_id[test_case.scenario_id]

        test_case.pytest_code = ensure_pytest_import(
            test_case.pytest_code
        )
        if test_case.test_type != scenario.category:
            test_case.test_type = scenario.category

        try:
            parsed_test = ast.parse(test_case.pytest_code)
        except SyntaxError as exc:
            raise ValueError(
                f"Test case {test_case.id} contains invalid Python"
            ) from exc

        if (
            scenario.expected_outcome_kind == "error"
            and not uses_pytest_raises(test_case.pytest_code)
        ):
            raise ValueError(
                f"Test case {test_case.id} must use pytest.raises because "
                f"scenario {scenario.id} expects an error"
            )

        functions = [
            node for node in parsed_test.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        allowed_nodes = (
            ast.FunctionDef,
            ast.Import,
            ast.ImportFrom,
        )
        if (
            len(functions) != 1
            or len(functions) != sum(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                for node in parsed_test.body
            )
            or any(not isinstance(node, allowed_nodes) for node in parsed_test.body)
        ):
            raise ValueError(
                f"Test case {test_case.id} must contain exactly one "
                "top-level pytest test function"
            )
        test_functions.append(test_case.pytest_code.strip())

    pytest_code = (
        f"{source_code.rstrip()}\n\n"
        + "\n\n".join(test_functions)
        + "\n"
    )
    try:
        ast.parse(pytest_code)
    except SyntaxError as exc:
        raise ValueError("Generated pytest module contains invalid Python") from exc

    return generated.test_cases, pytest_code


def identify_scenarios(requirement: str, source_code: str) -> list[Scenario]:
    """
    Identify distinct testing scenarios (positive, negative, boundary,
    edge) from a natural-language requirement and its associated
    Python source code using a local Ollama model.

    The output is a structured intermediate representation. Responses
    that fail schema or structural validation are retried with the
    validation error as feedback.
    """

    messages = [
        {
            "role": "system",
            "content": SCENARIO_SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": build_scenario_prompt(requirement, source_code)
        }
    ]
    last_error: Exception | None = None

    for attempt in range(MAX_SCENARIO_ATTEMPTS):
        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            format=GeneratedScenarios.model_json_schema(),
            options={
                "temperature": 0.2
            }
        )
        content = response.message.content

        try:
            generated = GeneratedScenarios.model_validate_json(content)
            validate_scenarios(generated.scenarios, source_code)
            return generated.scenarios
        except (ValidationError, ValueError) as exc:
            last_error = exc
            if attempt == MAX_SCENARIO_ATTEMPTS - 1:
                break
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": (
                    "Your previous scenario response failed validation.\n\n"
                    f"Validation error:\n{exc}\n\n"
                    "Return the complete corrected JSON object. Fill every "
                    "field of every scenario, and use only parameter names "
                    "from the source code in example_inputs."
                ),
            })

    raise ValueError(
        "Scenario identification failed after "
        f"{MAX_SCENARIO_ATTEMPTS} attempts. "
        f"Last validation error: {last_error}"
    ) from last_error
