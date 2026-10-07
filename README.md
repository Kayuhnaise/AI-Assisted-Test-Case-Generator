# AI-Assisted Requirement-to-Test Case Generator

## Team Members

- Gulnar Aldasheva
- Samhitha Dwarakanath
- Keya Gangadharan

**Course:** SWENG 889 — Fall I 2026

---

## Project Overview

The **AI-Assisted Requirement-to-Test Case Generator** is a proof-of-concept AI4SE tool that converts natural-language software requirements and corresponding Python source code into structured test scenarios and executable pytest tests.

The system uses a local Large Language Model (LLM) to:

1. Interpret a software requirement and its associated Python source code.
2. Identify relevant positive, negative, boundary, and edge-case testing scenarios.
3. Generate structured test cases linked to those scenarios.
4. Generate executable pytest code.
5. Validate generated output.
6. Execute the generated tests automatically.
7. Return the identified scenarios, generated tests, pytest code, and execution results.

The project investigates both the usefulness and limitations of LLM-assisted software test generation. In particular, the evaluation distinguishes between **scenario coverage, pipeline reliability, test executability, and semantic correctness** rather than assuming that a passing generated test is necessarily a good test.

---

## Problem and Motivation

Translating software requirements into comprehensive test cases is a time-consuming software engineering activity.

Developers and QA engineers must determine:

- expected behavior;
- positive cases;
- negative cases;
- boundary conditions;
- edge cases;
- appropriate expected results; and
- how those scenarios should be represented as executable tests.

Important scenarios can be overlooked, and requirements can become disconnected from the tests intended to verify them.

This project explores whether a local LLM can assist with that process by transforming requirements into structured, executable tests while maintaining traceability between the requirement, identified scenarios, generated tests, and execution results.

The system is intended as an **assistive testing tool**, not as a replacement for developer or QA review.

---

## AI4SE / SE4AI Context

This project primarily represents **AI for Software Engineering (AI4SE)** because an AI model is used to assist with a traditional software engineering activity: software testing.

The LLM assists with:

- requirement interpretation;
- test scenario identification; and
- pytest test generation.

The project also incorporates **Software Engineering for AI (SE4AI)** practices by surrounding probabilistic model output with deterministic engineering controls, including:

- Pydantic schema validation;
- scenario-to-test traceability;
- Python syntax and AST validation;
- deterministic generation safeguards;
- bounded pytest execution; and
- explicit failure reporting.

The evaluation showed that prompt engineering alone is not sufficient to guarantee reliable generated tests.

---

## System Architecture

```text
Natural-Language Requirement
          +
    Python Source Code
          |
          v
     FastAPI API
          |
          v
   Input Validation
      (Pydantic)
          |
          v
 Scenario Identification
          |
          v
       Ollama
          |
          v
      Qwen3:4b
          |
          v
 Structured Scenarios
          |
          v
 Scenario-Grounded
   Test Generation
          |
          v
 Structured Test Cases
   + pytest Functions
          |
          v
 Validation & Safeguards
  (Pydantic + Python AST)
          |
          v
  Combined pytest Module
          |
          v
    Bounded pytest Run
          |
          v
 Scenarios + Test Cases
 + Code + Test Results
```

The architecture intentionally separates **scenario identification** from **test generation**.

This separation makes it possible to distinguish between:

1. a scenario that the model failed to identify; and
2. a scenario that was correctly identified but resulted in a poor generated test.

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Primary implementation language |
| FastAPI | REST API |
| Pydantic | Request, response, and LLM-output validation |
| Ollama | Local LLM runtime |
| Qwen3:4b | Local language model |
| pytest | Generated-test execution and backend testing |
| Python AST | Static validation and generation safeguards |
| Git / GitHub | Version control and project repository |

The LLM runs locally through Ollama. No hosted AI API is required.

---

## Repository Structure

```text
AI-Assisted-Test-Case-Generator/
|
├── backend/
|   ├── app/
|   |   ├── __init__.py
|   |   ├── main.py
|   |   ├── models.py
|   |   ├── generator.py
|   |   ├── prompts.py
|   |   └── test_runner.py
|   |
|   ├── tests/
|   |   └── test_generate.py
|   |
|   └── requirements.txt
|
├── evaluation/
|   ├── reference/
|   |   ├── account_lockout.json
|   |   ├── order_discount.json
|   |   ├── safe_division.json
|   |   └── username_length.json
|   |
|   └── evaluation result JSON files
|
├── .gitignore
└── README.md
```

Additional final-project documentation may be added under `docs/`.

---

## Primary API Endpoints

### `GET /`

Returns basic API information.

### `GET /health`

Verifies that the FastAPI application is running.

### `POST /scenarios`

Accepts a natural-language requirement and Python source code and asks the local LLM to identify relevant testing scenarios.

Each scenario contains:

- scenario ID;
- category;
- description.

Supported categories include:

- positive;
- negative;
- boundary;
- edge.

### `POST /generate`

Runs the complete requirement-to-test pipeline.

The endpoint:

1. validates the request;
2. identifies testing scenarios;
3. generates one scenario-linked test case per supplied scenario;
4. validates the generated output;
5. applies deterministic safeguards;
6. assembles the source and generated tests;
7. executes the tests using pytest; and
8. returns the complete result.

The response includes:

- original requirement;
- identified scenarios;
- structured test cases;
- generated pytest code; and
- pytest execution results.

---

## Generated Test Case Structure

Each generated test case contains:

- test case ID;
- title;
- test type/category;
- preconditions;
- test steps;
- expected result;
- source scenario ID; and
- one executable pytest test function.

The scenario ID provides traceability between the scenario identified by the model and the generated executable test.

---

# Installation and Setup

## Prerequisites

The project requires:

- Python
- Git
- Ollama
- Qwen3:4b
- a local environment capable of running the Qwen3:4b model

No external hosted LLM API or API key is required.

No project-specific environment variables are currently required.

---

## 1. Clone the Repository

```powershell
git clone https://github.com/Kayuhnaise/AI-Assisted-Test-Case-Generator.git
cd AI-Assisted-Test-Case-Generator
```

---

## 2. Navigate to the Backend

```powershell
cd backend
```

---

## 3. Create a Python Virtual Environment

```powershell
python -m venv .venv
```

---

## 4. Activate the Virtual Environment

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## 5. Install Dependencies

```powershell
pip install -r requirements.txt
```

---

# Local LLM Setup

The application uses **Qwen3:4b** through Ollama.

## 1. Install Ollama

Install Ollama from the official Ollama distribution.

## 2. Pull the Model

```powershell
ollama pull qwen3:4b
```

## 3. Verify the Model

```powershell
ollama list
```

The installed model list should contain:

```text
qwen3:4b
```

If Ollama is not already running, start the Ollama service before using the API.

---

# Running the Proof of Concept

From the `backend` directory with the virtual environment activated:

```powershell
python -m uvicorn app.main:app --reload
```

The API should start locally.

Open the interactive FastAPI documentation at:

```text
http://127.0.0.1:8000/docs
```

---

## Example `/generate` Request

In the FastAPI documentation, select:

```text
POST /generate
```

Then choose **Try it out**.

Example request:

```json
{
  "requirement": "The system shall accept usernames between 3 and 20 characters long, inclusive, and reject usernames outside that range.",
  "source_code": "def is_valid_username(username: str) -> bool:\n    return 3 <= len(username) <= 20"
}
```

A successful response contains:

```text
requirement
scenarios
test_cases
pytest_code
pytest_result
```

For example, the model may identify the lower and upper username-length boundaries and generate executable tests for values immediately below, at, and above those boundaries.

Because LLM generation is nondeterministic, the exact scenarios and generated tests may differ between runs.

---

# Running Automated Tests

From the `backend` directory with the virtual environment activated:

```powershell
python -m pytest -q
```

At the final project checkpoint, the repository's automated backend test suite contained **5 passing tests**.

Dependency deprecation warnings may appear during execution. These warnings do not represent test failures.

---

# Validation and Generation Safeguards

The project uses multiple layers of validation.

## Structured LLM Output

LLM responses are constrained using schemas derived from Pydantic models and are validated before being accepted by the application.

## Scenario-to-Test Traceability

Each generated test must correspond to an identified scenario.

## Python Validation

Generated Python is parsed before execution.

## Pytest Import Safeguard

During evaluation, the model generated code that used `pytest.raises` without importing `pytest`.

A deterministic safeguard was added using Python AST processing. If generated code references `pytest` but does not import it, the application adds the required import.

## Category Normalization

During evaluation, a generated test category sometimes differed from the category assigned to its source scenario.

The identified scenario is treated as the source of truth. A generated test-category mismatch is normalized to the corresponding scenario category rather than causing the entire pipeline to fail.

These safeguards address known **structural** generation failures. They do not guarantee semantic correctness.

