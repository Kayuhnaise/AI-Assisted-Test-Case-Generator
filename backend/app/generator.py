import ast
import ollama

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
        if test_case.test_type != scenario.category:
            raise ValueError(
                f"Test case {test_case.id} category does not match "
                f"scenario {scenario.id}"
            )

        try:
            parsed_test = ast.parse(test_case.pytest_code)
        except SyntaxError as exc:
            raise ValueError(
                f"Test case {test_case.id} contains invalid Python"
            ) from exc

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
    """

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": SCENARIO_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": build_scenario_prompt(requirement, source_code)
            }
        ],
        format=GeneratedScenarios.model_json_schema(),
        options={
            "temperature": 0.2
        }
    )

    generated = GeneratedScenarios.model_validate_json(
        response.message.content
    )

    return generated.scenarios