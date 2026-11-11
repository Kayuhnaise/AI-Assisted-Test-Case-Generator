# DB-TestGen: Automated Test Case Generation for Database Systems via LLM-Driven Requirement Parsing

**SWENG 889 — Fall I 2026**  
**Team:** Gulnar Aldasheva, Samhitha Dwarakanath, Keya Gangadharan  
**Project status:** November 6, 2026 — integrated R1→R2 pipeline, optional Claude-based R1 extraction, PostgreSQL validation, and additional benchmark artifacts available on `feature/r1-integration`.

## Overview

**DB-TestGen** is an AI for Software Engineering (AI4SE) proof of concept that converts natural-language database requirements into structured test scenarios and executable SQL tests. It separates **requirement interpretation (R1)** from **SQL test generation and validation (R2)** so that scenario coverage, executability, and semantic correctness can be assessed independently.

The repository also retains an earlier Python/pytest requirement-to-test generator using local Ollama/Qwen3:4b. Its historical results are reported separately below. DB-TestGen is a research prototype designed to support human developers and QA engineers, **not** a production-grade SQL sandbox.

## Current development status

| Component | Status | Purpose |
|---|---|---|
| R1 scenario extraction | Implemented | Extract positive, negative, boundary, and edge scenarios from text or Markdown requirements |
| Requirement-aware chunking and truncation recovery | Implemented | Process larger requirements and recover from truncated model responses |
| Claude R1 extraction | Implemented on `feature/r1-integration` | Select Claude instead of Ollama through the integrated pipeline |
| R1 expert-reference coverage | Implemented and evaluated | Compare extracted scenarios with expert-defined scenarios; separate experimental semantic evaluator available |
| R2 SQL generation | Implemented | Generate traceable SQLite or PostgreSQL SQL tests with Claude |
| SQLite validation and independent oracle | Implemented and benchmarked | Check execution, expected outcomes, and state assertions |
| PostgreSQL validation and independent oracle | Implemented and benchmarked | Run reviewed tests with rollback/savepoint handling and independent checks |
| Integrated R1→R2 API | Implemented | Extract scenarios and generate SQL tests while preserving scenario IDs |
| Review-gated repeated benchmark | Implemented; further repeated trials needed | Track extraction, coverage, generation, review, execution, and independent-oracle outcomes |
| Backend regression tests | 89 passed locally | Automated verification of backend functionality |
| Backend CI | Configured | GitHub Actions with temporary PostgreSQL 17 service |


## Problem and motivation

Deriving comprehensive database tests from requirements is labor-intensive. Test designers must identify normal and exceptional behavior, boundary conditions, integrity constraints, setup state, and expected database state after operations. A test can execute successfully while checking the wrong behavior, and generated tests may miss required scenarios entirely.

DB-TestGen investigates whether LLMs can generate scenario-traceable SQL tests while deterministic execution and independent expert oracles provide evidence of correctness. The project reports **coverage**, **test execution**, and **semantic validity** separately rather than treating a passing test as proof of full requirements coverage.

## DBMS system architecture

```text
Natural-language DBMS requirements (text/Markdown)
                         |
                         v
            R1: Requirement interpretation
          + requirement-aware chunking
          + truncation recovery (Ollama path)
          + Ollama or Claude extraction
                         |
                         v
             Structured DBMS scenarios
        (ID, category, precondition, behavior,
                  expected result)
                         |
             Optional expert coverage
             and semantic assessment
                         |
                         v
                R2: Claude SQL generation
                   (SQLite/PostgreSQL)
                         |
                         v
                  Generated SQL tests
          (setup, operation, assertions,
                 expected outcome)
                         |
                         v
              Schema and ID validation
                         |
                         v
                  Human SQL review
                         |
                         v
              Database test execution
           (SQLite or disposable PostgreSQL)
                         |
                         v
              Independent expert oracle
                         |
                         v
                Per-stage evaluation
```

`POST /dbms/pipeline/generate` chains R1 extraction and R2 SQL generation. The endpoint returns the original scenarios and generated SQL tests for review; **it does not execute generated SQL**. The repeated benchmark script supports a separate review-and-approval stage before PostgreSQL execution.

### R1: Requirement interpretation

Each extracted `DBMSScenario` includes:

- `id` and `category` (`positive`, `negative`, `boundary`, or `edge`)
- `precondition`
- `behavior_under_test`
- `expected_result`

