import ollama

from app.models import GeneratedTestCases, TestCase
from app.prompts import SYSTEM_PROMPT, build_generation_prompt


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