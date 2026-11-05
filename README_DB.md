# DB-TestGen: Detailed Technical Architecture and Implementation Plan

**Selected direction:** Combined approach
**Initial DBMS:** PostgreSQL

DB-TestGen is an extension of the existing AI-Assisted Requirement-to-Test Case Generator.

The new system will combine two testing objectives:

- **Requirement-driven testing:** Determine whether PostgreSQL implements the behavior specified in its requirements and documentation.
- **Coverage-guided testing:** Generate additional SQL tests to exercise DBMS functionality that has not yet been adequately tested.

The distinction is important: the first objective checks whether the DBMS behaves correctly; the second explores how much of its internal implementation is exercised.

The system should connect these objectives through a shared test-generation pipeline, rather than building two independent tools.

---

## 1. Project definition

### Proposed title

**DB-TestGen: Requirement-Driven and Coverage-Guided SQL Test Generation Using Large Language Models**

### Problem statement

DBMS testing requires engineers to translate complex requirements into executable SQL tests, construct the necessary database context, define expected behavior, and ensure sufficient coverage of DBMS functionality. This process is labor-intensive and requires specialized database knowledge.

Existing LLM-based approaches can generate SQL statements, but generated tests may contain syntactic errors, incorrect assumptions about database semantics, incomplete schemas, or incorrect expected results. Furthermore, successful execution does not necessarily mean that a test validates the intended requirement or detects a defect.

### Proposed solution

Develop an LLM-assisted framework that:

1. Extracts test scenarios from DBMS requirement documents.
2. Converts scenarios into structured, machine-readable representations.
3. Generates complete SQL test cases, including schemas, test data, and expected results.
4. Validates generated tests against PostgreSQL.
5. Executes tests in isolated database environments.
6. Measures requirement coverage and DBMS implementation coverage.
7. Uses execution feedback and coverage-guided mutation to improve test suites.

### 1.1 Project objectives

| ID | Objective |
|----|-----------|
| O1 | Automatically extract test scenarios from lengthy DBMS requirements. |
| O2 | Generate executable, semantically valid PostgreSQL test cases. |
| O3 | Preserve traceability between requirements, scenarios, and SQL tests. |
| O4 | Automatically execute and validate generated tests. |
| O5 | Identify uncovered requirements and DBMS code paths. |
| O6 | Generate additional SQL tests using LLM feedback and coverage-guided mutation. |
| O7 | Evaluate the effectiveness of the combined approach against a baseline. |

---

## 2. Overall technical architecture

I suggest a modular architecture with seven main components.

### DB-TestGen — system architecture

**INPUT LAYER**

- DBMS requirements
- PostgreSQL documentation
- DBMS version/configuration

**1. Requirement Understanding Layer** *(LLM + RAG)*

- Document parsing and chunking
- Requirement retrieval
- SQL feature identification
- Prerequisite and configuration extraction

**2. Scenario Generation Layer** *(LLM)*

- Positive scenarios
- Negative scenarios
- Boundary scenarios
- Edge scenarios
- Expected behavior extraction

**3. Intermediate Representation (IR)**

- Pydantic-validated JSON, requirement traceability, SQL feature metadata, preconditions, expected outcomes

**4. SQL Test Generation Layer** *(LLM + PostgreSQL feature catalog)*

- DDL generation
- DML generation
- DQL generation
- Expected result generation
- SQL dialect constraints

**5. Test Validation Layer** *(Deterministic checks)*

- SQL parsing
- Schema consistency
- Object/reference validation
- Expected-result verification
- Scenario-to-test consistency

**6. Execution and Measurement Layer**

- Isolated PostgreSQL instance
- SQL execution
- Result and error capture
- Requirement coverage
- DBMS code coverage

**7. Intelligent Refinement Layer** *(LLM + mutation + MCTS)*

- Error-driven test repair
- Missing-scenario generation
- SQL mutation
- Coverage-guided selection

**OUTPUT**

- Validated SQL test suite, execution report, requirement coverage report, DBMS coverage report, and traceability matrix

The refinement layer feeds new or repaired tests back into validation and execution.

> **The most important architectural decision** is to separate LLM-generated artifacts from deterministic validation. The LLM proposes tests; the software verifies whether those tests meet defined constraints.

---

## 3. Detailed component design

