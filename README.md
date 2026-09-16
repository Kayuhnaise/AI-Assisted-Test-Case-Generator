# AI-Assisted Requirement-to-Test Case Generator

## Overview

This project is a proof-of-concept AI-assisted software engineering tool that generates structured software test cases from natural-language requirements.

The project follows an AI4SE (Artificial Intelligence for Software Engineering) approach by using AI to assist with the software testing process.

## Current Status

The initial backend architecture has been implemented.

Completed so far:

- Created the project directory structure
- Created a Python virtual environment
- Installed FastAPI, Uvicorn, Pydantic, and pytest
- Created Pydantic models for requirements and test cases
- Created a FastAPI backend
- Added a `/health` endpoint
- Added a `/generate` endpoint
- Added input validation for natural-language requirements
- Created a prompt module for future LLM integration
- Created a temporary mock test-case generator
- Tested the API using FastAPI Swagger documentation
- Verified successful test-case responses
- Verified that invalid requirements are rejected with HTTP 422

## Current Architecture

```text
Natural-Language Requirement
            |
            v
      FastAPI Backend
            |
            v
     Input Validation
        (Pydantic)
            |
            v
    Test Case Generator
            |
            v
   Structured Test Cases
            |
            v
      JSON Response
```

The test-case generator currently uses mock data. The next step is to replace the mock generator with an LLM.

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

## Example Requirement

```text
The system shall lock an account after five consecutive failed login attempts.
```

## Project Structure

```text
requirement-test-generator/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── generator.py
│   │   └── prompts.py
│   │
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
├── evaluation/
├── docs/
├── .gitignore
└── README.md
```

## Running the Backend

Navigate to the backend:

```powershell
cd backend
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate the virtual environment on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
pip install -r requirements.txt
```

Start the API:

```powershell
uvicorn app.main:app --reload
```

The interactive API documentation will be available at:

```text
http://127.0.0.1:8000/docs
```

## Next Steps

- Connect a local LLM
- Replace the mock generator with AI-generated test cases
- Validate structured LLM output
- Add error handling
- Develop the frontend
- Add human review and editing
- Create an evaluation dataset
- Evaluate generated test cases for correctness and requirement coverage