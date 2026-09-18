import ollama

from app.models import GeneratedScenarios, GeneratedTestCases, Scenario, TestCase
from app.prompts import (
    SCENARIO_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_scenario_prompt,
)


MODEL_NAME = "qwen3:4b"


def generate_test_cases(requirement: str) -> list[TestCase]:
    """
    Generate structured software test cases from a natural-language
    requirement using a local Ollama model.
    """

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": build_generation_prompt(requirement)
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

    return generated.test_cases


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