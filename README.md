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

The system can currently accept a natural-language software requirement and return AI-generated structured test cases.

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
    Prompt Construction
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
   Structured Test Cases
```

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
├── docs/
├── .gitignore
└── README.md
```

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

Accepts a natural-language software requirement and uses Qwen3:4b to generate structured software test cases.

## Validation

Input requirements are validated using Pydantic before being sent to the LLM.

LLM output is constrained using a JSON schema generated from the Pydantic models. The returned JSON is then validated again using Pydantic before the test cases are returned by the API.

This ensures structural validity but does not guarantee that every AI-generated test case is semantically correct.

## Known Limitations

The current system does not yet guarantee the semantic correctness of AI-generated test cases.

An LLM can produce a test case that conforms to the required JSON structure but contains an expected result that contradicts the original requirement. Additional scenario identification and validation will be implemented to improve requirement traceability and semantic correctness.

## Next Steps

- Implement explicit requirement scenario identification
- Improve semantic correctness and requirement traceability
- Generate executable pytest test code
- Add automated pytest execution
- Develop the frontend
- Add human review and editing
- Create the reference evaluation dataset
- Evaluate generated tests for correctness, coverage, diversity, and hallucinations

## Evaluation Goal

The planned evaluation will investigate:

> How effectively can an LLM generate useful and valid software test cases from natural-language requirements compared with a reference set of manually designed test cases?
