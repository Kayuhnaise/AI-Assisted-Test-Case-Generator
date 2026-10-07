# System Architecture

## AI-Assisted Requirement-to-Test Case Generator

This document describes the final architecture of the AI-Assisted Requirement-to-Test Case Generator proof of concept.

The system uses a two-stage local LLM workflow to transform a natural-language software requirement and associated Python source code into structured testing scenarios, executable pytest tests, and test execution results.

---

## 1. Architecture Overview

The system follows the following high-level workflow:

```text
+--------------------------------+
| Natural-Language Requirement   |
| + Python Source Code           |
+---------------+----------------+
                |
                v
+--------------------------------+
| FastAPI API                    |
| POST /generate                 |
| POST /scenarios                |
+---------------+----------------+
                |
                v
+--------------------------------+
| Input / Schema Validation      |
| Pydantic                       |
+---------------+----------------+
                |
                v
+--------------------------------+
| Stage 1: Scenario              |
| Identification                 |
+---------------+----------------+
                |
                v
+--------------------------------+
| Ollama + Qwen3:4b              |
+---------------+----------------+
                |
                v
+--------------------------------+
| Structured Scenarios           |
| - Positive                     |
| - Negative                     |
| - Boundary                     |
| - Edge                         |
+---------------+----------------+
                |
                v
+--------------------------------+
| Stage 2: Test Case Generation  |
+---------------+----------------+
                |
                v
+--------------------------------+
| Ollama + Qwen3:4b              |
+---------------+----------------+
                |
                v
+--------------------------------+
| Structured Test Cases          |
| + pytest Functions             |
+---------------+----------------+
                |
                v
+--------------------------------+
| Validation & Safeguards        |
| Pydantic + Python AST          |
+---------------+----------------+
                |
                v
+--------------------------------+
| pytest Module Assembly         |
+---------------+----------------+
                |
                v
+--------------------------------+
| Bounded pytest Execution       |
+---------------+----------------+
                |
                v
+--------------------------------+
| Structured API Response        |
| - Scenarios                    |
| - Test Cases                   |
| - pytest Code                  |
| - Execution Results            |
+--------------------------------+
```

---

# 2. Major Components

## 2.1 FastAPI Application

Primary file:

```text
backend/app/main.py
```

FastAPI provides the external interface to the proof of concept.

The primary endpoints are:

### `POST /scenarios`

Runs only the scenario-identification stage.

This endpoint accepts:

- a natural-language requirement; and
- associated Python source code.

It returns the structured scenarios identified by the LLM.

### `POST /generate`

Runs the complete pipeline:

```text
Input
  -> Scenario Identification
  -> Test Generation
  -> Validation
  -> pytest Execution
  -> Response
```

Additional endpoints include:

```text
GET /
GET /health
```

These provide basic application and health information.

---

## 2.2 Data Models and Validation

Primary file:

```text
backend/app/models.py
```

Pydantic models define the structured data exchanged throughout the system.

They are used to validate:

- incoming API requests;
- identified scenarios;
- generated test cases;
- API responses; and
- pytest execution results.

Structured schemas are also used to constrain LLM responses.

This reduces the likelihood that free-form model output will be passed directly into later stages of the application.

---

## 2.3 Prompt Definitions

Primary file:

```text
backend/app/prompts.py
```

This module contains the instructions supplied to the local LLM.

Prompting is used for two distinct tasks:

1. scenario identification;
2. test-case and pytest generation.

Separating these tasks was an intentional architectural decision.

Rather than asking the model to interpret a requirement and immediately produce tests in a single step, the application first produces explicit scenarios.

Those scenarios then become inputs to the test-generation stage.

---

# 3. Two-Stage LLM Architecture

## Stage 1 — Scenario Identification

The first LLM stage receives:

```text
Natural-Language Requirement
+
Python Source Code
```

The model identifies testing conditions that may include:

- positive scenarios;
- negative scenarios;
- boundary scenarios; and
- edge scenarios.

The output is structured and validated before it is used by the next stage.

Conceptually:

