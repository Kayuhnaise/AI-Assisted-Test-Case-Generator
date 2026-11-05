
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.dbms_sql_generator import generate_dbms_sql_tests
from app.models import DBMSScenario


def make_scenario():
    return DBMSScenario(
        id="DBMS-001",
        category="negative",
        precondition="A user already exists.",
        behavior_under_test="Insert duplicate email.",
        expected_result="UNIQUE constraint violation.",
    )


def make_generated_case(valid=True):
    case = {
        "id": "SQL-001",
        "scenario_id": "DBMS-001",
        "title": "Duplicate email test",
        "category": "negative",
        "sql_dialect": "sqlite",
        "preconditions": ["A user already exists"],
        "constraints": ["email is UNIQUE"],
        "setup_sql": [
            "CREATE TABLE users (email TEXT UNIQUE);",
            "INSERT INTO users VALUES ('a@example.com');",
        ],
        "test_sql": (
            "INSERT INTO users VALUES ('a@example.com');"
        ),
        "verification_assertions": [
            {
                "query": "SELECT COUNT(*) FROM users",
                "expected_scalar": 1,
            }
        ],
        "verification_sql": [],
        "expected_outcome": {
            "outcome_type": "error",
            "expected_error": (
                "UNIQUE constraint failed" if valid else None
            ),
            "assertion_description": (
                "Duplicate email must be rejected"
            ),
        },
        "cleanup_sql": [],
    }

    return {"test_cases": [case]}


def mock_response(payload):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
        stop_reason="end_turn",
    )

@patch("app.dbms_sql_generator.anthropic.Anthropic")
def test_retry_recovers_invalid_generation(mock_anthropic):
    mock_chat = mock_anthropic.return_value.messages.create
    mock_chat.side_effect = [
        mock_response(make_generated_case(valid=False)),
        mock_response(make_generated_case(valid=True)),
    ]

    cases = generate_dbms_sql_tests(
        "Email addresses must be unique.",
        [make_scenario()],
    )

    assert len(cases) == 1
    assert cases[0].scenario_id == "DBMS-001"
    assert mock_chat.call_count == 2

    retry_messages = mock_chat.call_args_list[1].kwargs[
        "messages"
    ]

    assert "missing the expected SQL error" in (
        retry_messages[-1]["content"]
    )


@patch("app.dbms_sql_generator.anthropic.Anthropic")
def test_retry_exhaustion(mock_anthropic):
    mock_chat = mock_anthropic.return_value.messages.create
    mock_chat.return_value = mock_response(
        make_generated_case(valid=False)
    )

    with pytest.raises(
        ValueError,
        match="failed after 3 attempts",
    ):
        generate_dbms_sql_tests(
            "Email addresses must be unique.",
            [make_scenario()],
        )

    assert mock_chat.call_count == 3


@patch("app.dbms_sql_generator.anthropic.Anthropic")
def test_retry_corrects_scenario_id(mock_anthropic):
    mock_chat = mock_anthropic.return_value.messages.create
    invalid = make_generated_case(valid=True)
    invalid["test_cases"][0]["scenario_id"] = "WRONG-ID"

    mock_chat.side_effect = [
        mock_response(invalid),
        mock_response(make_generated_case(valid=True)),
    ]

    cases = generate_dbms_sql_tests(
        "Email addresses must be unique.",
        [make_scenario()],
    )

    assert cases[0].scenario_id == "DBMS-001"
    assert mock_chat.call_count == 2


@patch("app.dbms_sql_generator.anthropic.Anthropic")
def test_valid_generation_needs_no_retry(mock_anthropic):
    mock_chat = mock_anthropic.return_value.messages.create
    mock_chat.return_value = mock_response(
        make_generated_case(valid=True)
    )

    cases = generate_dbms_sql_tests(
        "Email addresses must be unique.",
        [make_scenario()],
    )

    assert len(cases) == 1
    assert mock_chat.call_count == 1
