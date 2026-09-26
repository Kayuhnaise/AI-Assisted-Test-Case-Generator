from fastapi import FastAPI

from app.models import ScenarioInput, ScenarioResponse, TestCaseResponse

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