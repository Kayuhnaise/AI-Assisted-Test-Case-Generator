# Project Specification

## AI-Assisted Requirement-to-Test Case Generator

**Course:** SWENG 889 — Fall I 2026

**Team Members:**
- Gulnar Aldasheva
- Samhitha Dwarakanath
- Keya Gangadharan

---

## 1. Purpose

The AI-Assisted Requirement-to-Test Case Generator is a proof-of-concept AI4SE system that assists software developers and testers in converting natural-language software requirements into structured test scenarios and executable pytest tests.

The system combines:

- natural-language requirement interpretation;
- source-code context;
- local LLM inference;
- structured test scenario generation;
- executable pytest generation;
- deterministic validation safeguards; and
- automated test execution.

The system is intended as an assistive development tool. AI-generated scenarios and tests require review before they are relied upon in a production software project.

---

## 2. Problem Statement

Software engineers must translate natural-language requirements into test scenarios and executable tests.

This process requires identifying:

- normal behavior;
- positive cases;
- negative cases;
- boundary conditions;
- edge cases; and
- appropriate expected results.

Important scenarios may be overlooked during manual test design.

The purpose of this proof of concept is to investigate whether a local LLM can assist with this process while preserving traceability from the original requirement to identified scenarios, generated tests, and test execution results.

---

## 3. Scope

### 3.1 In Scope

The proof of concept supports:

- natural-language software requirements;
- Python source code associated with a requirement;
- local LLM-based scenario identification;
- structured positive, negative, boundary, and edge scenarios when supported by the requirement;
- scenario-linked test-case generation;
- executable pytest generation;
- validation of generated structures;
- selected deterministic safeguards for known generation failures;
- automatic pytest execution;
- structured reporting of test execution results; and
- evaluation against manually defined reference scenarios.

### 3.2 Out of Scope

The current proof of concept does not provide:

- production-grade execution sandboxing;
- guaranteed semantic correctness of generated tests;
- automatic acceptance of generated tests into a production repository;
- automated semantic comparison between generated and reference scenarios;
- statistical characterization of model behavior across repeated trials;
- support for every programming language or test framework;
- testing of arbitrary external applications; or
- guaranteed protection against LLM hallucinations.

---

## 4. Intended Users and Stakeholders

Primary users include:

- software developers;
- QA engineers;
- software testers; and
- development teams evaluating AI-assisted testing workflows.

The system is designed to support human test-design activities rather than replace human review.

---

## 5. System Inputs

The primary `/generate` workflow accepts:

### Natural-Language Requirement

A textual statement describing expected software behavior.

Example:

```text
The system shall accept usernames between 3 and 20 characters long,
inclusive, and reject usernames outside that range.
```

### Python Source Code

Python code implementing the behavior associated with the requirement.

Example:

```python
def is_valid_username(username: str) -> bool:
    return 3 <= len(username) <= 20
```

---

## 6. System Outputs

The complete generation workflow returns:

- the original requirement;
- identified test scenarios;
- structured test cases;
- generated pytest code; and
- pytest execution results.

Execution results include information such as:

- execution status;
- exit code;
- number of tests executed;
- passed tests;
- failed tests;
- errors;
- skipped tests;
- stdout; and
- stderr.

---

# 7. Functional Requirements

## R1 — Requirement and Source Input

The system shall accept a natural-language software requirement and associated Python source code.

### Acceptance Criteria

- The API accepts both `requirement` and `source_code`.
- Valid input can be submitted through the FastAPI `/generate` endpoint.
- Invalid Python source is rejected before generated tests are executed.

---

## R2 — Scenario Identification

The system shall use the supplied requirement and source code to identify relevant testing scenarios.

Scenario categories may include:

- positive;
- negative;
- boundary; and
- edge.

### Acceptance Criteria

- `POST /scenarios` returns structured scenarios.
- Each scenario contains an ID.
- Each scenario contains a category.
- Each scenario contains a description.
- Scenario generation occurs before test generation in the `/generate` workflow.

---

## R3 — Scenario-Linked Test Generation

The system shall generate structured test cases corresponding to the identified scenarios.

### Acceptance Criteria

- Generated test cases contain a scenario identifier.
- Generated tests can be traced back to an identified scenario.
- The system attempts to produce one generated test case for each supplied scenario.
- Test-case output is validated against the application's structured data model.

---

## R4 — Executable pytest Generation

The system shall generate executable pytest test functions for identified scenarios.

### Acceptance Criteria

- Generated test code is valid Python before execution.
- Each generated test function follows pytest-compatible naming conventions.
- Generated test code is combined with the supplied source implementation.
- The resulting module can be submitted to pytest for execution.

---

