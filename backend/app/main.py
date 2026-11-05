from fastapi import FastAPI, HTTPException

from app.models import (
    DBMSCoverageAnalysisRequest,
    DBMSCoverageGenerationRequest,
    DBMSCoverageGenerationResponse,
    DBMSCoverageRequest,
    DBMSCoverageResponse,
    DBMSCoverageReport,
    DBMSRefinementRequest,
    DBMSRefinementResponse,
    DBMSRequirementInput,
    DBMSScenarioResponse,
    DBMSSQLExecutionRequest,
    DBMSSQLExecutionResponse,
    DBMSSQLTestRequest,
    DBMSSQLTestResponse,
    DBMSSQLValidationRequest,
    DBMSSQLValidationResponse,
    ScenarioInput,
    ScenarioResponse,
    TestCaseResponse,
)

from app.dbms_coverage import analyze_lcov_report
from app.dbms_scenarios import (
    evaluate_dbms_scenario_coverage,
    identify_dbms_scenarios,
)
from app.dbms_refinement import (
    generate_coverage_guided_scenarios,
    refine_failed_dbms_test,
)
from app.dbms_sql_execution import execute_dbms_sql_tests
from app.dbms_sql_tests import generate_dbms_sql_tests
from app.dbms_sql_validation import validate_dbms_sql_tests
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


@app.post("/dbms/sql-tests/generate", response_model=DBMSSQLTestResponse)
def dbms_sql_tests(request: DBMSSQLTestRequest):
    try:
        tests = generate_dbms_sql_tests(
            request.scenarios,
            postgres_version=request.postgres_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return DBMSSQLTestResponse(
        postgres_version=request.postgres_version,
        tests=tests,
    )


@app.post(
    "/dbms/sql-tests/validate",
    response_model=DBMSSQLValidationResponse,
)
def dbms_sql_tests_validate(request: DBMSSQLValidationRequest):
    return validate_dbms_sql_tests(request.tests)


@app.post(
    "/dbms/sql-tests/execute",
    response_model=DBMSSQLExecutionResponse,
)
def dbms_sql_tests_execute(request: DBMSSQLExecutionRequest):
    validation = validate_dbms_sql_tests(request.tests)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "SQL validation failed; no tests were executed",
                "results": [
                    result.model_dump() for result in validation.results
                ],
            },
        )
    try:
        return execute_dbms_sql_tests(request.tests)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/dbms/coverage/analyze",
    response_model=DBMSCoverageReport,
)
def dbms_coverage_analyze(request: DBMSCoverageAnalysisRequest):
    try:
        return analyze_lcov_report(request.lcov_report)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/dbms/coverage/generate",
    response_model=DBMSCoverageGenerationResponse,
)
def dbms_coverage_generate(request: DBMSCoverageGenerationRequest):
    try:
        return generate_coverage_guided_scenarios(
            request.requirement_document,
            request.coverage_report,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/dbms/refine", response_model=DBMSRefinementResponse)
def dbms_refine(request: DBMSRefinementRequest):
    try:
        return refine_failed_dbms_test(
            request.scenario,
            request.failed_test,
            request.error_message,
            request.actual_sqlstate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc