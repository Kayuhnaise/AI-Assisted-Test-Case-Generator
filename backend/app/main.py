from fastapi import FastAPI

from app.models import (
    DBMSCoverageRequest,
    DBMSCoverageResponse,
    DBMSRequirementInput,
    DBMSScenarioResponse,
    DBMSSQLGenerationRequest,
    DBMSSQLGenerationResponse,
    DBMSSQLValidationRequest,
    DBMSSQLValidationResponse,
    ScenarioInput,
    ScenarioResponse,
    TestCaseResponse,
)

from app.dbms_scenarios import (
    evaluate_dbms_scenario_coverage,
    identify_dbms_scenarios,
)

from app.dbms_sql_generator import generate_dbms_sql_tests
from app.dbms_sql_validator import validate_sql_tests
from app.generator import generate_test_cases, identify_scenarios
from app.test_runner import run_pytest


app = FastAPI(
    title="AI-Assisted Requirement-to-Test Case Generator",
    description=(
        "Generates structured software test cases "
        "from natural-language requirements."
    ),
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "AI-Assisted Requirement-to-Test Case Generator API"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


@app.post("/generate", response_model=TestCaseResponse)
def generate(request: ScenarioInput):
    scenarios = identify_scenarios(request.requirement, request.source_code)
    test_cases, pytest_code = generate_test_cases(
        request.requirement,
        request.source_code,
        scenarios,
    )
    pytest_result = run_pytest(pytest_code)

    return TestCaseResponse(
        requirement=request.requirement,
        scenarios=scenarios,
        test_cases=test_cases,
        pytest_code=pytest_code,
        pytest_result=pytest_result,
    )


@app.post("/scenarios", response_model=ScenarioResponse)
def scenarios(request: ScenarioInput):

    scenarios = identify_scenarios(request.requirement, request.source_code)

    return ScenarioResponse(
        requirement=request.requirement,
        scenarios=scenarios
    )


@app.post("/dbms/scenarios", response_model=DBMSScenarioResponse)
def dbms_scenarios(request: DBMSRequirementInput):
    scenarios = identify_dbms_scenarios(request.requirement_document)
    return DBMSScenarioResponse(
        requirement_document=request.requirement_document,
        scenarios=scenarios,
    )


@app.post("/dbms/coverage", response_model=DBMSCoverageResponse)
def dbms_coverage(request: DBMSCoverageRequest):
    return evaluate_dbms_scenario_coverage(
        request.expert_scenarios,
        request.extracted_scenarios,
    )


@app.post(
    "/dbms/generate",
    response_model=DBMSSQLGenerationResponse,
)
def dbms_generate_sql(
    request: DBMSSQLGenerationRequest,
):
    test_cases = generate_dbms_sql_tests(
        requirement_document=request.requirement_document,
        scenarios=request.scenarios,
    )

    return DBMSSQLGenerationResponse(
        test_cases=test_cases
    )


@app.post(
    "/dbms/validate",
    response_model=DBMSSQLValidationResponse,
)
def dbms_validate_sql(
    request: DBMSSQLValidationRequest,
):
    return validate_sql_tests(
        request.test_cases
    )
