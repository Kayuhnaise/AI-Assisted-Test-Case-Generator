from __future__ import annotations

import ast
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


class DBMSRequirementInput(BaseModel):
    requirement_document: str = Field(
        ...,
        min_length=1,
        description="Plain-text or Markdown DBMS requirement document",
    )


class DBMSScenario(BaseModel):
    id: str = Field(min_length=1)
    category: Literal["positive", "negative", "boundary", "edge"]
    precondition: str = Field(min_length=1)
    behavior_under_test: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)


class GeneratedDBMSScenarios(BaseModel):
    scenarios: List[DBMSScenario] = Field(min_length=1)


class DBMSScenarioResponse(BaseModel):
    requirement_document: str
    scenarios: List[DBMSScenario]


class DBMSCoverageRequest(BaseModel):
    expert_scenarios: List[DBMSScenario] = Field(min_length=1)
    extracted_scenarios: List[DBMSScenario]

    @model_validator(mode="after")
    def scenario_ids_must_be_unique(self) -> DBMSCoverageRequest:
        expert_ids = [scenario.id for scenario in self.expert_scenarios]
        extracted_ids = [scenario.id for scenario in self.extracted_scenarios]
        if len(set(expert_ids)) != len(expert_ids):
            raise ValueError("Expert scenario IDs must be unique")
        if len(set(extracted_ids)) != len(extracted_ids):
            raise ValueError("Extracted scenario IDs must be unique")
        return self


class ScenarioPairJudgment(BaseModel):
    expert_scenario_id: str
    extracted_scenario_id: str
    precondition_matches: bool
    behavior_matches: bool
    expected_result_matches: bool


class ScenarioPairJudgments(BaseModel):
    judgments: List[ScenarioPairJudgment]


class DBMSCoverageMatch(BaseModel):
    expert_scenario_id: str
    extracted_scenario_id: str


class DBMSCoverageResponse(BaseModel):
    expert_scenario_count: int
    extracted_scenario_count: int
    covered_scenario_count: int
    coverage_percentage: float
    target_percentage: float
    target_met: bool
    matches: List[DBMSCoverageMatch]
    uncovered_expert_scenario_ids: List[str]


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