---

# Evaluation

## Evaluation Question

The project investigated:

> To what extent can a local LLM generate relevant, executable pytest tests from natural-language requirements and Python source code, and how do prompt and validation improvements affect the quality and reliability of those tests?

---

## Reference Benchmark

The evaluation uses four requirements containing **21 manually defined reference scenarios**.

| Requirement | Reference Scenarios |
|---|---:|
| Account Lockout | 5 |
| Order Discount | 5 |
| Safe Division | 5 |
| Username Length | 6 |
| **Total** | **21** |

Reference files are stored in:

```text
evaluation/reference/
```

Each reference file contains:

- the requirement;
- associated Python source code;
- manually defined reference scenarios; and
- notes where applicable.

---

## Evaluation Stages

Four stages were evaluated.

### Baseline

Initial prompt and generation pipeline.

### Improvement 1

Focused on improving scenario and test coverage.

### Improvement 2

Strengthened test-generation prompting, including instructions related to:

- required imports;
- scenario traceability;
- requirement-first expected behavior;
- avoiding unsupported behavior;
- numeric verification;
- pytest executability.

### Improvement 3

Added deterministic safeguards for:

- missing pytest imports; and
- scenario/test category mismatches.

---

# Evaluation Results

## Scenario Coverage

Generated scenarios were manually compared against the 21 predefined reference scenarios.

A generated scenario counted as covered when it represented the same substantive condition as the reference scenario, even when the exact wording or category differed.

| Stage | Reference Scenario Coverage |
|---|---:|
| Baseline | 6/21 (28.6%) |
| Improvement 1 | 14/21 (66.7%) |
| Improvement 2 | 7/21 (33.3%) |
| Improvement 3 | 14/21 (66.7%) |

Coverage therefore increased from **28.6% at baseline to as high as 66.7%**, but improvement was not monotonic.

This variability is an important finding of the project.

---

## Pipeline and Test Execution Results

| Stage | Successful Pipeline Runs | Passing Generated Tests |
|---|---:|---:|
| Baseline | 3/4 | 8/8* |
| Improvement 1 | 4/4 | 14/16 |
| Improvement 2 | 3/4 | 9/10* |
| Improvement 3 | 4/4† | 10/15 |

`*` Excludes requirements where the pipeline failed before executable tests were produced.

`†` The first Safe Division Improvement 3 attempt encountered a local Ollama inference failure. A single retry completed successfully.

---

## Why Test Pass Rate Is Not Enough

A generated pytest test passing does **not** necessarily mean the generated test is correct or comprehensive.

For example, the baseline produced:

```text
8/8 passing generated tests
```

but represented only:

```text
6/21 reference scenarios
```

or **28.6% reference-scenario coverage**.

Therefore, generated-test pass rate and test-generation quality must be evaluated separately.

---

# Important Evaluation Findings

Several failures observed during the project informed later improvements.

## Missing Boundary Scenario

The baseline Account Lockout generation missed the exact lockout threshold of five attempts.

Later iterations identified the threshold correctly.

## Incorrect Expected Result

One Order Discount generation produced an incorrect expected numerical value for a very large order total.

The generated test was structurally valid but semantically incorrect.

## Missing `pytest` Import

A Safe Division test used:

```python
pytest.raises(...)
```

without importing pytest.

This motivated the deterministic pytest-import safeguard.

## Scenario/Test Category Mismatch

A Username Length generation produced a category mismatch between the identified scenario and its generated test.

Earlier validation rejected the result and caused the request to fail.

Improvement 3 normalized the generated test category to the corresponding scenario.

## Hallucinated Function

During Improvement 3, the Order Discount evaluation generated tests that referenced:

```python
is_positive(...)
```

instead of the supplied function:

```python
apply_discount(...)
```

All five generated tests in that run failed.

This demonstrated that structural validation does not guarantee semantic grounding in the supplied source code.

## Local Model Inference Failure

One Safe Division Improvement 3 request failed during local Ollama inference because generation was aborted after reaching a token-repeat limit.

A single retry completed successfully.

This demonstrates that model inference reliability is another concern separate from test correctness.

---

# Evaluation Artifacts

Raw evaluation artifacts are stored under:

```text
evaluation/
```

The repository contains results from the baseline and three improvement stages.

File naming follows the general pattern:

```text
<requirement>_result.json
<requirement>_improved_result.json
<requirement>_improved2_result.json
<requirement>_improved3_result.json
```

