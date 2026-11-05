# DB-TestGen: Automated Test Case Generation for Database Systems via LLM-Driven Requirement Parsing

**SWENG 889 — Fall I 2026**  
**Team:** Gulnar Aldasheva, Samhitha Dwarakanath, Keya Gangadharan  
**Project status:** November 5, 2026 — integrated R1→R2 generation and a review-gated PostgreSQL benchmark are implemented; new benchmark results have not yet been collected

## Overview

**DB-TestGen** is an AI for Software Engineering (AI4SE) proof of concept that translates natural-language database requirements into structured test scenarios and executable SQL tests. It separates **requirement interpretation (R1)** from **SQL test generation and validation (R2)** so that scenario coverage, test executability, and semantic correctness can be assessed independently.

The repository also preserves an earlier **Python/pytest requirement-to-test generator**, which uses local Ollama/Qwen3:4b. That earlier workflow and its historical evaluation are described in a separate section below; it should not be confused with the newer DBMS-focused evaluation.

The system is intended to support human developers and QA engineers, not replace expert judgment or provide a production-grade SQL sandbox.

## Current development status

| Component | Status as of November 5, 2026 | Purpose |
|---|---|---|
| R1 — DBMS scenario extraction | Implemented on `main` | Extract positive, negative, boundary, and edge-case scenarios from a plain-text or Markdown DBMS requirement document |
| R1 — Expert-scenario coverage | Implemented on `main`; DBMS coverage target not yet independently established here | Compare extracted scenarios against expert scenarios on preconditions, behavior, and expected results |
| R2 — Scenario-grounded SQL generation | Implemented and benchmarked on `main` | Generate traceable SQLite/PostgreSQL SQL test cases using Anthropic Claude |
| R2 — SQLite validation | Implemented and benchmarked | Execute SQL and verify expected outcomes and database-state assertions |
| R2 — PostgreSQL validation | Implemented and benchmarked | Execute reviewed SQL in a transaction with savepoint handling and rollback |
| Independent R2 benchmark oracles | Implemented | Evaluate generated tests against separately specified expert checks |
| Backend CI | Configured and reported passing | Run backend tests with a temporary PostgreSQL 17 service in GitHub Actions |
| Integrated R1 → R2 generation | Implemented | Extract scenarios and feed the same IDs directly into SQLite or PostgreSQL SQL generation |
| Repeated R1 → R2 benchmark | Implemented; not yet run | Record extraction, coverage, generation, reviewed PostgreSQL validation, and independent-oracle results per stage |
| PostgreSQL benchmark isolation | Implemented with documented limits | Run reviewed benchmark cases in disposable Docker containers, expose PostgreSQL only on localhost, and use a non-superuser role |

