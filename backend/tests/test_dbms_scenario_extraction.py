
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.dbms_scenarios import identify_dbms_scenarios

from app.dbms_chunking import chunk_document


def scenario(scenario_id, behavior):
    return {
        "id": scenario_id,
        "category": "positive",
        "precondition": "A database table exists",
        "behavior_under_test": behavior,
        "expected_result": "The operation succeeds",
    }


def mock_response(scenarios, done_reason="stop"):
    import json

    return SimpleNamespace(
        message=SimpleNamespace(
            content=json.dumps({"scenarios": scenarios})
        ),
        done_reason=done_reason,
    )


def long_document():
    return (
        "# Requirement A\n"
        + "Insert valid records.\n" * 400
        + "\n# Requirement B\n"
        + "Retrieve existing records.\n" * 400
    )


def test_short_document_preserves_scenario_id():
    response = mock_response([scenario("SC-001", "Insert a record")])

    with patch("app.dbms_scenarios.ollama.chat", return_value=response) as chat:
        result = identify_dbms_scenarios("Insert a valid record.")

    assert len(result) == 1
    assert result[0].id == "SC-001"
    assert chat.call_count == 1


def test_long_document_extracts_from_multiple_chunks():
    chunks = chunk_document(long_document())
    assert len(chunks) > 1

    responses = [
        mock_response([
            scenario(f"SC-{i}", f"Operation {i}")
        ])
        for i in range(len(chunks))
    ]

    with patch(
        "app.dbms_scenarios.ollama.chat",
        side_effect=responses,
    ) as chat:
        result = identify_dbms_scenarios(long_document())

    assert chat.call_count == len(chunks)
    assert len(result) == len(chunks)
    assert [item.id for item in result] == [
        f"dbms_{i}" for i in range(1, len(chunks) + 1)
    ]

def test_long_document_deduplicates_scenarios():
    chunks = chunk_document(long_document())
    duplicate = scenario("SC-001", "Insert a record")

    responses = [
        mock_response([duplicate])
        for _ in chunks
    ]

    with patch(
        "app.dbms_scenarios.ollama.chat",
        side_effect=responses,
    ) as chat:
        result = identify_dbms_scenarios(long_document())

    assert chat.call_count == len(chunks)
    assert len(result) == 1
    assert result[0].id == "dbms_1"


def test_chunk_can_return_no_scenarios():
    chunks = chunk_document(long_document())
    assert len(chunks) > 1

    responses = [
        mock_response([])
        for _ in chunks
    ]

    responses[-1] = mock_response([
        scenario("SC-002", "Retrieve a record")
    ])

    with patch(
        "app.dbms_scenarios.ollama.chat",
        side_effect=responses,
    ) as chat:
        result = identify_dbms_scenarios(long_document())

    assert chat.call_count == len(chunks)
    assert len(result) == 1
    assert result[0].behavior_under_test == "Retrieve a record"


def test_truncated_response_raises_error():
    response = mock_response(
        [scenario("SC-001", "Insert a record")],
        done_reason="length",
    )

    with patch("app.dbms_scenarios.ollama.chat", return_value=response):
        with pytest.raises(ValueError, match="truncated"):
            identify_dbms_scenarios("Insert a valid record.")


def test_empty_document_is_rejected():
    with patch("app.dbms_scenarios.ollama.chat") as chat:
        with pytest.raises(ValueError, match="empty"):
            identify_dbms_scenarios("   ")

    chat.assert_not_called()