### Component 1 — Requirement Understanding Layer

**Purpose:** Understand DBMS requirements and retrieve relevant information from lengthy documentation.

This component addresses Challenge 1 from ICSE: test-relevant information is scattered across sections and may exceed the model's context window.

**Input:**

- DBMS requirement document (PDF, Markdown, HTML).
- PostgreSQL documentation.
- Target PostgreSQL version.
- Relevant configuration settings.

**Processing:**

1. Extract text from documents.
2. Divide documents into semantically meaningful chunks.
3. Store chunks with source references and metadata.
4. Identify relevant SQL features.
5. Retrieve related requirements, prerequisites, and expected behaviors.
6. Ask the LLM to consolidate the retrieved information.

For example, a requirement about foreign keys may reference:

- Foreign-key constraint definition.
- Referenced table requirements.
- NULL handling.
- Referential actions such as `CASCADE`.
- Expected constraint violation behavior.

The system should retrieve all related information before creating the scenario.

**Recommended technologies:**

| Function | Technology |
|----------|------------|
| PDF parsing | PyMuPDF |
| Chunking | LangChain or custom Python |
| Embeddings | Local embedding model |
| Vector database | Chroma |
| Retrieval | Semantic + metadata filtering |
| Generation | Qwen through Ollama |

 PostgreSQL's official documentation is used as the knowledge base, together with a small collection of explicit challenge requirements.

### Component 2 — Scenario Generator

**Purpose:** Translate retrieved requirements into complete test scenarios.

This is the first LLM generation stage, directly inherited from our previous project.

The generator should identify:

- **Positive scenarios:** expected successful behavior.
- **Negative scenarios:** invalid operations.
- **Boundary scenarios:** minimum, maximum, and threshold values.
- **Edge scenarios:** unusual combinations and special conditions.

Each scenario must include three essential elements from the ICSE challenge:

1. Preconditions.
2. Behavior under test.
3. Expected result.

**Example requirement**

> A PostgreSQL table must enforce a `UNIQUE` constraint on the `email` column.

The scenario generator should produce something like:

| Category | Scenario | Expected result |
|----------|----------|-----------------|
| Positive | Insert a unique email | Successful insertion |
| Negative | Insert an existing email | Unique violation |
| Boundary | Insert an empty string, if permitted by the specification | Behavior determined by the applicable requirement |
| Edge | Insert `NULL` into the column | Depends on `NULL` and `NOT NULL` constraints |

Notice that the generator must not assume that `UNIQUE` automatically means `NOT NULL`. It must consider the actual specification and schema.

### Component 3 — Intermediate Representation (IR)

**Purpose:** Establish a reliable contract between scenario generation, SQL generation, validation, and execution.

I recommend implementing this component before expanding the SQL generator.

A scenario should be represented as a Pydantic model and serialized into JSON. Here is a more complete proposed schema:

```json
{
  "scenario_id": "DB-001",
  "requirement_id": "REQ-001",
  "feature": "UNIQUE constraint",
  "category": "negative",
  "preconditions": {
    "database": "test_db",
    "table": "users",
    "schema": {
      "id": "INTEGER PRIMARY KEY",
      "email": "VARCHAR UNIQUE"
    },
    "existing_data": [
      [1, "alice@example.com"]
    ]
  },
  "action": {
    "sql": "INSERT INTO users VALUES (2, 'alice@example.com')"
  },
  "expected_result": {
    "outcome": "error",
    "sqlstate": "23505"
  },
  "source_references": [
    {
      "document": "postgres_requirements.pdf",
      "section": "4.2"
    }
  ]
}
```

The schema above is illustrative. The actual implementation should validate the structure and verify the SQLSTATE against PostgreSQL's error behavior.

Adding these fields as well:

- `postgres_version`
- `configuration`
- `setup_sql`
- `cleanup_sql`
- `dependencies`
- `validation_status`
- `generated_test_id`

This makes each test reproducible.

**Why this matters:** our previous project experienced semantic hallucinations, missing imports, and category mismatches. The IR gives us a way to detect structural errors before generated code reaches execution.

### Component 4 — SQL Test Generator

**Purpose:** Convert validated scenarios into complete executable SQL test packages.

This stage should use a second LLM call, just as our previous project used a separate Test Generator.

