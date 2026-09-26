import ast
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator


class RequirementInput(BaseModel):
    requirement: str = Field(
        ...,
        min_length=10,
        description="Natural-language software requirement"
    )


class ScenarioInput(BaseModel):
    requirement: str = Field(
        ...,
        min_length=10,
        description="Natural-language software requirement"
    )
    source_code: str = Field(
        ...,
        min_length=1,
        description="Python source code associated with the requirement"
    )

    @field_validator("source_code")
    @classmethod
    def source_must_be_valid_python(cls, source_code: str) -> str:
        try:
            ast.parse(source_code)
        except SyntaxError as exc:
            raise ValueError("source_code must be valid Python") from exc
        return source_code


class Scenario(BaseModel):
    id: str
    category: Literal[
        "positive",
        "negative",
        "boundary",
        "edge"
    ]
    description: str = Field(
        ...,
        description=(
            "The expected behavior or boundary condition this "
            "scenario covers"
        )
    )


class GeneratedScenarios(BaseModel):
    scenarios: List[Scenario] = Field(min_length=1)


class ScenarioResponse(BaseModel):
    requirement: str
    scenarios: List[Scenario]


class TestCase(BaseModel):
    id: str
    scenario_id: str
    title: str
    test_type: Literal[
        "positive",
        "negative",
        "boundary",
        "edge"
    ]
    preconditions: List[str]
    steps: List[str]
    expected_result: str
    pytest_code: str = Field(
        ...,
        description="A single executable pytest test function for this scenario"
    )


class PytestExecutionResult(BaseModel):
    status: Literal["passed", "failed", "error", "timeout"]
    exit_code: int | None
    tests_run: int
    passed: int
    failed: int
    errors: int
    skipped: int
    stdout: str
    stderr: str


class GeneratedTestCases(BaseModel):
    test_cases: List[TestCase]
    
class TestCaseResponse(BaseModel):
    requirement: str
    scenarios: List[Scenario]
    test_cases: List[TestCase]
    pytest_code: str
    pytest_result: PytestExecutionResult