The pipeline supports `r1_provider: "ollama"` (default) or `r1_provider: "claude"`. The Ollama extraction path includes requirement-aware chunking and truncated-output recovery. The standalone `/dbms/scenarios` endpoint uses the default R1 implementation.

Expert-scenario coverage compares extracted scenarios with reference scenarios based on preconditions, behavior, and expected outcomes. An additional **experimental Claude semantic coverage evaluator** is available; its automated judgments should not be conflated with the manually audited benchmark results.

### R2: SQL test generation

R2 uses Anthropic Claude to generate scenario-grounded SQL test cases. Each test includes a test identifier, source-scenario identifier, category, dialect, setup statements, test operation, verification queries, expected results, and optional cleanup. Pydantic validation and consistency checks detect malformed output and mismatched scenario IDs or categories.

SQLite tests can be executed locally. PostgreSQL tests use transaction rollback, savepoints for expected errors, timeouts, and database-state assertions. Benchmark PostgreSQL execution uses a disposable Docker PostgreSQL 17 instance, a localhost-only published port, and a non-superuser role. **This is not a general-purpose secure SQL sandbox:** the Docker bridge may permit outbound traffic. Generated SQL must be reviewed and must never be run against production or sensitive databases.

## Technology stack

| Technology | Role |
|---|---|
| Python | Backend and evaluation scripts |
| FastAPI | HTTP API |
| Pydantic | Structured schemas and validation |
| Ollama / Qwen3:4b | Local R1 and historical Python test generation |
| Anthropic Python SDK / Claude | Optional R1 extraction, experimental semantic coverage, and R2 generation |
| SQLite | Local SQL execution and validation |
| PostgreSQL 17 / psycopg 3 | PostgreSQL test execution and independent checks |
| pytest | Automated backend regression tests |
| Docker | Disposable PostgreSQL benchmark instances |
| GitHub Actions | Backend CI with PostgreSQL service |

## Repository layout

```text
AI-Assisted-Test-Case-Generator/
├── .github/workflows/tests.yml
├── backend/
│   ├── app/
│   │   ├── main.py                       # FastAPI endpoints
│   │   ├── models.py                     # Request/response schemas
│   │   ├── dbms_scenarios.py             # R1 extraction and coverage
│   │   ├── dbms_chunking.py              # Requirement-aware chunking
│   │   ├── dbms_scenarios_claude.py      # Claude R1 extraction
│   │   ├── dbms_coverage_claude.py       # Experimental semantic evaluator
│   │   ├── dbms_sql_generator.py         # R2 SQL generation
│   │   ├── dbms_sql_validator.py         # SQLite validation
│   │   ├── dbms_r2_oracle.py             # SQLite independent oracle
│   │   ├── dbms_postgres_executor.py     # PostgreSQL execution
│   │   ├── dbms_postgres_oracle.py       # PostgreSQL independent oracle
│   │   ├── disposable_postgres.py        # Ephemeral PostgreSQL containers
│   │   ├── generator.py                  # Original Python test generator
│   │   └── test_runner.py               # Original pytest runner
│   ├── tests/
│   │   └── fixtures/
│   │       ├── dbms_r2_benchmark.json
│   │       ├── dbms_r1_r2_supplemental.json
│   │       └── external/                # Library Management SRS/reference
│   ├── benchmark_results/               # Saved R1/R2 and demo artifacts
│   ├── evaluate_dbms_r2.py              # SQLite R2 evaluation
│   ├── evaluate_dbms_r2_postgres.py     # PostgreSQL R2 evaluation
│   ├── evaluate_dbms_r1_r2_postgres.py  # Integrated benchmark
│   ├── evaluate_library_r1_claude.py    # Library Management R1 evaluation
│   ├── evaluate_library_r2_claude.py    # Library Management R2 evaluation
│   ├── validate_library_r2_postgres.py  # PostgreSQL verification
│   └── requirements.txt
├── evaluation/reference/                 # Historical Python references
└── README.md
```

This is a high-level map, not an exhaustive inventory.

## API endpoints

Start the API and open `http://127.0.0.1:8000/docs` for the interactive OpenAPI documentation.