However, it is recommended generating a structured test package rather than unrestricted SQL text.

Each package should contain:

| Artifact | Purpose |
|----------|---------|
| `setup.sql` | Create tables, indexes, constraints, and other prerequisites |
| `data.sql` | Insert initial and boundary test data |
| `test.sql` | Execute the SQL behavior under test |
| `expected.json` | Define expected results or errors |
| `cleanup.sql` | Restore the test environment |
| `metadata.json` | Link the test to its requirement and scenario |

**Example**

For the `UNIQUE` constraint scenario:

`setup.sql`

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email VARCHAR UNIQUE
);
```

`data.sql`

```sql
INSERT INTO users VALUES
  (1, 'alice@example.com');
```

`test.sql`

```sql
INSERT INTO users VALUES
  (2, 'alice@example.com');
```

`expected.json`

```json
{
  "expected_outcome": "error",
  "sqlstate": "23505"
}
```

This package makes it possible to execute every scenario independently.

#### Feature-guided SQL generation

Introduce a PostgreSQL feature catalog. Start with a manageable hierarchy:

```
PostgreSQL feature catalog
├── DDL — Data Definition Language
│     CREATE, ALTER, DROP, constraints, indexes, schemas
├── DML — Data Manipulation Language
│     INSERT, UPDATE, DELETE, UPSERT, NULL handling
├── DQL — Data Query Language
│     SELECT, JOIN, GROUP BY, subqueries, window functions
├── Transactions
│     COMMIT, ROLLBACK, savepoints, isolation levels
├── Configuration
│     Session settings, server parameters, permissions
└── Security and access
      Roles, privileges, ownership, access restrictions
