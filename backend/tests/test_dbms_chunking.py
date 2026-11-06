import pytest
from pydantic import ValidationError
from app.dbms_chunking import chunk_document, parse_sections, split_text, chunk_by_requirement
from app.models import GeneratedDBMSScenarios


def _doc(sections: int, body_chars: int = 900) -> str:
    parts = ["# Overview\nAll tables use the InnoDB-like engine by default."]
    parts.append("## Configuration\nSet `max_rows=100` before running tests.")
    for i in range(sections):
        parts.append(
            f"## Feature {i}\n" + (f"Feature {i} behavior. " * (body_chars // 20))
        )
    return "\n\n".join(parts)


def test_short_document_is_a_single_chunk_without_context():
    chunks = chunk_document("# T\nA committed row survives restart.")
    assert len(chunks) == 1
    assert chunks[0].context == ""


def test_empty_document_has_no_chunks():
    assert chunk_document("   \n ") == []


def test_full_document_response_requires_scenarios():
    with pytest.raises(ValidationError):
        GeneratedDBMSScenarios(scenarios=[])


def test_long_document_is_split_and_every_chunk_fits():
    document = _doc(sections=20)
    assert len(document) > 6000
    chunks = chunk_document(document, max_chars=2000)
    assert len(chunks) > 1
    assert all(len(c.text) <= 2000 for c in chunks)


def test_no_content_is_lost_when_chunking():
    document = _doc(sections=12)
    chunks = chunk_document(document, max_chars=1500)
    joined = "\n".join(c.text for c in chunks)
    for i in range(12):
        assert f"Feature {i} behavior." in joined


def test_configuration_section_is_carried_as_shared_context():
    chunks = chunk_document(_doc(sections=20), max_chars=2000)
    later = [c for c in chunks if "Feature 15 behavior" in c.text][0]
    assert "max_rows=100" in later.context


def test_a_chunk_does_not_repeat_its_own_sections_in_context():
    chunks = chunk_document(_doc(sections=20), max_chars=2000)
    first = chunks[0]  # holds Overview + Configuration
    assert "max_rows=100" in first.text
    assert "max_rows=100" not in first.context


def test_headings_inside_code_fences_are_not_sections():
    text = "# Real\nintro\n```\n# not a heading\n```\nmore"
    assert [s.path for s in parse_sections(text)] == [("Real",)]


def test_oversized_section_is_split_into_parts():
    pieces = split_text("word " * 1000, max_chars=500)
    assert len(pieces) > 1 and all(len(p) <= 500 for p in pieces)


def test_numbered_requirements_are_separate_chunks():
    document = """
# System Requirements

#### SRS-001: Registration
Users must have unique usernames.

#### SRS-002: Book Addition
Books must have unique ISBN values.

#### SRS-003: Borrowing
Available books may be borrowed.
"""

    chunks = chunk_by_requirement(document)

    assert len(chunks) == 3

    for chunk in chunks:
        assert chunk.text.count("#### SRS-") == 1


def test_shared_data_constraints_are_available_as_context():
    document = """
#### SRS-001: Registration
Users must have unique usernames.

#### SRS-002: Book Addition
Books must have unique ISBN values.

## Data Requirements
### Data Validation Rules
Usernames and ISBN values must be unique.
"""

    chunks = chunk_by_requirement(document)

    assert len(chunks) == 2

    for chunk in chunks:
        assert "Usernames and ISBN values must be unique" in chunk.context


def test_ordinary_short_document_uses_existing_behavior():
    document = "# Requirement\nA row must persist after commit."

    chunks = chunk_by_requirement(document)

    assert len(chunks) == 1
    assert chunks[0].context == ""