Not every stage has a result file for every requirement.

In particular, no valid baseline Username Length result or Improvement 2 Username Length result was produced because those requests failed before a valid response artifact was available.

Missing result files should therefore **not** be interpreted as zero-test results.

---

# Reproducing the Evaluation

The recorded evaluation can be reproduced manually using the reference requirements under:

```text
evaluation/reference/
```

For each reference requirement:

1. Start Ollama.
2. Verify that `qwen3:4b` is installed.
3. Start the FastAPI backend.
4. Open the FastAPI documentation.
5. Select `POST /generate`.
6. Copy the `requirement` and `source_code` from the selected reference JSON file.
7. Execute the request.
8. Record the returned:
   - scenarios;
   - test cases;
   - generated pytest code; and
   - pytest result.
9. Compare the generated scenarios with the predefined `reference_scenarios`.

The final evaluation used **conservative substantive matching**: a generated scenario was counted as covering a reference scenario only when it represented the same underlying condition.

Scenario matching was reviewed manually; the repository does not currently contain an automated semantic comparison script.

Because the LLM is nondeterministic, reproducing a request may not produce exactly the same output as the stored evaluation artifact.

---

# Known Limitations

## LLM Nondeterminism

The model can produce different scenarios and tests across different runs.

The final evaluation records observed runs rather than enough repeated trials to statistically characterize model variability.

## Small Evaluation Dataset

The final benchmark contains four requirements and 21 reference scenarios.

The results should not be generalized to all software requirements or production systems.

## Semantic Correctness Is Not Guaranteed

Generated code can be syntactically valid and executable while still containing:

- incorrect expected values;
- unsupported assumptions;
- incomplete requirement coverage; or
- hallucinated source interfaces.

## Requirement vs. Implementation

The requirement is intended to define expected behavior while the source code provides the interface being tested.

There remains a risk that an LLM may derive an expected result from the implementation rather than the requirement, potentially reproducing an implementation defect in a generated test.

## Local Model Reliability

Local inference can fail independently of the quality of the requirement or source code.

## Test Execution Is Not Sandboxed

The system executes submitted Python source code together with generated test code.

The application is intended for **trusted local development and educational use only**.

Do not expose the current `/generate` endpoint to untrusted users or execute untrusted source code.

## Human Oversight Is Required

The current proof of concept should be used as an assistive tool.

Generated scenarios and tests should be reviewed by a developer or tester before being relied upon in a production software project.

---

# Future Work

Potential extensions include:

- AST-based validation of generated function calls against functions available in the supplied source;
- rejection and regeneration of tests that reference undefined functions;
- repeated evaluation trials to quantify LLM variability;
- a larger and more diverse requirement benchmark;
- automated scenario-to-reference comparison;
- comparison across different local and hosted models;
- additional code-coverage analysis;
- support for larger multi-function source modules;
- human review and editing workflows;
- stronger execution isolation or sandboxing; and
- CI integration for accepted generated tests.

A particularly important next step is **source-grounding validation**.

For example, the system could inspect generated test function calls using Python AST and verify that referenced functions exist in the supplied source before allowing the generated test to execute.

---

# External Tools and Dependencies

The project depends on the following external software:

- **Ollama** — local model runtime
- **Qwen3:4b** — local LLM
- **FastAPI** — API framework
- **Pydantic** — structured validation
- **pytest** — test execution

Python package versions used by the project are recorded in:

```text
backend/requirements.txt
```

No external dataset is required.

The evaluation benchmark was created specifically for this project and is included under:

```text
evaluation/reference/
```

---

# Responsible Use

AI-generated tests should not be assumed correct solely because they compile or pass.

Users should:

- review generated scenarios;
- inspect generated assertions;
- verify requirement alignment;
- verify referenced source interfaces;
- review failures;
- avoid executing untrusted code; and
- maintain human oversight before incorporating generated tests into a software project.

The project's evaluation demonstrates why these safeguards are necessary.

---

# Final Project Takeaway

The proof of concept demonstrates that a local LLM can generate useful test scenarios and executable pytest tests from natural-language requirements and Python source code.

Reference-scenario coverage increased from:

```text
28.6% at baseline
```

to as high as:

```text
66.7%
```

However, the experiments also exposed semantic hallucinations, structural generation failures, incomplete scenario coverage, and local-model inference instability.

The primary conclusion is:

> **AI can assist test generation, but reliable AI-assisted testing requires engineering and validation around the model—not just prompting it.**