**Repository status:** Pull request [#3](https://github.com/Kayuhnaise/AI-Assisted-Test-Case-Generator/pull/3) merged the R2 benchmark and PostgreSQL support into `main`. The older feature branches were intermediate development branches and are not required to reproduce the current code.

## Problem and motivation

Deriving comprehensive database tests from requirements is labor-intensive. Test designers must identify ordinary and exceptional behavior, boundary conditions, data integrity constraints, required setup state, and the expected state after an operation. Requirements can become disconnected from tests, and a test that runs successfully is not necessarily a test that checks the right behavior.

DB-TestGen investigates whether LLMs can help generate scenario-traceable SQL tests while deterministic validation and independent expert oracles provide evidence about correctness. Its evaluation reports distinct measures rather than equating passing tests with full requirements coverage.

## DBMS system architecture

```text
Natural-language DBMS requirements (text/Markdown)
                        |
                        v
              R1: Scenario extraction
              (positive / negative /
                boundary / edge)
                        |
                        v
             Structured DBMS scenarios
      (ID, category, precondition, behavior,
                  expected result)
                        |
        Integrated generation API
                        |
                        v
            R2: Claude SQL generation
               (SQLite/PostgreSQL)
                        |
                        v
              Generated SQL test cases
   (setup, operation, assertions, outcome,
                   traceability)
                        |
                        v
         Schema/traceability validation
                        |
                        v
              Human SQL review
                        |
                        v
         Test execution and validation
        (isolated, disposable DB for PG)
                        |
                        v
          Results + independent oracle
```

`POST /dbms/pipeline/generate` connects document extraction to SQL generation and returns the original scenarios alongside generated test cases. It preserves scenario IDs and stops before execution so a human can review the generated SQL. The repeated benchmark script continues through expert-labeled coverage measurement and, after hash approval, PostgreSQL validation and an independent oracle. The benchmark implementation is available; no new end-to-end score is claimed until it has actually been run.

### R1: Requirement interpretation and scenario coverage

R1 reads a DBMS requirements document and extracts structured scenarios. Each `DBMSScenario` contains:

- `id` and `category` (`positive`, `negative`, `boundary`, or `edge`)
- `precondition`
- `behavior_under_test`
- `expected_result`

An expert-scenario coverage evaluator compares extracted and reference scenarios. Matching considers the precondition, behavior, and expected result, rather than relying only on similar wording. **At least 90% expert-scenario coverage is an evaluation target, not a demonstrated result in this README.**

### R2: SQL test generation and validation

R2 accepts a requirements document plus structured DBMS scenarios and generates one traceable SQL test case for each scenario. Tests include:

- test and source-scenario identifiers, title, and category;
- SQL dialect (`sqlite` or `postgresql`);
- preconditions and constraints;
- `setup_sql` statements and an executable `test_sql` operation;
- explicit verification queries and expected scalar or row results;
- expected outcome and optional cleanup statements.

The generation layer uses **Anthropic Claude**, with the model selectable through `CLAUDE_MODEL`. The recorded R2 evaluations used `claude-fable-5-1`. Generation includes Pydantic model validation, category and scenario-ID consistency checks, and retries for invalid structured output.

SQLite and PostgreSQL execution have different implementations. The PostgreSQL validator uses transaction rollback, savepoints for expected SQL errors, query timeouts, and state-verification assertions. Benchmark execution uses a fresh Docker PostgreSQL 17 container, a localhost-only published port, a temporary database, and a role without superuser, database-creation, or role-creation privileges. The standard Docker bridge may still allow outbound network access from the container, so this is not a network-isolated or general-purpose secure SQL sandbox. Review generated SQL and never use sensitive or production data.

## Technology stack

| Technology | Role |
|---|---|
| Python | Backend implementation and evaluation scripts |
| FastAPI | API endpoints for the original and DBMS workflows |
| Pydantic | Structured input/output and generated-test validation |
| Ollama + Qwen3:4b | Original Python test generator; local LLM workflows |
| Anthropic Python SDK / Claude | R2 SQL test generation and benchmark evaluation |
| SQLite | Local SQL test execution and benchmark validation |
| PostgreSQL 17 + psycopg 3 | PostgreSQL execution and integration-test database access |
| pytest | Automated backend regression tests |
| Docker | Disposable local PostgreSQL test instances |
| GitHub Actions | Backend CI with PostgreSQL service container |

**Model configuration differs by workflow:** the original Python proof of concept uses a local model; Claude-based SQL generation requires an Anthropic API key and access to the selected model.

## Repository layout

```text
AI-Assisted-Test-Case-Generator/
├── .github/workflows/tests.yml          # Backend CI with PostgreSQL service
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI endpoints
│   │   ├── models.py                    # Pydantic request/test schemas
│   │   ├── dbms_scenarios.py            # R1 extraction and coverage
│   │   ├── dbms_sql_generator.py        # R2 SQL generation
│   │   ├── dbms_sql_validator.py        # SQLite validation
│   │   ├── dbms_r2_oracle.py            # SQLite independent benchmark oracle
│   │   ├── dbms_postgres_executor.py    # PostgreSQL execution/validation
│   │   ├── dbms_postgres_oracle.py      # PostgreSQL independent oracle
│   │   ├── disposable_postgres.py       # Ephemeral PostgreSQL benchmark containers
│   │   ├── generator.py                 # Original Python test generator
│   │   └── test_runner.py              # Original pytest runner
│   ├── tests/
│   │   ├── fixtures/dbms_r2_benchmark.json
│   │   └── fixtures/dbms_r1_r2_supplemental.json
│   ├── benchmark_results/              # Recorded R2 JSON results
│   ├── evaluate_dbms_r2.py             # SQLite evaluation
│   ├── evaluate_dbms_r2_postgres.py    # PostgreSQL review/evaluation
│   ├── evaluate_dbms_r1_r2_postgres.py # Repeated integrated benchmark
│   └── requirements.txt
├── evaluation/
│   └── reference/                      # Original Python reference scenarios
└── README.md
```

This is a high-level map; consult the repository for the complete file list.

## API endpoints

Run FastAPI locally to access interactive documentation at `http://127.0.0.1:8000/docs`.

| Endpoint | Purpose | Current limitation |
|---|---|---|
| `GET /` | Basic API information | — |
| `GET /health` | Health check | — |
| `POST /scenarios` | Extract scenarios from a requirement and Python source code | Original Python workflow |
| `POST /generate` | Generate and run pytest tests from Python-oriented input | Original Python workflow; trusted local use only |
| `POST /dbms/scenarios` | Extract structured DBMS scenarios from a requirement document | Standalone R1 endpoint; use the pipeline endpoint for chained SQL generation |
| `POST /dbms/coverage` | Compare extracted DBMS scenarios to expert scenarios | Requires supplied expert and extracted scenario sets |
| `POST /dbms/generate` | Generate SQL tests from an explicitly supplied scenario list | Currently defaults to SQLite; PostgreSQL supported in Python R2 function/benchmark |
| `POST /dbms/pipeline/generate` | Extract scenarios and generate SQL tests in one request | Returns SQL for human review; does not execute it |
| `POST /dbms/validate` | Validate supplied SQL tests | Current API uses the SQLite validator; PostgreSQL validation is a separate Python workflow |

### Example: R1 scenario extraction

Request to `POST /dbms/scenarios`:

```json
{
  "requirement_document": "A product quantity must be between 1 and 100 inclusive. Inserts outside this range must be rejected."
}
```

R1 returns scenarios with identifiers, categories, preconditions, operations, and expected results. Use `POST /dbms/pipeline/generate` to pass those scenarios directly to SQL generation while preserving their identifiers. The endpoint returns `"review_required": true`; it does not execute generated SQL.

## Installation and local development

### Requirements

- Python and Git
- Dependencies from `backend/requirements.txt`
- Ollama and `qwen3:4b` **only** for local-model workflows
- `ANTHROPIC_API_KEY` and accessible `CLAUDE_MODEL` **for Claude-based R2 generation**
- Docker with PostgreSQL 17 **for PostgreSQL integration tests or local benchmark execution**

Clone and install:

```sh
git clone https://github.com/Kayuhnaise/AI-Assisted-Test-Case-Generator.git
cd AI-Assisted-Test-Case-Generator
cd backend
```

On macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For Claude SQL generation, configure environment variables in your own terminal or secrets manager; never commit API keys:

```powershell
$env:ANTHROPIC_API_KEY = "<your-api-key>"
$env:CLAUDE_MODEL = "claude-fable-5-1"
```

For the original local-model workflow:

```powershell
ollama pull qwen3:4b
```

Start the API:

```powershell
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

### Automated tests

From `backend/`:

```powershell
python -m pytest tests -q
```

The backend suite now reports **51 passed, 1 warning (November 5, 2026)**, including the integrated pipeline and savepoint regression tests. Some PostgreSQL integration tests require a reachable PostgreSQL test service and `DBTESTGEN_POSTGRES_URL`; a missing/stopped service causes connection-related failures and does not imply SQL generation is broken.

GitHub Actions starts a temporary PostgreSQL 17 service and initializes the `dbtestgen_sandbox` schema for those integration tests. The new benchmark evaluator starts its own disposable containers and does not use `DBTESTGEN_POSTGRES_URL`.

## Benchmark evaluation

### Current R2 SQL benchmark — November 4, 2026

The **12-scenario benchmark** comprises three positive, three negative, three boundary, and three edge cases, with expert-specified expected outcomes and verification checks.

| Database and model | Generated | Validation passed | Exact oracle metadata match | Independent validity |
|---|---:|---:|---:|---:|
| SQLite / Claude (`claude-fable-5-1`) | 12/12 | 12/12 | 12/12 | **12/12 (100%)** |
| PostgreSQL / Claude (`claude-fable-5-1`) | 12/12 | 12/12 | 10/12 | **12/12 (100%)** |

The PostgreSQL metadata mismatches occurred for **R2-006 and R2-012**, both foreign-key constraint cases. Execution validation and the independent state/outcome checks passed for both; the narrower metadata comparison used different error-string phrasing. A metadata match is not the same metric as an independently valid SQL test.

These findings describe a **small, iteratively refined, controlled benchmark**. They are not a controlled model comparison or an estimate of performance on arbitrary DBMS requirements. The SQLite and PostgreSQL scores also **do not establish R1 extraction coverage** or success of the combined R1→R2 workflow.

Recorded artifacts are available in `backend/benchmark_results/`, including:

- `dbms_r2_results_claude-fable-5-1_20261104T181658Z.json` — refined SQLite result;
- `postgres_review_20261104T200629Z.json` — generated PostgreSQL SQL prepared for review;
- `postgres_evaluation_20261104T200755Z.json` — evaluated PostgreSQL results.

Earlier Qwen-based R2 runs and intermediate Claude runs are also retained for historical comparison; differing prompt/benchmark refinements limit direct attribution of changes to the model alone.

### PostgreSQL benchmark execution safety

`backend/evaluate_dbms_r2_postgres.py` deliberately separates **generation** and **execution**:

1. Generate the SQL and write a `postgres_review_<timestamp>.json` file, without executing the SQL.
2. Manually review **all** setup statements, test operations, and verification queries.
3. Ensure Docker is running. Evaluation creates a disposable PostgreSQL 17 container with no host mounts, a localhost-only published port, and a temporary non-superuser SQL role. The standard Docker bridge may permit outbound network access.
4. Pass the exact reviewed file and its SHA-256 digest to the evaluation command; the script verifies the file hash before running the reviewed SQL.
5. Examine the result JSON; each temporary database container is removed after validation/oracle execution.

Example generation and approved evaluation commands from `backend/`:

```sh
python evaluate_dbms_r2_postgres.py
shasum -a 256 benchmark_results/postgres_review_<timestamp>.json
python evaluate_dbms_r2_postgres.py \
  --reviewed-file "benchmark_results/postgres_review_<timestamp>.json" \
  --approved-sha256 "<sha256-of-reviewed-file>"
```

The integrated benchmark includes 12 existing expert-labeled cases plus four supplemental cases covering cascading deletes, tenant-scoped uniqueness, savepoint rollback, and generated identity values. The R1 matcher compares each extraction with its expert-labeled scenario; generated SQL is stored for review before any PostgreSQL execution.

Run repeated trials from `backend/`:

```sh
python evaluate_dbms_r1_r2_postgres.py --trials 3
```

The script writes a `dbms_r1_r2_review_<timestamp>.json` artifact with per-case extraction, coverage, generation, and pending-review outcomes, then prints its SHA-256 digest. Review all generated `setup_sql`, `test_sql`, and verification assertions. For every generated entry, change `stages.review.status` from `"pending"` to `"approved"` or `"rejected"`; rejected entries need a non-empty `reason` and will not be executed. Only after approving that exact edited artifact, calculate/confirm its digest and run:

```sh
shasum -a 256 benchmark_results/dbms_r1_r2_review_<timestamp>.json
python evaluate_dbms_r1_r2_postgres.py \
  --reviewed-file "benchmark_results/dbms_r1_r2_review_<timestamp>.json" \
  --approved-sha256 "<sha256-of-reviewed-file>"
```

The resulting report includes per-stage outcomes and success rates, the review approval/rejection counts, R1 coverage against the 90% target, PostgreSQL validation outcomes, and independent-oracle results for expert-matched scenarios. Coverage failures count as uncovered scenarios. The benchmark is intentionally small and does not establish general model performance; independently inspect the expert labels and reported results.

**Do not run AI-generated SQL on a persistent project database or a system containing valuable data.** The Docker runner limits SQL privileges and resources, limits inbound access to localhost, and destroys the container after each test/oracle run. It does not block all outbound network access. Human review and disposable execution reduce risk, but neither makes arbitrary SQL execution risk-free.

## Historical Python/pytest proof of concept

The initial project generated pytest cases from natural-language requirements and supplied Python source code using local Ollama/Qwen3:4b. The pipeline included scenario identification, generated-test traceability, Pydantic and Python AST validation, a safeguard for missing `pytest` imports, category normalization, and bounded pytest execution. These Python-specific safeguards are separate from SQL generation and its PostgreSQL execution controls.

### Historical reference data

Four Python-oriented requirements contained **21 manually defined reference scenarios**:

| Requirement | Reference scenarios |
|---|---:|
| Account Lockout | 5 |
| Order Discount | 5 |
| Safe Division | 5 |
| Username Length | 6 |
| **Total** | **21** |

Reference scenarios and associated source code are in `evaluation/reference/`.

### Historical scenario coverage

| Stage | Reference scenario coverage |
|---|---:|
| Baseline | 6/21 (28.6%) |
| Improvement 1 | 14/21 (66.7%) |
| Improvement 2 | 7/21 (33.3%) |
| Improvement 3 | 14/21 (66.7%) |

Coverage was not monotonic. These results were obtained through historical manual substantive matching, **not** the newer DBMS scenario coverage endpoint.

### Historical execution results

| Stage | Successful pipeline runs | Passing generated pytest tests |
|---|---:|---:|
| Baseline | 3/4 | 8/8* |
| Improvement 1 | 4/4 | 14/16 |
| Improvement 2 | 3/4 | 9/10* |
| Improvement 3 | 4/4† | 10/15 |

`*` Excludes requirements for which no executable tests were produced.  
`†` A Safe Division attempt encountered a local Ollama inference failure; a retry succeeded.

### Lessons from the earlier evaluation

- The Account Lockout baseline missed an exact five-attempt boundary.
- One Order Discount run asserted an incorrect numerical result.
- Generated Safe Division tests sometimes referenced `pytest.raises` without importing `pytest`.
- A Username Length generation had a scenario/test-category mismatch.
- An Order Discount run hallucinated a function name, using `is_positive(...)` rather than the supplied `apply_discount(...)`.
- Ollama inference could fail independently of a requirement's validity.

A passing generated test is **not** evidence of full reference-scenario coverage or correct test semantics. The earlier experiments motivate independent verification in the DBMS-focused work.

## Limitations and responsible use

- **Small datasets:** The R2 SQL evaluation covers 12 scenarios; the historical Python benchmark contains 21 reference scenarios. Neither supports broad generalization.
- **Incomplete end-to-end evidence:** The integrated generation and review-gated evaluation workflow is implemented, but no R1→R2 benchmark trial has yet been reported.
- **R1 coverage target:** At least 90% coverage is a goal, not a substantiated achievement based on the R2 scores.
- **LLM variability:** Generation can vary between runs, and model/prompt refinements complicate comparisons.
- **Semantic risk:** Structurally valid tests can assert the wrong behavior or rely on unsupported assumptions.
- **Execution safety:** Neither the original Python executor nor the PostgreSQL SQL validator is a secure sandbox for untrusted input. Use only appropriately isolated, reviewed development artifacts.
- **Human oversight:** A developer or tester must evaluate requirements alignment, SQL statements, expected results, and failures before using generated tests.

## Next steps

1. **Run the integrated benchmark:** Execute at least three reviewed trials with `evaluate_dbms_r1_r2_postgres.py --trials 3` and report stage-specific failures.
2. **Establish R1 coverage:** Compare measured coverage on the 16 expert-labeled cases against the 90% target; review semantic matches and misses before treating the score as evidence.
3. **Broaden and audit the benchmark:** Add more independently reviewed requirements, especially transaction isolation, concurrency, permissions, and recovery scenarios, with repeated trials and independent oracles.
4. **Review isolation limits:** Evaluate outbound-network restrictions and stronger container policies before using the runner with higher-risk SQL; the current disposable container is not a formal security boundary.

## Project takeaway

The historical R2 results show high independent validity on a small controlled benchmark when generation is paired with structural validation, executable assertions, expert-defined checks, and human review. The integrated R1→R2 workflow is now implemented, but its reliability and R1 coverage remain unmeasured until the new benchmark is run and independently reviewed.
