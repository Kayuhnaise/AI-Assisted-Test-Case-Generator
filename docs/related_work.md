# Related Work

This section summarizes the related work reviewed for the project (SWENG 889, Lesson 6 Scientific Reading & Review, Samhitha Dwarakanath). It also describes how each paper influenced the design and evaluation of the AI-Assisted Requirement-to-Test Case Generator.

Both papers were selected from Penn State–approved sources (ACM Digital Library and Springer), after excluding papers already cited in the team proposal.

---

## 1. Req2Test

França, M., & Benitti, F. B. V. (2026). *Req2Test: An Approach for the Automatic Generation of Unit Tests from User Stories Using LLMs.* In Proceedings of the 41st ACM/SIGAPP Symposium on Applied Computing (SAC '26), pp. 1654–1663. ACM. https://doi.org/10.1145/3748522.3780013

### Summary

Req2Test generates unit tests directly from user stories and acceptance criteria, before any source code exists. It uses a two-stage pipeline:

1. a **structured test-planning stage**, where the LLM's reasoning is constrained by a purpose-built domain-specific language (DSL) that encodes what a test plan must contain; and
2. a **test-generation stage**, where the LLM produces executable code from that structured plan.

The authors compared Req2Test against EvoSuite using mutation score as the primary metric and reported consistently higher mutation scores. In scalability tests on QuixBugs, it achieved near-optimal coverage and autonomously detected 72.8% of injected faults.

### Relation to this project

| Aspect | Req2Test | This project |
|---|---|---|
| Inputs | User story + acceptance criteria only | Natural-language requirement **and** Python source code |
| Pipeline | DSL-guided planning → code generation | Scenario Generator → Test Generator (two LLM calls) |
| Intermediate representation | Formal DSL | Structured scenario schema (see below) |

**Design contrast.** Our generator deliberately requires source code, so expected outcomes can be grounded in a concrete implementation instead of inferred from requirement text alone. Req2Test shows that source-free generation is viable to a surprising degree. It also highlights a risk: assertions may encode the model's assumptions rather than the intended behavior.

**Adopted idea: a machine-checkable intermediate representation.** The original architecture passed free-text scenario descriptions from the Scenario Generator to the Test Generator. Following Req2Test's DSL-guided planning stage, scenarios are now typed records (`ScenarioCore` / `Scenario` in `backend/app/models.py`). Each scenario explicitly declares:

- its **category** (`positive`, `negative`, `boundary`, `edge`);
- the **input condition** it targets (`precondition`, `behavior_under_test`, `example_inputs`);
- its **expected outcome** (`expected_result`, `expected_outcome_kind`: `success` / `error` / `unspecified`); and
- the **requirement clause** it traces to (`requirement_clause`, a verbatim quote).

This is a lightweight schema, not a full DSL. It is enough to make the Scenario-Type Coverage and Requirement Alignment evaluation steps score structured fields instead of interpreting free text:

- **Scenario-Type Coverage** uses a deterministic gate (same category and outcome kind), exact `example_inputs` matching, and an LLM judge only for the remaining free-text fields (`backend/app/scenario_coverage.py`).
- **Requirement Alignment** is fully deterministic: a scenario is aligned when its `requirement_clause` appears verbatim in the requirement.
- The `unspecified` outcome kind gives the model an explicit way to flag behavior the requirement does not define. This addresses the question Req2Test raises about requirements that under-specify behavior the code implements in one particular way.

See `docs/architecture.md` (§3, "Structured scenario representation", and Decision 6).

---

## 2. TestBench

Zhang, Q., Shang, Y., Fang, C., Gu, S., Zhou, J., & Chen, Z. (2025). *TestBench: Evaluating Class-Level Test Case Generation Capability of Large Language Models.* Frontiers of Computer Science. Springer / Higher Education Press.

### Summary

TestBench is a benchmark, not a generation tool. It contains 108 Java functions from nine large, actively maintained open-source projects. It evaluates LLMs (CodeLlama, GPT-3.5, GPT-4) under three context levels: self-contained, full class, and an AST-derived class skeleton.

Its five-dimension, execution-based evaluation covers syntactic correctness, compilation, execution, line coverage (JaCoCo), and mutation kill rate (PITest).

Key findings:

- **Coverage does not imply fault detection.** GPT-4 reached 92.5% average line coverage but only a 26.1% mutation kill rate on passing tests. Many passing tests had weak or absent assertions.
- **More context is not always better.** Added context reliably helped only the largest model. For CodeLlama it sometimes reduced performance.

### Relation to this project

- **Evaluation design.** TestBench's multi-dimension, execution-grounded evaluation informed the decision to report scenario coverage, pipeline reliability, test executability, and test correctness separately (`evaluation/README.md`), rather than using pass rate as the only measure of quality.
- **Planned extension: mutation testing.** Our metrics measure whether tests execute and whether they cover the expected scenarios. Like TestBench's coverage numbers, they would not catch a test that runs cleanly but asserts too weakly to detect a bug. A small mutation-testing step (for example, `mutmut` on the benchmark's Python functions) is a planned supplementary metric and **is not yet implemented**.
- **Context sensitivity.** Because the generator receives both the requirement and the full source code, and runs on a small local model (`qwen3:4b`), TestBench's observation that extra context can degrade smaller models is a risk to check empirically rather than assume away.
- **Language gap.** TestBench is Java-only, so its specific numbers cannot be assumed to transfer to Python.

---

## 3. Synthesis

Both papers indicate that producing *executable* tests is no longer the hard part. The hard part is producing tests that actually encode and verify the intended behavior.

- Req2Test makes a positive claim: structured planning improves LLM test generation, even without source code.
- TestBench makes a cautionary one: even with source code, LLM tests often have weak assertions that coverage numbers hide.

This project sits between the two. It gives the model more grounding than Req2Test (the source code), and it asks for something neither paper evaluates: explicitly **categorized** scenarios (positive, negative, boundary, edge), each tied back to a specific requirement clause. Neither paper's dataset or harness is directly reusable, since both target Java and neither measures scenario-type differentiation. They did, however, lead to two concrete changes:

| Influence | Change | Status |
|---|---|---|
| Req2Test DSL-guided planning | Structured scenario schema between Scenario Generator and Test Generator; automated coverage and alignment scoring | Implemented (Improvement 4) |
| TestBench coverage vs. mutation-kill gap | Supplementary mutation-testing metric | Planned |
