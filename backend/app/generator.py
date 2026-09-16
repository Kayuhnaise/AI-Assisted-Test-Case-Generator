from app.models import TestCase


def generate_test_cases(requirement: str) -> list[TestCase]:
    """
    Temporary mock generator.

    This will later be replaced by an LLM-based implementation.
    """

    test_cases = [
        TestCase(
            id="TC-001",
            title="Verify expected requirement behavior",
            test_type="positive",
            preconditions=[
                "The system is available",
                "A valid test user exists"
            ],
            steps=[
                "Prepare the system for the test",
                "Perform the action described in the requirement",
                "Observe the system response"
            ],
            expected_result=(
                "The system behaves according to the specified requirement."
            )
        ),
        TestCase(
            id="TC-002",
            title="Verify behavior with invalid input",
            test_type="negative",
            preconditions=[
                "The system is available"
            ],
            steps=[
                "Provide invalid or unexpected input",
                "Observe the system response"
            ],
            expected_result=(
                "The system handles the invalid input without "
                "unexpected behavior."
            )
        )
    ]

    return test_cases