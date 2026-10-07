# Evaluation Artifacts

## Overview

This directory contains the evaluation benchmark and recorded results for the **AI-Assisted Requirement-to-Test Case Generator**.

The evaluation investigated the following question:

> To what extent can a local LLM generate relevant, executable pytest tests from natural-language requirements and Python source code, and how do prompt and validation improvements affect the quality and reliability of those tests?

The evaluation was performed across four requirements and four development stages:

1. Baseline
2. Improvement 1
3. Improvement 2
4. Improvement 3

The evaluation considers multiple dimensions rather than treating generated-test pass rate as the only measure of quality.

These dimensions include:

- reference-scenario coverage;
- pipeline reliability;
- generated-test executability;
- generated-test correctness and source grounding; and
- qualitative failure analysis.

---

## Reference Benchmark

The `reference/` directory contains four manually defined evaluation requirements.

| Requirement | Reference Scenarios |
|---|---:|
| Account Lockout | 5 |
| Order Discount | 5 |
| Safe Division | 5 |
| Username Length | 6 |
| **Total** | **21** |

Each reference JSON file contains:

- the natural-language requirement;
- the corresponding Python source code;
- manually defined reference scenarios; and
- notes explaining non-obvious cases where applicable.

The files are:

```text
reference/
├── account_lockout.json
├── order_discount.json
├── safe_division.json
└── username_length.json
```

These 21 reference scenarios form the benchmark used for the reported scenario-coverage results.

---

## Evaluation Stages

### Baseline

The baseline represents the initial working requirement-to-test generation pipeline.

It established the initial behavior of:

- scenario identification;
- structured test generation;
- pytest-code generation; and
- automatic test execution.

### Improvement 1

Improvement 1 focused primarily on improving scenario and test coverage.

Observed improvements included better identification of important boundary conditions, such as the exact Account Lockout threshold.

The evaluation also revealed additional semantic and executability problems, including an incorrect expected numeric value and a missing pytest import.

### Improvement 2

Improvement 2 strengthened the **test-generation prompt**.

Additional instructions addressed:

- required imports;
- one test per supplied scenario;
- scenario IDs and categories;
- requirement-first expected behavior;
- unsupported behavior;
- numeric calculations;
- use of `pytest.approx` when appropriate; and
- generated-code executability.

These changes did not modify the scenario-identification prompt.

Because LLM generation is nondeterministic, stronger prompting did not result in uniformly better evaluation results.

### Improvement 3

Improvement 3 added deterministic safeguards for structural failures observed during earlier evaluations.

The two primary safeguards were:

1. **Missing pytest import detection**

   Generated test code is parsed using Python AST. If the code references `pytest` without importing it, the system adds:

   ```python
   import pytest
   ```

2. **Scenario/test category normalization**

   If a generated test-case category differs from the category of its corresponding identified scenario, the scenario is treated as the source of truth and the test category is normalized.

These safeguards address specific structural failures.

They do **not** automatically correct semantic hallucinations or incorrect assertions.

---

## Result File Naming

Evaluation results use the following naming convention:

```text
<requirement>_result.json
<requirement>_improved_result.json
<requirement>_improved2_result.json
<requirement>_improved3_result.json
```

These correspond to:

| Filename Pattern | Evaluation Stage |
|---|---|
| `_result.json` | Baseline |
| `_improved_result.json` | Improvement 1 |
| `_improved2_result.json` | Improvement 2 |
| `_improved3_result.json` | Improvement 3 |

For example:

```text
account_lockout_result.json
account_lockout_improved_result.json
account_lockout_improved2_result.json
account_lockout_improved3_result.json
```

represent the four recorded Account Lockout evaluation stages.

---

## Intentionally Missing Result Files

Not every requirement has a valid result file for every evaluation stage.

### Username Length — Baseline

There is no:

```text
username_length_result.json
```

The baseline request ended with an HTTP 500 error before a valid response artifact was produced.

### Username Length — Improvement 2

There is no:

```text
username_length_improved2_result.json
```

During Improvement 2, scenario identification completed, but generated test validation detected a category mismatch between a generated test and its corresponding scenario.

The request therefore ended with an HTTP 500 error before pytest execution and before a valid result JSON could be saved.

These missing files should **not** be interpreted as zero-test or zero-coverage result files. They represent pipeline failures.

---

# Evaluation Results

## Reference-Scenario Coverage

Generated scenarios were manually compared against the 21 predefined reference scenarios.

A generated scenario was counted as covering a reference scenario when it represented the same substantive testing condition, even if the wording or scenario category differed.

Matching was performed conservatively.

| Requirement | Reference | Baseline | Improvement 1 | Improvement 2 | Improvement 3 |
|---|---:|---:|---:|---:|---:|
| Account Lockout | 5 | 2/5 | 3/5 | 3/5 | 3/5 |
| Order Discount | 5 | 2/5 | 5/5 | 2/5 | 4/5 |
| Safe Division | 5 | 2/5 | 2/5 | 2/5 | 3/5 |
| Username Length | 6 | 0/6* | 4/6 | 0/6* | 4/6 |
| **Overall** | **21** | **6/21** | **14/21** | **7/21** | **14/21** |
| **Coverage** | **100%** | **28.6%** | **66.7%** | **33.3%** | **66.7%** |

`*` The pipeline failed before a usable result was produced.

