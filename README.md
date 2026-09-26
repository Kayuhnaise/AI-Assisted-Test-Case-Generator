# AI-Assisted Requirement-to-Test Case Generator

## Overview

This project is a proof-of-concept AI-assisted software engineering tool that generates structured software test cases from natural-language requirements.

The project follows an AI4SE (Artificial Intelligence for Software Engineering) approach by using AI to assist with software testing activities.

## Current Status

Completed so far:

- Created the project directory structure
- Created a Python virtual environment
- Installed FastAPI, Uvicorn, Pydantic, pytest, and the Ollama Python client
- Created Pydantic models for requirements and test cases
- Created a FastAPI backend
- Added a `/health` endpoint
- Added a `/generate` endpoint
- Added input validation for natural-language requirements
- Created a prompt module for LLM prompting
- Installed and configured Ollama for local LLM inference
- Integrated Qwen3:4b as the local language model
- Added structured LLM output using a Pydantic-generated JSON schema
- Added Pydantic validation of LLM-generated test cases
- Verified the complete requirement-to-AI-test-case pipeline through the FastAPI API
- Added automatic pytest execution for generated tests and structured result capture in `/generate`
- Added a separate scenario-identification step (`POST /scenarios`) that derives positive, negative, boundary, and edge scenarios from a requirement and its associated Python source code, before any test case is generated
- Created an initial reference evaluation dataset (`evaluation/reference/`) of manually-derived, ground-truth scenarios for a small set of requirements, for comparison against AI-generated output

The system accepts a natural-language requirement and its associated Python source code, identifies scenarios, generates scenario-linked pytest tests, runs those tests, and returns both the tests and their execution results. The `/scenarios` endpoint remains available to run scenario identification by itself.

## Current Architecture

```text
Requirement + Python Source Code
            |
            v
      FastAPI Backend
            |
            v
     Input Validation
        (Pydantic)
            |
            v
 Scenario Identification
      |
      v
 Scenario-Grounded Test
   and pytest Generation
            |
            v
         Ollama
            |
            v
        Qwen3:4b
            |
            v
   Structured JSON Output
            |
            v
    Pydantic Validation
            |
            v
 Scenarios + Test Cases
    + pytest Module
      |
      v
    Bounded pytest Run
      |
      v
    Execution Results
```

`POST /scenarios` exposes the scenario-identification stage by itself. `POST /generate` runs that stage first, passes its scenario output to test generation, executes the resulting pytest module in a temporary directory with a 15-second timeout, and returns scenarios, structured test cases, the pytest module, and execution results.

## Test Case Structure

Each generated test case contains:

- Test case ID
- Title
- Test type
  - Positive
  - Negative
  - Boundary
  - Edge
- Preconditions
- Test steps
- Expected result
- The scenario ID it covers
- One executable pytest test function

## Scenario Structure

Each identified scenario (from `POST /scenarios`) contains:

- Scenario ID
- Category
  - Positive
  - Negative
  - Boundary
  - Edge
- Description of the expected behavior or boundary condition being covered

A scenario describes a behavior, not a test: it does not contain test steps or expected-result wording.

## Example Requirement

```text
The system shall lock an account after five consecutive failed login attempts.
```

## Project Structure

```text
AI-Assisted-Test-Case-Generator/
|
├── backend/
|   ├── app/
|   |   ├── __init__.py
|   |   ├── main.py
|   |   ├── models.py
|   |   ├── generator.py
|   |   └── prompts.py
|   |
|   ├── tests/
|   └── requirements.txt
|
├── frontend/
├── evaluation/
|   └── reference/
|       ├── account_lockout.json
|       ├── order_discount.json
|       ├── username_length.json
|       └── safe_division.json
├── docs/
├── .gitignore
└── README.md
```

Each file under `evaluation/reference/` contains a `requirement`, its associated `source_code`, a list of `reference_scenarios` (manually agreed ground truth, in the same `id`/`category`/`description` shape returned by `POST /scenarios`), and free-text `notes` explaining the reasoning behind non-obvious scenarios.

## Running the Backend

### 1. Navigate to the backend

```powershell
cd backend
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment on Windows

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install Python dependencies

```powershell
pip install -r requirements.txt
```

## Local LLM Setup

The application currently uses Qwen3:4b through Ollama.

### 1. Install Ollama

Install Ollama from the official Ollama website.

### 2. Download Qwen3:4b

```powershell
ollama pull qwen3:4b
```

### 3. Verify the model

```powershell
ollama list
```

The installed model list should include `qwen3:4b`.

## Start the Application

From the `backend` directory with the virtual environment activated, run:

```powershell
uvicorn app.main:app --reload
```

The interactive FastAPI documentation will be available at:

```text
http://127.0.0.1:8000/docs
```

## API Endpoints

### GET `/`

Returns basic API information.

### GET `/health`

Checks whether the backend is running.

### POST `/generate`

Accepts a natural-language software requirement and its associated Python source code. It identifies scenarios first, then generates one scenario-linked test case and pytest function per scenario. The response includes `scenarios`, `test_cases`, `pytest_code`, and `pytest_result`. The API automatically runs the generated module with pytest in a temporary directory (15-second timeout) and returns the execution status, exit code, test counts, stdout, and stderr. The `pytest_code` field is also returned so it can be saved and rerun manually.

### POST `/scenarios`

Accepts a natural-language software requirement and its associated Python source code, and uses Qwen3:4b to identify the distinct positive, negative, boundary, and edge testing scenarios implied by both, before any test case is written.

## Validation

Both endpoints accept `requirement` and `source_code`; requirements and source code are validated before being sent to the LLM. `/generate` rejects invalid Python source.

LLM output is constrained using a JSON schema generated from the Pydantic models. The returned JSON is then validated again using Pydantic before the test cases are returned by the API.

The generated scenario IDs and categories are checked against the test cases, each case must contain valid Python with one pytest test function, and the combined pytest module must parse. Pytest execution is bounded by a timeout, and its result is included in the response. These checks do not guarantee that every AI-generated assertion is semantically correct; review generated tests before relying on them.

## Known Limitations

The current system does not guarantee the semantic correctness of AI-generated test cases.

An LLM can produce a test case or assertion that contradicts the source or requirement despite being structurally valid. `/generate` consumes the identified scenarios, validates scenario-to-test coverage, and executes the resulting module with pytest, but semantic correctness still requires review. Test execution runs submitted Python source and generated code. It is intended for trusted local development only and is **not sandboxed**; do not expose this endpoint to untrusted users or the public internet. The generated module tests the submitted source included in that module; it is not yet wired to an external application module or CI execution pipeline.

The reference evaluation dataset currently contains 4 requirements, short of the proposal's target of 15-20. There is not yet an automated comparison between AI-generated scenarios and the reference scenarios; evaluation metrics (scenario coverage, scenario-type coverage, test execution rate, requirement alignment) are defined in the project proposal but not yet implemented.

## Next Steps

- Implement automated comparison of AI-generated scenarios against `evaluation/reference/` ground truth (scenario coverage, scenario-type coverage)
- Expand the reference evaluation dataset toward the proposal's target of 15-20 requirements
- Evaluate generated tests for correctness, coverage, diversity, and hallucinations
- Develop the frontend
- Add human review and editing

## Evaluation Goal

The planned evaluation will investigate:

> How effectively can an LLM generate useful and valid software test cases from natural-language requirements compared with a reference set of manually designed test cases?
