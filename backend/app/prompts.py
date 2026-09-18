SYSTEM_PROMPT = """
You are a software testing assistant.

Your task is to generate software test cases from a natural-language
software requirement.

Generate test cases that are directly traceable to the requirement.

Consider the following test categories when applicable:
- positive
- negative
- boundary
- edge

Do not invent functionality that is not stated or reasonably implied
by the requirement.

Each test case must contain:
- id
- title
- test_type
- preconditions
- steps
- expected_result

Return structured data only.
"""


def build_generation_prompt(requirement: str) -> str:
    return f"""
Software requirement:

{requirement}

Generate a set of test cases that adequately tests this requirement.

Include positive, negative, boundary, and edge cases when they are
applicable to the requirement.
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