## R5 — Generated-Output Validation and Safeguards

The system shall validate generated output before executing it.

### Acceptance Criteria

- Structured LLM responses are validated using Pydantic models.
- Generated Python is parsed before execution.
- Scenario/test relationships are validated.
- If generated test code references `pytest` without importing it, the system adds the required `pytest` import.
- If a generated test category differs from the corresponding scenario category, the scenario category is treated as the source of truth and the test category is normalized.

### Limitation

These safeguards validate known structural conditions and do not guarantee that generated assertions are semantically correct.

---

## R6 — Automated Test Execution

The system shall automatically execute generated pytest tests.

### Acceptance Criteria

- Generated tests are executed using pytest.
- Execution occurs with a bounded timeout.
- The execution result captures whether the generated test suite passed or failed.
- Test counts and execution output are returned to the caller.

---

## R7 — Structured API Response

The `/generate` endpoint shall return the artifacts produced by the complete generation and execution pipeline.

### Acceptance Criteria

A successful response contains:

- `requirement`;
- `scenarios`;
- `test_cases`;
- `pytest_code`; and
- `pytest_result`.

This allows the user to inspect both the AI-generated artifacts and the empirical execution result.

---

# 8. Non-Functional Requirements

## NFR1 — Local AI Execution

The system should support local LLM inference through Ollama.

The final proof of concept uses:

```text
Qwen3:4b
```

This avoids requiring a hosted LLM API for normal operation.

---

## NFR2 — Traceability

Generated tests should remain traceable to the scenarios from which they were produced.

This supports:

- debugging;
- evaluation;
- human review; and
- analysis of model failures.

---

## NFR3 — Reproducibility

The repository shall document:

- Python dependencies;
- local model requirements;
- installation steps;
- application startup;
- automated test execution; and
- evaluation procedures.

Because LLM generation is nondeterministic, reproducibility refers to reproducing the **experimental process**, not necessarily obtaining identical generated text on every run.

---

## NFR4 — Execution Safety

Generated code execution shall be treated as trusted local execution.

The current proof of concept does not provide a security sandbox.

The API should therefore not be exposed to untrusted users or used to execute untrusted source code.

---

## NFR5 — Human Oversight

Generated scenarios and tests shall be considered candidate software-engineering artifacts.

They should be reviewed before being incorporated into a production software project.

A successful pytest execution does not independently establish requirement correctness.

---

# 9. Primary Workflow

The primary system workflow is:

```text
Requirement + Python Source
          |
          v
     Input Validation
          |
          v
 Scenario Identification
          |
          v
 Scenario-Grounded
    Test Generation
          |
          v
 Structured Validation
          |
          v
 Deterministic Safeguards
          |
          v
 pytest Module Assembly
          |
          v
    pytest Execution
          |
          v
 Structured API Response
```

---

# 10. Proof-of-Concept Success Criteria

The proof of concept is considered functionally complete when the following capabilities are demonstrated:

- a user can submit a requirement and Python implementation;
- the system can identify structured test scenarios;
- the system can generate scenario-linked test cases;
- the system can generate pytest code;
- the generated code can be automatically executed;
- execution results are returned through the API;
- generated artifacts can be inspected by the user;
- known structural generation failures are validated or handled; and
- the system can support the evaluation procedure used in the final project.

The POC is not required to guarantee that every generated scenario or assertion is semantically correct.

---

# 11. Evaluation Acceptance Criteria

The final project evaluation shall include:

- a predefined reference benchmark;
- multiple requirements;
- reference scenarios defined independently of generated output;
- a recorded baseline;
- recorded improvement iterations;
- scenario-coverage analysis;
- generated-test execution results; and
- qualitative analysis of important failures.

The final benchmark contains:

```text
4 requirements
21 reference scenarios
```

Evaluation results are stored under:

```text
evaluation/
```

---

# 12. Known Constraints

The final proof of concept has the following constraints:

1. LLM output is nondeterministic.
2. The evaluation dataset is small.
3. Generated tests may be structurally valid but semantically incorrect.
4. The model may hallucinate functions or other source interfaces.
5. Local Ollama inference may occasionally fail.
6. Test execution is not sandboxed.
7. Scenario-to-reference comparison is currently performed manually.
8. Human review remains necessary.

---

# 13. Future Enhancements

Potential future improvements include:

- AST-based validation of generated function calls against the supplied source code;
- automatic rejection or regeneration of tests containing undefined source references;
- larger evaluation benchmarks;
- repeated evaluation trials;
- automated scenario-to-reference comparison;
- comparison across multiple LLMs;
- stronger test-execution isolation;
- additional code-coverage metrics; and
- integration of reviewed generated tests into CI/CD workflows.