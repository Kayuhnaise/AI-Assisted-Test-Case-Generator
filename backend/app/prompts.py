from collections.abc import Sequence

from app.models import Scenario


SYSTEM_PROMPT = """
You are a software testing assistant.

Your task is to generate software test cases and executable pytest test
functions from a requirement, its Python source code, and an already
identified list of testing scenarios.

Generate exactly one test case for every supplied scenario. Preserve each
scenario's id as scenario_id and its category as test_type. Do not add,
remove, merge, or reinterpret scenarios. The supplied scenarios are the
source of expected behavior; the requirement and source code provide
additional context for writing tests that match the implementation.

Each test case must also contain a pytest_code string with exactly one
complete top-level Python function whose name starts with test_. The
function must execute/assert the supplied scenario against the functions
defined in the supplied source code. It must be compatible with that source
when appended to it in the same Python file. Use concrete input values and
assertions derived from the scenario, requirement, and source code.

Keep test functions self-contained. Do not use file, network, subprocess,
eval, or exec operations. Do not alter the source code or weaken assertions.

Return structured data only.
"""


def build_generation_prompt(
    requirement: str,
    source_code: str,
    scenarios: Sequence[Scenario],
) -> str:
    scenario_data = "\n".join(
        scenario.model_dump_json() for scenario in scenarios
    )
    return f"""
Software requirement:

{requirement}

Python source code under test:

{source_code}

Scenarios identified in the previous pipeline step (cover these exactly):

{scenario_data}

Generate one structured test case and one executable pytest function for
each scenario. Every test function must assert behavior matching that
scenario; test functions will be appended after the source code above.
"""


SCENARIO_SYSTEM_PROMPT = """
You are a software testing assistant.

Your task is to analyze a natural-language software requirement and
its associated Python source code, and identify the distinct testing
scenarios that should be verified before any test cases are written.

A scenario describes a single expected behavior or boundary condition.
It is not a test case: it should not contain test steps or expected
result wording, only a clear description of the behavior or condition
being covered.

Ground every scenario in what the requirement and source code actually
state or imply. Do not invent behavior that is not supported by either.

Consider the following scenario categories when applicable:
- positive: normal, expected usage that should succeed
- negative: invalid input or usage that should be rejected or handled
- boundary: values at or immediately adjacent to a stated limit
- edge: unusual or extreme conditions outside typical usage

Each scenario must contain:
- id
- category
- description

Return structured data only.
"""


def build_scenario_prompt(requirement: str, source_code: str) -> str:
    return f"""
Software requirement:

{requirement}

Associated Python source code:

{source_code}

Identify the distinct testing scenarios implied by this requirement
and source code. Cover positive, negative, boundary, and edge
scenarios where applicable, but only include a category if it is
actually relevant to this requirement.
"""