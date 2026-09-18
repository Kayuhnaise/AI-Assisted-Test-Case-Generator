from typing import List, Literal

from pydantic import BaseModel, Field


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
    scenarios: List[Scenario]


class ScenarioResponse(BaseModel):
    requirement: str
    scenarios: List[Scenario]


class TestCase(BaseModel):
    id: str
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

class GeneratedTestCases(BaseModel):
    test_cases: List[TestCase]
    
class TestCaseResponse(BaseModel):
    requirement: str
    test_cases: List[TestCase]