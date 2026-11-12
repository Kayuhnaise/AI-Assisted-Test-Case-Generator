
# Library Management System R1 Reference Scenario Methodology

## Source Requirements

The reference scenarios were developed from six selected
requirements in the Library Management System SRS:

- SRS-001: User Registration
- SRS-005: Book Addition
- SRS-008: Book Update
- SRS-009: Book Deletion
- SRS-010: Book Borrowing
- SRS-013: Book Return

The selected requirements are preserved in
`library_management_r1_input.md`.

## Reference Scenario Construction

The reference scenarios were prepared on November 5, 2026,
with assistance from ChatGPT.

An initial set of 20 scenarios was drafted from the
selected SRS requirements. During benchmark preparation,
one overlapping scenario was removed, producing the final
set of 19 reference scenarios.

The final reference set was prepared before examination
of the first recorded R1 model extraction output.

The scenarios were not independently authored or
validated by an external requirements engineering expert.

## Reference Scenario Structure

Each reference scenario includes:
- A unique reference identifier
- The associated SRS requirement identifier
- A scenario category
- A precondition
- A behavior under test
- An expected result

The final reference set is stored in
`library_management_r1_reference.json`.

## Evaluation Interpretation

The reference set is used to evaluate R1 requirement
coverage by comparing generated scenarios against
the 19 reference scenarios.

Strict coverage counts only fully matched reference
scenarios. Partial matches are excluded from the
strict coverage numerator.

Because the reference set was constructed with
LLM assistance, coverage scores measure agreement
with this benchmark rather than independently
established expert ground truth.

The reference set does not by itself establish
the correctness, non-redundancy, or precision of
all generated scenarios.

## Limitations

The benchmark contains only 19 reference scenarios
across six requirements.

The reference scenarios were developed with LLM
assistance and were not independently validated
by external domain experts.

Although the reference set preceded the recorded
model outputs, AI assistance during its construction
may introduce selection bias or shared assumptions.

These limitations should be considered when
interpreting reported R1 coverage.
