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
    scenarios: List[DBMSScenario]


class GeneratedDBMSSQLScenarios(BaseModel):
    scenarios: List[DBMSScenario]


class DBMSScenarioResponse(BaseModel):
    requirement_document: str
    scenarios: List[DBMSScenario]


class DBMSSQLTestRequest(BaseModel):
    scenarios: List[DBMSScenario] = Field(min_length=1)
    postgres_version: str = Field(default="17", min_length=1)

    @model_validator(mode="after")
    def scenario_ids_must_be_unique(self) -> DBMSSQLTestRequest:
        scenario_ids = [scenario.id for scenario in self.scenarios]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("Scenario IDs must be unique")
        return self


class DBMSSQLTestPackage(BaseModel):
    test_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    setup_sql: str
    data_sql: str
    test_sql: str = Field(min_length=1)
    expected_outcome: Literal["success", "error"]
    expected_sqlstate: str | None = Field(
        default=None,
        pattern=r"^[0-9A-Z]{5}$",
    )
    cleanup_sql: str

    @model_validator(mode="after")
    def sqlstate_must_match_outcome(self) -> DBMSSQLTestPackage:
        if self.expected_outcome == "error" and self.expected_sqlstate is None:
            raise ValueError("Error outcomes require an expected SQLSTATE")
        if self.expected_outcome == "success" and self.expected_sqlstate is not None:
            raise ValueError("Successful outcomes must not include a SQLSTATE")
        return self


class GeneratedDBMSSQLTests(BaseModel):
    tests: List[DBMSSQLTestPackage] = Field(min_length=1)


class DBMSSQLTestResponse(BaseModel):
    postgres_version: str
    tests: List[DBMSSQLTestPackage]


class DBMSSQLValidationRequest(BaseModel):
    tests: List[DBMSSQLTestPackage] = Field(min_length=1)

    @model_validator(mode="after")
    def test_ids_must_be_unique(self) -> DBMSSQLValidationRequest:
        test_ids = [test.test_id for test in self.tests]
        if len(set(test_ids)) != len(test_ids):
            raise ValueError("SQL test IDs must be unique")
        return self


class DBMSSQLValidationResult(BaseModel):
    test_id: str
    scenario_id: str
    valid: bool
    errors: List[str]


class DBMSSQLValidationResponse(BaseModel):
    valid: bool
    results: List[DBMSSQLValidationResult]


class DBMSSQLExecutionRequest(BaseModel):
    tests: List[DBMSSQLTestPackage] = Field(min_length=1)

    @model_validator(mode="after")
    def test_ids_must_be_unique(self) -> DBMSSQLExecutionRequest:
        test_ids = [test.test_id for test in self.tests]
        if len(set(test_ids)) != len(test_ids):
            raise ValueError("SQL test IDs must be unique")
        return self


class DBMSSQLExecutionResult(BaseModel):
    test_id: str
    scenario_id: str
    status: Literal["passed", "failed", "error"]
    expected_sqlstate: str | None
    actual_sqlstate: str | None
    duration_ms: float
    detail: str | None = None


class DBMSSQLExecutionResponse(BaseModel):
    results: List[DBMSSQLExecutionResult]


class DBMSCoverageMetric(BaseModel):
    covered: int
    total: int
    percentage: float


class DBMSCoverageModule(BaseModel):
    name: Literal[
        "parser",
        "analysis",
        "optimizer",
        "executor",
        "storage",
        "transactions",
    ]
    line_coverage: DBMSCoverageMetric
    branch_coverage: DBMSCoverageMetric
    function_coverage: DBMSCoverageMetric
    uncovered_files: List[str]
    feature_hints: List[
        Literal[
            "SQL parsing and syntax",
            "Name resolution and semantic analysis",
            "Query planning and optimization",
            "Query execution",
            "Table, index, and constraint operations",
            "Transactions and statement execution",
        ]
    ]


class DBMSFeatureHint(BaseModel):
    feature: Literal[
        "SQL parsing and syntax",
        "Name resolution and semantic analysis",
        "Query planning and optimization",
        "Query execution",
        "Table, index, and constraint operations",
        "Transactions and statement execution",
    ]
    module: Literal[
        "parser",
        "analysis",
        "optimizer",
        "executor",
        "storage",
        "transactions",
    ]
    uncovered_files: List[str]


class DBMSCoverageReport(BaseModel):
    files_analyzed: int
    line_coverage: DBMSCoverageMetric
    branch_coverage: DBMSCoverageMetric
    function_coverage: DBMSCoverageMetric
    modules: List[DBMSCoverageModule]
    feature_hints: List[DBMSFeatureHint]


class DBMSCoverageAnalysisRequest(BaseModel):
    lcov_report: str = Field(min_length=1)


class DBMSCoverageGenerationRequest(BaseModel):
    requirement_document: str = Field(min_length=1)
    coverage_report: DBMSCoverageReport


class DBMSCoverageGenerationResponse(BaseModel):
    targeted_features: List[str]
    scenarios: List[DBMSScenario]


class DBMSRefinementRequest(BaseModel):
    scenario: DBMSScenario
    failed_test: DBMSSQLTestPackage
    error_message: str = Field(min_length=1)
    actual_sqlstate: str | None = Field(
        default=None,
        pattern=r"^[0-9A-Z]{5}$",
    )

    @model_validator(mode="after")
    def failed_test_must_match_scenario(self) -> DBMSRefinementRequest:
        if self.failed_test.scenario_id != self.scenario.id:
            raise ValueError("The failed test must match the supplied scenario")
        return self


class DBMSRefinementResponse(BaseModel):
    repaired_test: DBMSSQLTestPackage
    oracle_preserved: bool


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