```

This feature catalog should be expanded gradually using official PostgreSQL documentation, rather than attempting to model every PostgreSQL feature at the beginning.

### Component 5 — Deterministic Test Validation Engine

This is a critical component because LLM-generated SQL cannot be trusted automatically.

Implementing validation in five steps:

| # | Validation | Implementation |
|---|------------|----------------|
| 1 | Structural validation | Pydantic |
| 2 | SQL syntax validation | SQLGlot PostgreSQL dialect |
| 3 | Schema validation | PostgreSQL catalog inspection |
| 4 | Execution validation | Isolated PostgreSQL instance |
| 5 | Semantic validation | Expected results, SQLSTATE, and scenario assertions |

One important distinction: SQLGlot parsing confirms that a statement can be parsed according to its grammar. It does not guarantee that the statement is valid against the actual database schema or that it implements the requirement.

Therefore, actual PostgreSQL execution is essential.

#### Expected-result validation

For a **negative** test, the framework should check:

- Did the SQL statement fail?
- Was the expected error produced?
- Did it have the correct SQLSTATE?
- Did the database remain in the expected state?

For a **positive** test:

- Did the statement execute successfully?
- Did it produce the expected data?
- Did it preserve the required constraints?

Use SQLSTATE codes rather than comparing complete error-message strings, which can vary by version and environment.

### Component 6 — Execution and Coverage Measurement

This component has two separate responsibilities.

#### A. Requirement-level execution

Run every generated test against PostgreSQL and record:

- Scenario ID.
- SQL statements.
- Execution status.
- Actual output.
- Expected output.
- Error code.
- Execution duration.
- Validation result.

Use a disposable database or isolated schema for each test package. Transaction rollback alone is not sufficient for every operation because some PostgreSQL operations cannot be rolled back in the same way as ordinary DML.

#### B. Internal DBMS code coverage

This is where the Quover and MIST research directions become relevant.

To measure PostgreSQL implementation coverage, you need an instrumented PostgreSQL build.

**Recommended approach:**

1. Build PostgreSQL from source with GCC coverage instrumentation (`--enable-coverage`).
2. Run generated SQL workloads against the instrumented server.
3. Collect coverage data using `gcov` and `lcov`.
4. Analyze coverage by source files and modules.
5. Identify previously unexecuted code paths.

PostgreSQL has several important internal areas to investigate:

| Module | What SQL exercises |
|--------|--------------------|
| Parser | SQL grammar and syntax |
| Analyzer | Semantic analysis and name resolution |
| Optimizer | Query planning and optimization |
| Executor | Query execution |
| Storage | Data access and storage operations |
| Transaction manager | Transaction processing and concurrency |

For the first prototype, we would concentrate on parser, optimizer, and executor coverage.

> **Note:** This requires a source-built, instrumented PostgreSQL server. Running PostgreSQL in a standard Docker image does not automatically provide internal code-coverage measurements.

### Component 7 — Intelligent Refinement Engine

This is the component that combines the coverage-guided generation direction with MIST's MCTS approach.

Implementing it in three incremental levels.

#### Level 1: Error-driven refinement

When a generated SQL test fails unexpectedly:

1. Capture the PostgreSQL error.
2. Retrieve the original requirement and scenario.
3. Send the error and generated SQL to the LLM.
4. Ask it to repair the test without changing the intended behavior.
5. Validate the repaired test again.

Do not let the LLM simply remove the failing assertion to make the test pass.

#### Level 2: Coverage-guided generation

When tests execute successfully but code coverage stops improving:

1. Identify uncovered DBMS modules or code regions.
2. Map relevant SQL features to those regions where possible.
3. Select features that may exercise the missing functionality.
4. Generate additional SQL tests.
5. Execute them and measure coverage changes.
6. Keep tests that produce new coverage.

This is the most direct connection to coverage-driven SQL generation research.

#### Level 3: MCTS-based mutation

Once the basic feedback loop works, introduce Monte Carlo Tree Search.

For this project, the search **state** can represent:

- A selected seed SQL test.
- Its current database schema and data.
- The mutation history.
- The current coverage information.

**Actions** are SQL mutation operators, such as:

- Add a `JOIN`.
- Replace a comparison operator.
- Add a nested subquery.
- Change a data type.
- Introduce `NULL`.
- Modify a constraint.
- Add an aggregate function.

The **reward** should account for coverage improvement while preserving validity and, where relevant, requirement traceability.

An illustrative reward function:

$$R = 0.6\,\Delta C + 0.2\,V + 0.2\,D$$

Where:

- $\Delta C$ = normalized new DBMS code coverage.
- $V$ = test validity indicator.
- $D$ = test diversity indicator.

These weights are proposed starting values, not values established by the research papers. They should be tuned experimentally.

For requirement-specific tests, add a hard constraint: a mutation that changes the intended behavior under test cannot be counted as a valid requirement test.

For exploratory coverage tests, requirement traceability is not mandatory, but the tests should be labeled separately.

---

## 4. Technology stack and infrastructure

I recommend keeping the architecture Python-based, so you can reuse your previous project's implementation skills and much of its code.

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| API | FastAPI | System endpoints |
| Data models | Pydantic | IR and validation |
| LLM | Ollama + Qwen | Scenario and SQL generation |
| RAG | Chroma + embeddings | Requirement retrieval |
| Document processing | PyMuPDF | PDF extraction |
| SQL parsing | SQLGlot | SQL parsing and dialect checks |
| Database | PostgreSQL | Target DBMS |
| Database access | psycopg | SQL execution |
| Test orchestration | pytest | Automated test workflow |
| Code coverage | gcov + lcov | Internal PostgreSQL coverage |
| Search optimization | Python MCTS | Mutation selection |
| Containerization | Docker | Isolated execution |
| CI/CD | GitHub Actions | Regression testing |

### Proposed deployment architecture

**Local development environment**

- **FastAPI backend** — REST API and orchestration
- **Ollama** — Local Qwen model
- **Chroma** — Document retrieval
- **Test orchestration service** — Scenario generation, SQL validation, execution, coverage and refinement
- **PostgreSQL** — Target database
- **Instrumented PostgreSQL** — Code coverage
- **Results and evaluation storage** — Test artifacts, execution logs, coverage reports, and experiment results

Keeping the LLM, database, and execution environment local initially. This avoids sending requirements or database information to an external model provider.

> **Security requirement:** The SQL execution service should use a non-superuser PostgreSQL account, disposable databases, resource limits, query timeouts, and network isolation. Generated SQL must never execute with unrestricted host or database privileges.

---

## 5. Backend API design

Preserving the API-driven architecture of our previous project.

Our existing `/scenarios` and `/generate` endpoints are a good starting point, but the new system needs additional endpoints for SQL generation, validation, execution, and coverage refinement.

### Proposed API endpoints

| Endpoint | Method | Responsibility |
|----------|--------|----------------|
| `/requirements` | POST | Upload and process requirement documents |
| `/requirements/{id}/retrieve` | POST | Retrieve relevant requirement sections |
| `/scenarios` | POST | Generate structured test scenarios |
| `/sql-tests/generate` | POST | Generate SQL test packages |
| `/sql-tests/validate` | POST | Validate generated SQL |
| `/sql-tests/execute` | POST | Execute tests against PostgreSQL |
| `/coverage` | GET | Retrieve coverage information |
| `/refine` | POST | Generate additional tests using feedback |
| `/experiments` | GET | Retrieve evaluation results |

### Example workflow

**Step 1: Upload a requirement**

`POST /requirements`

Input:

```json
{
  "document_name": "postgres_requirements.pdf",
  "dbms": "postgresql",
  "version": "17"
}
```

**Step 2: Generate scenarios**

`POST /scenarios`

Input:

```json
{
  "requirement_id": "REQ-001",
  "feature": "UNIQUE constraint"
}
```

Output:

```json
{
  "scenarios": [
    {
      "scenario_id": "DB-001",
      "category": "positive",
      "behavior": "Insert unique email",
      "expected_result": "Successful insertion"
    },
    {
      "scenario_id": "DB-002",
      "category": "negative",
      "behavior": "Insert duplicate email",
      "expected_result": "Unique violation"
    }
  ]
}
```

**Step 3: Generate SQL tests**

`POST /sql-tests/generate`

Input:

```json
{
  "scenario_ids": ["DB-001", "DB-002"],
  "dbms": "postgresql",
  "version": "17"
}
```

Output:

```json
{
  "generated_tests": [
    {
      "test_id": "SQL-001",
      "scenario_id": "DB-001",
      "status": "generated"
    },
    {
      "test_id": "SQL-002",
      "scenario_id": "DB-002",
      "status": "generated"
    }
  ]
}
```

**Step 4: Validate and execute**

`POST /sql-tests/execute`

Input:

```json
{
  "test_ids": ["SQL-001", "SQL-002"],
  "environment": "isolated"
}
```

Output:

```json
{
  "results": [
    {
      "test_id": "SQL-001",
      "status": "passed"
    },
    {
      "test_id": "SQL-002",
      "status": "passed",
      "expected_sqlstate": "23505",
      "actual_sqlstate": "23505"
    }
  ]
}
```

A negative test that correctly produces its expected SQL error should be reported as **passed**, not failed.

These are proposed API contracts, not existing implementations.

---

## 6. Suggested GitHub repository structure

I would create a new repository rather than significantly modifying the previous project. This allows you to preserve the original implementation as a baseline.

Suggested repository: `db-testgen`

```
db-testgen/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── api/
│   │   │   ├── requirements.py
│   │   │   ├── scenarios.py
│   │   │   ├── sql_tests.py
│   │   │   ├── execution.py
│   │   │   └── coverage.py
│   │   │
│   │   ├── models/
│   │   │   ├── requirement.py
│   │   │   ├── scenario.py
│   │   │   ├── sql_test.py
│   │   │   └── execution_result.py
│   │   │
│   │   ├── services/
│   │   │   ├── document_processor.py
│   │   │   ├── retrieval_service.py
│   │   │   ├── scenario_generator.py
│   │   │   ├── sql_generator.py
│   │   │   ├── sql_validator.py
│   │   │   ├── db_executor.py
│   │   │   ├── coverage_analyzer.py
│   │   │   └── refinement_engine.py
│   │   │
│   │   ├── dbms/
│   │   │   ├── postgres.py
│   │   │   ├── feature_catalog.py
│   │   │   └── sql_mutations.py
│   │   │
│   │   ├── prompts/
│   │   │   ├── scenario_prompt.txt
│   │   │   ├── sql_generation_prompt.txt
│   │   │   └── repair_prompt.txt
│   │   │
│   │   └── utils/
│   │
│   ├── tests/
│   │   ├── test_scenarios.py
│   │   ├── test_sql_generation.py
│   │   ├── test_sql_validation.py
│   │   └── test_execution.py
│   │
│   └── requirements.txt
│
├── documents/
│   ├── requirements/
│   └── postgres_documentation/
│
├── evaluation/
│   ├── benchmark/
│   ├── reference_scenarios/
│   ├── results/
│   └── analysis/
│
├── postgres/
│   ├── docker/
│   ├── scripts/
│   └── instrumentation/
│
├── docker-compose.yml
├── README.md
└── .github/
    └── workflows/
        └── tests.yml