Reference-scenario coverage therefore increased from **28.6% at baseline to as high as 66.7%**, although performance was not monotonic across iterations.

---

## Generated-Test Execution

| Requirement | Baseline | Improvement 1 | Improvement 2 | Improvement 3 |
|---|---:|---:|---:|---:|
| Account Lockout | 3/3 | 4/4 | 3/4 | 2/2 |
| Order Discount | 3/3 | 5/6 | 3/3 | 0/5 |
| Safe Division | 2/2 | 1/2 | 3/3 | 4/4† |
| Username Length | HTTP 500 | 4/4 | HTTP 500 | 4/4 |

`†` The first Safe Division Improvement 3 attempt failed during local Ollama inference. A single retry completed successfully and produced the recorded 4/4 result.

---

## Combined Summary

| Stage | Scenario Coverage | Successful Pipeline Runs | Passing Generated Tests |
|---|---:|---:|---:|
| Baseline | 6/21 (28.6%) | 3/4 | 8/8* |
| Improvement 1 | 14/21 (66.7%) | 4/4 | 14/16 |
| Improvement 2 | 7/21 (33.3%) | 3/4 | 9/10* |
| Improvement 3 | 14/21 (66.7%) | 4/4† | 10/15 |

`*` Excludes requirements where the pipeline failed before executable tests were produced.

`†` Safe Division Improvement 3 required one retry following a local Ollama inference failure.

---

# Important Failure Examples

## 1. Missing Exact Boundary

The baseline Account Lockout result did not identify the exact threshold of five failed attempts.

Later iterations identified the threshold correctly.

This demonstrated that a generated test suite can execute successfully while still missing an important requirement condition.

---

## 2. Incorrect Expected Value

During Improvement 1, an Order Discount test involving a very large numeric input generated an incorrect expected discounted value.

The test was structurally valid but semantically incorrect.

This demonstrated that Python syntax validation and pytest execution alone cannot guarantee test correctness.

---

## 3. Missing `pytest` Import

During Improvement 1, a Safe Division test generated:

```python
with pytest.raises(ValueError):
```

without importing `pytest`.

The result was a `NameError`.

This failure motivated the deterministic pytest-import safeguard introduced in Improvement 3.

---

## 4. Category Mismatch

During Improvement 2, Username Length generation produced a test whose category did not match the category of its corresponding scenario.

Validation correctly detected the inconsistency, but the pipeline terminated before pytest execution.

Improvement 3 changed this behavior by normalizing the generated test category to the source scenario category.

---

## 5. Semantic / Source-Grounding Hallucination

During Improvement 3, the Order Discount run generated five tests that referenced:

```python
is_positive(...)
```

instead of the actual supplied function:

```python
apply_discount(...)
```

All five generated tests failed with a `NameError`.

This is an important remaining limitation.

The deterministic safeguards introduced in Improvement 3 corrected known structural problems but did not guarantee that generated tests remained semantically grounded in the supplied source code.

---

## 6. Local LLM Inference Failure

The first Safe Division Improvement 3 attempt failed during scenario generation because Ollama aborted generation after reaching a token-repeat limit.

No test-generation safeguard could prevent this because the failure occurred during LLM inference before test generation.

A single retry completed successfully and produced four passing tests.

This failure demonstrates that **model inference reliability** should be considered separately from test quality.

---

# Interpreting the Results

The evaluation should not be interpreted as showing that each improvement was uniformly better than the previous stage.

LLM generation is nondeterministic, and the number and content of generated scenarios changed between runs.

For example:

- Baseline produced 8/8 passing executable tests but covered only 28.6% of the reference scenarios.
- Improvement 1 increased reference-scenario coverage to 66.7%.
- Improvement 2 introduced stronger prompting but coverage fell to 33.3% in the recorded runs.
- Improvement 3 again achieved 66.7% coverage, but the Order Discount run contained a semantic hallucination that caused all five generated tests to fail.

Therefore, **pytest pass rate should not be treated as a standalone measure of AI-generated test quality**.

The project evaluates generated output across multiple dimensions.

---

# Main Evaluation Conclusion

The recorded experiments support the following conclusion:

> Iterative prompt and validation improvements increased reference-scenario coverage from 28.6% at baseline to as high as 66.7%, but performance varied substantially between runs. Deterministic safeguards resolved specific structural failures, while semantic hallucinations and model inference instability remained unresolved.

The results indicate that a local LLM can assist with generating useful software test scenarios and executable pytest tests, but reliable use requires software-engineering validation around the model and continued human oversight.

---

# Reproducing the Evaluation

To reproduce an evaluation run:

1. Install and start Ollama.
2. Ensure `qwen3:4b` is installed.
3. Start the FastAPI backend.
4. Open:

   ```text
   http://127.0.0.1:8000/docs
   ```

5. Select `POST /generate`.
6. Open one of the files under:

   ```text
   evaluation/reference/
   ```

7. Copy its `requirement` and `source_code` into the request.
8. Execute the request.
9. Record the returned:
   - scenarios;
   - test cases;
   - pytest code; and
   - pytest result.
10. Compare the generated scenarios with the file's predefined `reference_scenarios`.

Because Qwen3:4b generation is nondeterministic, a new run may not exactly reproduce the stored JSON result.

The stored JSON files should therefore be treated as the **recorded experimental artifacts used for the final project evaluation**.