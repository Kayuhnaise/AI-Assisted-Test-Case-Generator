from typing import List, Literal

from pydantic import BaseModel, Field


class RequirementInput(BaseModel):
    requirement: str = Field(
        ...,
        min_length=10,
        description="Natural-language software requirement"
    )


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