| Endpoint | Purpose | Notes |
|---|---|---|
| `GET /` | API information | — |
| `GET /health` | Health check | — |
| `POST /scenarios` | Original Python scenario extraction | Python-oriented workflow |
| `POST /generate` | Original Python pytest generation/execution | Trusted local use only |
| `POST /dbms/scenarios` | Standalone R1 scenario extraction | Default R1 path |
| `POST /dbms/coverage` | Compare extracted and expert scenarios | Requires supplied scenario sets |
| `POST /dbms/generate` | Generate SQL from supplied scenarios | API defaults to SQLite |
| `POST /dbms/pipeline/generate` | Chain R1 extraction and R2 SQL generation | Supports `r1_provider`; returns SQL for review, does not execute |
| `POST /dbms/validate` | Validate SQL tests | API uses SQLite; PostgreSQL is a separate Python workflow |

### Example: R1 extraction

Send this JSON to `POST /dbms/scenarios`:

```json
{
  "requirement_document": "A product quantity must be between 1 and 100 inclusive. Inserts outside this range must be rejected."
}
```

The response contains structured scenarios with IDs, categories, preconditions, behavior, and expected results. To generate SQL tests from those scenarios in the same request, use `POST /dbms/pipeline/generate` and select `r1_provider` as `ollama` or `claude`. Generated SQL requires human review before execution.

## Installation and local development

### Prerequisites

- Python, Git, and dependencies in `backend/requirements.txt`
- Ollama with `qwen3:4b` for local-model workflows
- Anthropic API key and access to the selected Claude models for Claude workflows
- Docker for disposable PostgreSQL benchmark execution
- A reachable PostgreSQL test service for applicable integration tests

Clone the repository:

```sh
git clone https://github.com/Kayuhnaise/AI-Assisted-Test-Case-Generator.git
cd AI-Assisted-Test-Case-Generator/backend
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set credentials in your local environment or ignored `.env` file. **Never commit real keys or database passwords.** The following are placeholders, not verified model IDs:

```powershell
$env:ANTHROPIC_API_KEY = "<your-api-key>"
$env:CLAUDE_MODEL = "<accessible-R2-model-id>"
$env:CLAUDE_R1_MODEL = "<accessible-R1-model-id>"
$env:CLAUDE_COVERAGE_MODEL = "<accessible-coverage-model-id>"
```

The Claude modules have model defaults; override these settings only with model IDs available to your Anthropic account. The historical R2 result artifacts record the model string `claude-fable-5-1`; that string is a recorded configuration, not a guarantee of current API availability.

For local Ollama workflows:

```powershell
ollama pull qwen3:4b
```

Start the API from `backend/`:

```powershell
python -m uvicorn app.main:app --reload
```

### Automated tests

From `backend/`:

```powershell
python -m pytest tests -q
```

**Latest reported local run (November 6, 2026): 89 passed, 1 deprecation warning.** PostgreSQL integration tests require a reachable test database configured through `DBTESTGEN_POSTGRES_URL`; GitHub Actions provisions a temporary PostgreSQL 17 service. Disposable-container benchmark runs use their own PostgreSQL instances.

## Benchmark evaluation

The results below are from **different evaluation stages and datasets**. Do not combine their denominators into a single accuracy score or interpret iterative prompt/model refinements as a controlled comparison.

### R1: Library Management expert-scenario coverage

The Library Management SRS was evaluated against **19 expert reference scenarios**. Strict coverage counts fully matched reference scenarios; lenient coverage also counts partial matches.

| Extraction run | Full | Partial | Missing | Strict coverage |
|---|---:|---:|---:|---:|
| Ollama / Qwen3:4b | 14 | 4 | 1 | **14/19 (73.7%)** |
| Improved Claude extraction | 19 | 0 | 0 | **19/19 (100%)** |

The Ollama lenient coverage was 18/19 (94.7%). The improved Claude extraction generated more scenarios than the 19 reference scenarios; **100% reference coverage does not imply 100% precision, uniqueness, or validity of every generated scenario**. The improved Claude result is a manually audited reference-coverage finding, not a general guarantee and not an independently controlled model comparison.

Relevant files:

- `backend/tests/fixtures/external/library_management_srs.md`
- `backend/tests/fixtures/external/library_management_r1_reference.json`
- `backend/benchmark_results/library_r1_traceability_audited.csv`
- `backend/benchmark_results/library_r1_claude_extraction_improved.json`
- `backend/benchmark_results/library_r1_requirement_chunks.json`

### R2: SQLite and PostgreSQL benchmark (November 4, 2026)

The earlier 12-scenario R2 benchmark contains three positive, three negative, three boundary, and three edge cases, with expert-defined expected outcomes and independent verification checks.

| Database / recorded model | Generated | Execution validation | Exact oracle metadata match | Independent validity |
|---|---:|---:|---:|---:|
| SQLite / Claude (`claude-fable-5-1`) | 12/12 | 12/12 | 12/12 | **12/12 (100%)** |
| PostgreSQL / Claude (`claude-fable-5-1`) | 12/12 | 12/12 | 10/12 | **12/12 (100%)** |

The two PostgreSQL metadata mismatches, R2-006 and R2-012, concerned foreign-key error-string phrasing; execution and independent state/outcome checks passed. This is a small, iteratively refined benchmark and does **not** establish R1 coverage or general performance on unseen requirements.

Saved artifacts include:

- `backend/benchmark_results/dbms_r2_results_claude-fable-5-1_20261104T181658Z.json`
- `backend/benchmark_results/postgres_review_20261104T200629Z.json`
- `backend/benchmark_results/postgres_evaluation_20261104T200755Z.json`

### Additional Library Management R2 and end-to-end demo

A reviewed set of **10 Library Management R2 PostgreSQL tests passed 10/10**, including two tests adapted after review. A **separate book-registration end-to-end PostgreSQL demonstration passed 10/10**. These are distinct validation results, not evidence that an unreviewed fully automatic R1→R2 pipeline achieves 100% success across arbitrary requirements.

Artifacts:

- `backend/benchmark_results/library_r2_claude_selected_10.json`
- `backend/benchmark_results/library_r2_postgres_results.json`
- `backend/benchmark_results/library_r2_postgres_remaining_2.json`
- `backend/benchmark_results/end_to_end_demo_r1.json`
- `backend/benchmark_results/end_to_end_demo_r2.json`
- `backend/benchmark_results/end_to_end_demo_postgres_results.json`

### PostgreSQL benchmark execution and safety

`backend/evaluate_dbms_r2_postgres.py` separates generation from execution:

1. Generate a `postgres_review_<timestamp>.json` artifact without running SQL.
2. Manually inspect all setup statements, operations, and verification queries.
3. Confirm Docker is running; the evaluator uses a disposable PostgreSQL 17 container, localhost-only published port, and temporary non-superuser role.
4. Compute the reviewed file's SHA-256 digest and supply it to the evaluator; the file hash is verified before execution.
5. Inspect the results and independent oracle checks; the temporary container is removed afterward.

Example from `backend/` on macOS/Linux:

```sh
python evaluate_dbms_r2_postgres.py
shasum -a 256 benchmark_results/postgres_review_<timestamp>.json
python evaluate_dbms_r2_postgres.py \
  --reviewed-file "benchmark_results/postgres_review_<timestamp>.json" \
  --approved-sha256 "<sha256-of-reviewed-file>"