```text
Requirement + Source
        |
        v
 Scenario Prompt
        |
        v
    Qwen3:4b
        |
        v
Structured Scenarios
```

---

## Stage 2 — Test Generation

The second LLM stage receives:

- the original requirement;
- the supplied source code; and
- the structured scenarios from Stage 1.

It generates scenario-linked test cases and pytest functions.

Conceptually:

```text
Requirement
   +
Source Code
   +
Scenarios
   |
   v
Test Generation Prompt
   |
   v
Qwen3:4b
   |
   v
Structured Test Cases
+
pytest Functions
```

This architecture provides explicit traceability between scenario identification and executable test generation.

It also makes failure analysis easier.

For example, the evaluation can distinguish between:

- a relevant scenario that was never identified; and
- a correctly identified scenario that resulted in an incorrect generated test.

---

# 4. Generation and Validation Component

Primary file:

```text
backend/app/generator.py
```

The generator coordinates communication with Ollama and performs validation of generated artifacts.

Its responsibilities include:

- requesting scenario generation;
- requesting test generation;
- parsing structured LLM output;
- validating generated Python;
- maintaining scenario-to-test traceability; and
- applying deterministic safeguards.

---

# 5. Deterministic Safeguards

One of the main engineering lessons from the project was that prompt instructions alone were insufficient to prevent all generation failures.

Improvement 3 therefore introduced deterministic safeguards around selected model outputs.

## 5.1 Missing pytest Import

During evaluation, the LLM generated a test containing:

```python
pytest.raises(...)
```

without:

```python
import pytest
```

This caused an otherwise relevant test to fail with a `NameError`.

The final system parses generated code using Python AST.

If the generated code uses the `pytest` name without importing pytest, the system adds:

```python
import pytest
```

before execution.

---

## 5.2 Scenario Category Normalization

Another observed failure involved a mismatch between:

```text
scenario.category
```

and:

```text
test_case.test_type
```

Earlier validation treated this mismatch as an error and terminated the request.

In the final implementation, the identified scenario is treated as the source of truth.

If the generated test category differs, the application normalizes the generated test category to the corresponding scenario category.

---

## 5.3 Safeguard Boundary

The safeguards deliberately address known **structural** failures.

They do not silently rewrite the semantic meaning of a generated assertion.

For example, during the final evaluation, generated Order Discount tests referenced:

```python
is_positive(...)
```

instead of the supplied:

```python
apply_discount(...)
```

The existing safeguards did not correct this hallucination.

This distinction is intentional:

```text
Structural validation
        !=
Semantic correctness
```

A future version could add AST-based source-grounding validation to detect calls to functions that do not exist in the supplied implementation.

---

# 6. pytest Execution

Primary file:

```text
backend/app/test_runner.py
```

Generated tests are not merely returned as text.

The application assembles the supplied Python source code and generated pytest functions into an executable module.

The module is then executed using pytest.

The execution process is bounded by a timeout to prevent an indefinitely running generated test process.

The application captures structured execution information including:

- status;
- exit code;
- tests run;
- tests passed;
- tests failed;
- errors;
- skipped tests;
- standard output; and
- standard error.

The execution result becomes part of the `/generate` response.

---

# 7. End-to-End Data Flow

A typical `/generate` request follows this sequence:

```text
1. User submits requirement and source code
                     |
                     v
2. FastAPI receives request
                     |
                     v
3. Pydantic validates request structure
                     |
                     v
4. Scenario-identification prompt is created
                     |
                     v
5. Qwen3:4b identifies scenarios
                     |
                     v
6. Scenario output is parsed and validated
                     |
                     v
7. Requirement + source + scenarios are
   passed to test generation
                     |
                     v
8. Qwen3:4b generates structured tests
                     |
                     v
9. Generated tests are validated
                     |
                     v
10. Deterministic safeguards are applied
                     |
                     v
11. pytest module is assembled
                     |
                     v
12. Generated tests are executed
                     |
                     v
13. Execution results are parsed
                     |
                     v
14. Complete structured response is returned
```

---

# 8. Local LLM Architecture

The system uses:

```text
Ollama
  |
  v
Qwen3:4b
```

