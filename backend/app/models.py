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


class ScenarioCore(BaseModel):
    """
    Structured intermediate representation shared by the Python and
    DBMS pipelines. Every scenario declares its category, the
    condition it targets, and the outcome it expects as separate
    fields so that downstream steps and evaluation can compare fields
    instead of interpreting free text.
    """

    id: str = Field(min_length=1)
    category: Literal["positive", "negative", "boundary", "edge"]
    precondition: str = Field(
        min_length=1,
        description="The state, data, or input condition the scenario targets",
    )
    behavior_under_test: str = Field(
        min_length=1,
        description="The operation or behavior being exercised",
    )
    expected_result: str = Field(
        min_length=1,
        description="The observable outcome required by the requirement",
    )


class InputArgument(BaseModel):
    name: str = Field(
        min_length=1,
        description="Parameter name of a function in the source code",
    )
    value: str | int | float | bool | None = Field(
        description="Concrete value passed for this parameter",
    )


class Scenario(ScenarioCore):
    requirement_clause: str = Field(
        min_length=1,
        description=(
            "Exact, verbatim quote of the requirement text this "
            "scenario targets"
        ),
    )
    expected_outcome_kind: Literal["success", "error", "unspecified"] = Field(
        description=(
            "success: returns a result; error: raises or rejects; "
            "unspecified: the requirement does not define the outcome"
        ),
    )
    example_inputs: List[InputArgument] = Field(
        description="Concrete argument values that exercise the scenario",
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


class DBMSScenario(ScenarioCore):
    pass


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


class ScenarioCoverageMatch(BaseModel):
    reference_scenario_id: str
    generated_scenario_id: str
    matched_by: Literal["example_inputs", "judge"]


class ScenarioCoverageResponse(BaseModel):
    reference_scenario_count: int
    generated_scenario_count: int
    covered_scenario_count: int
    coverage_percentage: float
    matches: List[ScenarioCoverageMatch]
    uncovered_reference_scenario_ids: List[str]
    aligned_scenario_count: int
    alignment_percentage: float
    misaligned_scenario_ids: List[str]


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
    untested_scenario_ids: List[str] = Field(
        default_factory=list,
        description=(
            "Scenarios whose outcome the requirement does not specify; "
            "no test is generated for them"
        ),
    )
    test_cases: List[TestCase]
    pytest_code: str
    pytest_result: PytestExecutionResult


class SQLExpectedOutcome(BaseModel):
    outcome_type: Literal[
        "rows",
        "scalar",
        "row_count",
        "error",
        "database_state"
    ]
    expected_value: str | int | float | bool | None = None
    expected_error: str | None = None
    assertion_description: str = Field(min_length=1)



class SQLVerificationAssertion(BaseModel):
    query: str = Field(min_length=1)
    expected_scalar: str | int | float | bool | None = None
    expected_rows: list[
        list[str | int | float | bool | None]
    ] | None = None

    @model_validator(mode="after")
    def exactly_one_expected_result(self):
        has_scalar = self.expected_scalar is not None
        has_rows = self.expected_rows is not None

        if has_scalar == has_rows:
            raise ValueError(
                "Provide exactly one of expected_scalar "
                "or expected_rows"
            )

        return self



class DBMSSQLTestCase(BaseModel):
    id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)

    title: str = Field(min_length=1)
    category: Literal[
        "positive", "negative", "boundary", "edge"
    ]

    sql_dialect: Literal["sqlite", "postgresql"]

    preconditions: list[str]
    constraints: list[str]

    setup_sql: list[str]
    test_sql: str = Field(min_length=1)
    verification_assertions: list[SQLVerificationAssertion] = Field(
        default_factory=list
    )
    verification_sql: list[str] = Field(default_factory=list)

    expected_outcome: SQLExpectedOutcome

    cleanup_sql: list[str] = Field(default_factory=list)


class GeneratedDBMSSQLTests(BaseModel):
    test_cases: list[DBMSSQLTestCase] = Field(min_length=1)


class DBMSSQLGenerationRequest(BaseModel):
    scenarios: list[DBMSScenario] = Field(min_length=1)
    requirement_document: str = Field(min_length=1)


class DBMSSQLGenerationResponse(BaseModel):
    test_cases: list[DBMSSQLTestCase]


class DBMSPipelineGenerationRequest(BaseModel):
    requirement_document: str = Field(min_length=1)
    sql_dialect: Literal["sqlite", "postgresql"] = "postgresql"
    r1_provider: Literal["ollama", "claude"] = "ollama"


class DBMSPipelineGenerationResponse(BaseModel):
    requirement_document: str
    sql_dialect: Literal["sqlite", "postgresql"]
    scenarios: list[DBMSScenario]
    test_cases: list[DBMSSQLTestCase]
    review_required: Literal[True] = True


class DBMSSQLValidationRequest(BaseModel):
    test_cases: list[DBMSSQLTestCase] = Field(min_length=1)


class DBMSSQLValidationResult(BaseModel):
    test_case_id: str
    scenario_id: str

    status: Literal["passed", "failed", "error"]

    setup_successful: bool
    execution_successful: bool
    assertion_passed: bool

    expected_outcome: str
    actual_outcome: str

    errors: list[str] = Field(default_factory=list)


class DBMSSQLValidationResponse(BaseModel):
    total_tests: int
    passed: int
    failed: int
    errors: int

    validity_percentage: float
    target_percentage: float
    target_met: bool

    results: list[DBMSSQLValidationResult]
