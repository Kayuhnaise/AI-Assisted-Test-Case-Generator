from fastapi import FastAPI

from app.models import RequirementInput, TestCaseResponse

from app.generator import generate_test_cases


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
def generate(request: RequirementInput):

    test_cases = generate_test_cases(request.requirement)

    return TestCaseResponse(
        requirement=request.requirement,
        test_cases=test_cases
    )