The LLM runs locally rather than through a hosted model API.

## Advantages

The local architecture:

- avoids requiring external AI API credentials;
- keeps requirement and source-code processing local;
- provides direct control over the model environment; and
- supports experimentation without per-request hosted API costs.

## Trade-Offs

The evaluation also demonstrated trade-offs:

- inference can be slower than hosted services;
- smaller local models may have weaker reasoning capabilities;
- output remains nondeterministic;
- local hardware affects model availability and performance; and
- local inference itself can fail.

One recorded evaluation run failed when Ollama aborted generation after reaching a token-repeat limit.

---

# 9. Evaluation Architecture

Evaluation artifacts are stored under:

```text
evaluation/
```

Reference scenarios are stored under:

```text
evaluation/reference/
```

The benchmark contains:

```text
4 requirements
21 reference scenarios
```

The evaluation compares generated scenarios against these manually defined reference scenarios.

The system was evaluated across:

```text
Baseline
Improvement 1
Improvement 2
Improvement 3
```

The evaluation separates:

```text
Scenario Coverage
Pipeline Reliability
Test Executability
Test Correctness
Failure Analysis
```

This separation is important because a generated test can execute successfully without adequately representing the original requirement.

---

# 10. Security Boundary

The current system executes:

```text
User-Supplied Python Source
+
AI-Generated Python Tests
```

The execution environment is not a security sandbox.

Therefore, the current architecture is intended only for trusted local or educational use.

The `/generate` endpoint should not be exposed to untrusted users in its current form.

A production architecture would require stronger isolation, such as a dedicated sandbox or isolated execution environment.

---

# 11. Key Architecture Decisions

## Decision 1 — Local LLM

**Decision:** Use Ollama with Qwen3:4b.

**Reason:** Enable a fully local proof of concept without requiring a hosted LLM API.

**Trade-off:** Local execution provides control but introduces hardware constraints and local-model reliability limitations.

---

## Decision 2 — Two-Stage Generation

**Decision:** Separate scenario identification from test generation.

**Reason:** Improve traceability and allow the evaluation to distinguish scenario-generation failures from test-generation failures.

---

## Decision 3 — Structured Model Output

**Decision:** Constrain and validate model responses using structured Pydantic models.

**Reason:** Reduce reliance on unrestricted free-form LLM output and make downstream processing predictable.

---

## Decision 4 — Execute Generated Tests

**Decision:** Run generated pytest code rather than evaluating generated text alone.

**Reason:** Executability is an important dimension of generated-test usefulness.

**Trade-off:** Passing tests do not establish semantic correctness.

---

## Decision 5 — Deterministic Safeguards Around LLM Output

**Decision:** Add deterministic handling for known structural generation problems.

**Reason:** Prompt engineering alone did not consistently prevent these errors.

**Trade-off:** Narrow safeguards solve known structural problems but cannot guarantee semantic correctness.

---

# 12. Future Architecture Improvements

Future versions could extend the architecture with:

```text
Generated pytest
      |
      v
AST Source-Grounding Validator
      |
      +---- Valid ----> Execute
      |
      +---- Invalid --> Reject / Regenerate
```

Potential improvements include:

- validating generated function calls against supplied source definitions;
- automatically regenerating structurally or semantically invalid tests;
- isolated test-execution environments;
- automated reference-scenario comparison;
- repeated-run evaluation tooling;
- support for larger source modules;
- multiple-model comparison; and
- integration of reviewed generated tests into CI/CD workflows.

---

# 13. Architecture Summary

The final proof of concept combines probabilistic AI generation with deterministic software-engineering controls.

The core architecture can be summarized as:

```text
Requirement + Source
        |
        v
        AI
 Scenario Identification
        |
        v
        AI
   Test Generation
        |
        v
 Deterministic Validation
        |
        v
 Automated Execution
        |
        v
 Human-Reviewable Evidence
```

The project evaluation showed why all of these layers are necessary.

The LLM can assist with scenario and test generation, but reliable AI-assisted testing requires validation, execution, traceability, and human oversight around the model.