```

On Windows, use `Get-FileHash -Algorithm SHA256 <path>` to obtain the digest.

The repeated integrated benchmark contains 12 existing expert-labeled cases and four supplemental cases covering cascading deletes, tenant-scoped uniqueness, savepoint rollback, and generated identity values. Generate three trials with:

```sh
python evaluate_dbms_r1_r2_postgres.py --trials 3
```

This writes a `dbms_r1_r2_review_<timestamp>.json` file. Inspect all generated SQL and mark each `stages.review.status` as `"approved"` or `"rejected"` (rejected entries require a reason). After calculating the SHA-256 digest of the **edited and approved** artifact, execute:

```sh
python evaluate_dbms_r1_r2_postgres.py \
  --reviewed-file "benchmark_results/dbms_r1_r2_review_<timestamp>.json" \
  --approved-sha256 "<sha256-of-reviewed-file>"
```

The resulting report separates extraction, expert coverage, generation, review decisions, PostgreSQL execution, and independent-oracle outcomes. **Do not run generated SQL on persistent project databases or systems containing valuable data.** Docker-based disposal and review reduce risk but do not make arbitrary SQL execution secure or fully network-isolated.

## Historical Python/pytest proof of concept

The original project generated pytest cases from natural-language requirements and supplied Python code using local Ollama/Qwen3:4b. It included scenario identification, test traceability, Pydantic and AST validation, safeguards for missing `pytest` imports, category normalization, and bounded local pytest execution. These safeguards are separate from the DBMS SQL workflow.

### Historical reference data

| Requirement | Expert reference scenarios |
|---|---:|
| Account Lockout | 5 |
| Order Discount | 5 |
| Safe Division | 5 |
| Username Length | 6 |
| **Total** | **21** |

Reference data and associated Python code are in `evaluation/reference/`.

### Historical scenario coverage

| Stage | Reference coverage |
|---|---:|
| Baseline | 6/21 (28.6%) |
| Improvement 1 | 14/21 (66.7%) |
| Improvement 2 | 7/21 (33.3%) |
| Improvement 3 | 14/21 (66.7%) |

These were manually assessed historical Python scenarios, not DBMS R1 coverage measurements. Coverage was not monotonic.

### Historical execution results

| Stage | Successful pipeline runs | Passing generated pytest tests |
|---|---:|---:|
| Baseline | 3/4 | 8/8* |
| Improvement 1 | 4/4 | 14/16 |
| Improvement 2 | 3/4 | 9/10* |
| Improvement 3 | 4/4† | 10/15 |

`*` Excludes requirements for which no executable tests were produced.  
`†` A Safe Division attempt encountered a local Ollama inference failure; a retry succeeded.

Historical issues included a missed account-lockout boundary, incorrect order-discount assertions, missing `pytest` imports, scenario-category mismatches, hallucinated function names, and local Ollama inference failures. These results motivated separate requirements-coverage and independent-correctness checks.

## Related work

Two papers shaped the design and evaluation. Full summaries and their mapping to this project are in [`docs/related_work.md`](docs/related_work.md).

- **Req2Test** (França & Benitti, ACM SAC '26, [doi:10.1145/3748522.3780013](https://doi.org/10.1145/3748522.3780013)) generates unit tests from user stories using a DSL-guided planning stage before code generation. Following its approach, the Scenario Generator now emits a **structured, machine-checkable scenario schema**: each scenario declares its category, input condition, expected outcome, and the requirement clause it traces to. Free-text descriptions are gone. This lets Scenario-Type Coverage and Requirement Alignment be scored on structured fields (`backend/app/scenario_coverage.py`).
- **TestBench** (Zhang et al., *Frontiers of Computer Science*, 2025) benchmarks class-level LLM test generation and shows that high line coverage (92.5% for GPT-4) can coexist with a low mutation kill rate (26.1%). This motivated reporting coverage, executability, and correctness separately, and a planned mutation-testing metric (not yet implemented).

## Limitations and responsible use

- **Small and curated datasets:** The historical R2 SQL benchmark has 12 cases; Library Management R1 has 19 reference scenarios; the historical Python benchmark has 21. None supports broad generalization.
- **Different evaluation measures:** Reference coverage, generated-scenario precision, SQL executability, exact metadata matching, and independent validity are not interchangeable.
- **Limited end-to-end evidence:** A separate PostgreSQL demonstration has recorded results, but repeated independently audited full-pipeline reliability remains to be established.
- **Experimental model comparisons:** Prompt and model configurations evolved between runs. Differences should not be attributed solely to the model.
- **Semantic risks:** Generated tests can be syntactically valid while asserting the wrong behavior or relying on unsupported assumptions.
- **Execution risks:** Neither the Python executor nor the PostgreSQL runner is a secure sandbox for untrusted code. Use reviewed SQL and disposable, nonsensitive test data only.
- **Human oversight:** Expert review is needed for requirements alignment, test assertions, coverage judgments, and generated SQL.

## Next steps

1. **Run repeated integrated trials:** Execute at least three reviewed trials with `evaluate_dbms_r1_r2_postgres.py --trials 3`, recording per-stage success and failure rates.
2. **Audit more R1 datasets:** Reproduce the Library Management traceability audit and independently assess the 16-case integrated benchmark against its expert references.
3. **Expand test diversity:** Add independently reviewed requirements for concurrency, transaction isolation, permissions, and recovery, with repeated trials and independent oracles.
4. **Strengthen isolation:** Evaluate outbound-network restrictions and stronger container controls before running higher-risk generated SQL.

## Project takeaway

DB-TestGen demonstrates a traceable workflow from natural-language database requirements to generated SQL tests and reviewed execution. Its R2 benchmarks show strong independent validity on small curated datasets, and the newer Library Management experiments document manually audited R1 reference coverage and successful PostgreSQL validation. **These findings are promising proof-of-concept evidence, not proof of generalized or fully autonomous test-generation reliability.**