```

### Development principle

Keep the responsibilities separate:

- `scenario_generator.py` should not generate SQL.
- `sql_generator.py` should not redefine the original requirement.
- `sql_validator.py` should not silently change the expected behavior.
- `db_executor.py` should execute only validated test packages.
- `coverage_analyzer.py` should measure and report coverage, not decide whether a requirement is satisfied.
- `refinement_engine.py` should use feedback to propose new tests, which must pass through validation again.

This separation will make debugging, evaluation, and future research easier.

---

## 7. Experimental design and evaluation

This is especially important because ICSE challenge defines two quantitative requirements.

It is recommended designing the evaluation before implementing all the features.

### 7.1 Build a reference benchmark

Create a manually labeled benchmark of PostgreSQL requirements and test scenarios.

For a manageable first experiment suggestion:

- 10–15 requirement statements.
- 50–80 expert-labeled reference scenarios.
- A mixture of DDL, DML, DQL, transactions, constraints, and configuration.
- Positive, negative, boundary, and edge conditions.

Each reference scenario should have:

- Requirement ID.
- Preconditions.
- Behavior under test.
- Expected result.
- Relevant PostgreSQL feature.
- Reference SQL test, if applicable.

Have at least two people independently review the reference scenarios and resolve disagreements. This reduces the risk of evaluating the LLM against an arbitrary ground truth.

### 7.2 Core challenge metrics

**Metric 1 — Test-Scenario Extraction Coverage**

Use the definition from our challenge document:

$$\text{Coverage}_{\text{scenario}} = \frac{\text{Number of matched reference scenarios}}{\text{Total reference scenarios}} \times 100$$

A scenario only counts as covered if all three elements match:

1. Preconditions.
2. Behavior under test.
3. Expected result.

**Target: above 90%**

**Metric 2 — Constraint-Preserving Test Validity**

$$\text{Validity} = \frac{\text{Valid generated SQL test cases}}{\text{Total generated SQL test cases}} \times 100$$

A valid test must satisfy:

1. Correct SQL syntax.
2. Correct SQL semantics.
3. Complete database context.
4. Correct expected behavior.

**Target: above 90%**

### 7.3 Additional metrics

| Metric | Measurement |
|--------|-------------|
| SQL Execution Success Rate | Expected successful executions / generated tests intended to execute successfully |
| Test Repair Rate | Initially invalid tests successfully repaired |
| Requirement Traceability | Tests mapped to valid source scenarios |
| Line Coverage | Executed source lines / executable source lines |
| Branch Coverage | Executed branches / measurable branches |
| Function Coverage | Executed functions / measurable functions |
| Mutation Score | Detected injected faults / non-equivalent injected faults |

One important point: execution success and test validity are different metrics. A negative test can execute an operation that raises an error and still be a successful test.

### 7.4 Compare four configurations

This is the recommended experiment design.

| Experiment | Configuration | Purpose |
|------------|---------------|---------|
| E0 | Direct LLM-to-SQL generation | Baseline |
| E1 | LLM + RAG + structured IR | Evaluate requirement understanding |
| E2 | E1 + deterministic validation + execution feedback | Evaluate test reliability |
| E3 | E2 + coverage-guided generation + SQL mutation/MCTS | Evaluate additional DBMS coverage |

This makes it possible to measure the incremental value of each component.

#### Expected experimental comparison

*Illustrative evaluation design, not measured results.*

**Metrics to compare across experiments** (E0–E3): scenario coverage and test validity.

The experiment should measure these independently rather than assume that one configuration wins.

> **Note:** The original document contains an empty placeholder chart (E0–E3 on the x-axis, scenario coverage and test validity series, 0%–1% y-axis). Populate this chart with actual repeated-run measurements. Zeroes are placeholders, not predictions.

For each configuration, run multiple trials using the same requirements, model, PostgreSQL version, and execution limits. Report mean and variability. This matters because your previous project demonstrated that LLM generation quality can vary considerably between runs.

### 7.5 Test effectiveness: seeded defects

Particularly recommended adding seeded defects.

For example, deliberately modify a PostgreSQL test implementation or use a controlled test fixture that violates a specified behavior.

Then determine whether the generated tests detect the defect.

This is valuable because a test suite may have high code coverage without detecting incorrect behavior.

For the initial prototype, you can use small, controlled SQL-level fault scenarios. Actual PostgreSQL source-code fault injection can be a later research extension.

---

## 8. Implementation roadmap

Divide development into six phases, prioritizing a working end-to-end prototype before advanced coverage optimization.

### Proposed 8-week implementation schedule

*Assuming a small student team working in parallel. Adjust based on course deadlines and available computing resources.*

#### Week 1 — Foundation

- Create the new GitHub repository.
- Set up FastAPI, Ollama, and PostgreSQL.
- Define Pydantic models.
- Select PostgreSQL requirements for the benchmark.

**Deliverable:** Working infrastructure

#### Week 2 — Requirement Analyzer

- Implement PDF and document processing.
- Add RAG retrieval.
- Build the initial PostgreSQL feature catalog.
- Implement scenario generation.

**Deliverable:** Structured scenarios

#### Week 3 — Intermediate Representation

- Finalize JSON schema.
- Add source traceability.
- Implement scenario validation.
- Build the reference-scenario benchmark.

**Deliverable:** Validated scenario IR

#### Week 4 — SQL Test Generation

- Generate DDL, DML, and DQL.
- Generate setup, test, and cleanup scripts.
- Generate expected results.
- Add SQLGlot validation.

**Deliverable:** SQL test packages

#### Week 5 — PostgreSQL Execution

- Implement isolated execution.
- Capture errors and SQLSTATE codes.
- Validate expected results.
- Add error-driven LLM refinement.

**Deliverable:** End-to-end working prototype

#### Week 6 — Coverage Measurement

- Build instrumented PostgreSQL.
- Integrate gcov/lcov.
- Analyze module-level coverage.
- Implement uncovered-feature identification.

**Deliverable:** Coverage feedback

#### Week 7 — Mutation and Optimization

- Implement SQL mutation operators.
- Select promising seed tests.
- Add a basic MCTS implementation.
- Measure coverage improvement.

**Deliverable:** Coverage-guided generation

#### Week 8 — Evaluation and Reporting

- Run E0–E3 experiments.
- Calculate scenario coverage and validity.
- Analyze failures and seeded defects.
- Document limitations and results.

**Deliverable:** Final evaluated system

---

## 9. What should be implemented first?

I want to emphasize one architectural decision: **do not start with MCTS.**

MCTS is interesting from a research perspective, but implementing it before you have reliable SQL generation, validation, and coverage measurement will create unnecessary complexity.

Three implementation milestones.

### Milestone 1 — Minimum Viable Product

**Must have**

- Requirement document ingestion.
- RAG retrieval.
- LLM scenario generation.
- Structured JSON representation.
- SQL generation.
- PostgreSQL execution.
- Expected-result validation.

**Success criterion:** A requirement can be converted into a complete, executable, validated SQL test package.

### Milestone 2 — Research functionality

**Implemented in this repository**

- PostgreSQL SQLGlot validation with a restrictive statement/function allowlist.
- Transaction- and schema-isolated test execution with expected SQLSTATE checks.
- LCOV line, branch, function, and PostgreSQL-module reporting.
- Heuristic mapping from uncovered PostgreSQL source paths to feature hints.
- Requirement-supported scenario generation targeted at uncovered features.
- Error-driven SQL repair that preserves the scenario, setup, data, cleanup,
  and expected oracle.

**Environment-dependent verification still required:** Build PostgreSQL with
coverage instrumentation, run the generated SQL against that build, collect an
LCOV report, and compare the resulting coverage. This repository includes the
analysis and generation pipeline but does not vendor or build PostgreSQL.
Execution requires `DBMS_TEST_DATABASE_URL` pointed at a dedicated,
non-superuser test database.

**Success criterion:** Demonstrate additional tests improve measured DBMS
coverage without losing requirement validity. This empirical result is not
claimed until the instrumented PostgreSQL workflow has been run.

### Milestone 3 — Advanced optimization

**Extension**

- SQL mutation engine.
- MCTS implementation.
- Mutation effectiveness analysis.
- Seeded-defect detection.
- Model comparison.

**Success criterion:** Demonstrate that coverage-guided mutation improves test effectiveness over ordinary LLM generation.

---

## 10. Risks and technical decisions

There are several issues I would address early.

| Risk | Recommended mitigation |
|------|------------------------|
| LLM invents PostgreSQL functionality | RAG from official documentation |
| Incorrect expected results | Independent deterministic assertions and requirement grounding |
| SQL dialect incompatibility | PostgreSQL-specific parsing and execution |
| Incomplete database context | Generate and validate complete setup scripts |
| Infinite LLM repair loops | Maximum 2–3 repair attempts |
| Tests modify shared data | Disposable databases and isolated execution |
| High code coverage but low defect detection | Seeded defects and mutation testing |
| MCTS becomes computationally expensive | Limit iterations and stop when coverage plateaus |

A particularly important distinction concerns **test oracles**. There are two kinds of validation:

- **Implicit oracle:** Did the DBMS execute the query without crashing or producing an unexpected error?
- **Explicit oracle:** Did the DBMS produce the correct result required by the specification?

Your project should support both, but explicit oracles are essential for the requirement-driven part.

This is also an opportunity to address a limitation in MIST: its primary testing objective is code coverage, and successful execution does not establish logical correctness.

---

## 11. Research positioning: What is actually new?

I would position your work carefully in relation to the two papers.

| Research | Main direction | What your project adds |
|----------|----------------|------------------------|
| Abdelkarim et al., *Boosting DBMS Test Coverage via LLM-Driven SQL Generation* (DBTest 2026) | LLM-driven SQL generation for DBMS coverage | Explicit requirement-to-test traceability and semantic validation |
| Chen et al., MIST (2026 preprint) | Feature-guided generation, error feedback, and MCTS mutation | Requirement-preserving generation and explicit expected-result checking |
| Your previous project | Requirement-to-test generation for Python | Complete DBMS test-context synthesis and SQL execution |

The ACM DOI distinction is worth preserving in your literature review: `10.1145/3810991` identifies the DBTest 2026 proceedings; the individual Quover paper has DOI `10.1145/3810991.3811637`.

The MIST paper is an arXiv preprint, not evidence of an established production standard. Its reported results are useful research motivation, not guaranteed outcomes for your implementation.

I would formulate your research question as:

> **RQ:** How effectively can an LLM-based framework generate requirement-compliant PostgreSQL tests and improve DBMS implementation coverage through execution-guided refinement and coverage-driven SQL mutation?

Potential subquestions:

- **RQ1:** Does RAG-based requirement analysis improve test-scenario extraction coverage?
- **RQ2:** Does structured intermediate representation improve SQL test validity?
- **RQ3:** Does execution feedback improve the quality of generated SQL tests?
- **RQ4:** Does coverage-guided mutation improve DBMS code coverage compared with direct LLM generation?
- **RQ5:** Does the generated test suite detect seeded defects?

This gives you a coherent research narrative rather than simply combining several existing techniques.

---

## 12. My recommended next steps

I would make the following decisions now:

1. Use **PostgreSQL 17** as the initial target version, and pin the exact version throughout your experiments.
2. Use **Qwen through Ollama** initially, reusing your previous local LLM setup.
3. Create the **structured IR** before implementing SQL generation.
4. Build a small **benchmark** of real DBMS requirements and manually validated scenarios.
5. Get the complete requirement-to-SQL **execution workflow** working before attempting code instrumentation.
6. Introduce **coverage-guided refinement and MCTS** incrementally.

> **My strongest recommendation:** Make the requirement-driven and coverage-guided pipelines share the same SQL validation and execution infrastructure, but keep their evaluation metrics separate. This is the architectural feature that will make the project both manageable and scientifically meaningful.

### Useful technical resources

- PostgreSQL 17 documentation
- PostgreSQL source code
- SQLGlot documentation
- Qwen models on Ollama
- MIST research paper
- Quover research paper

**One final practical suggestion:** Your first coding task should be to implement just one complete example: a PostgreSQL `UNIQUE` constraint requirement → scenario JSON → setup SQL → generated test SQL → expected SQLSTATE → execution result. Once this works reliably, generalizing it to other SQL features becomes much easier.
