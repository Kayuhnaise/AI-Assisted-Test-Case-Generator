"""Heading-aware chunking for long DBMS requirement documents.

Pure standard library, so it can be tested without Ollama or FastAPI.

Why this exists: a single ollama.chat call over a long document is silently
truncated at the model's context length. Here the document is split along
Markdown headings into chunks that fit the context window, and each chunk
is paired with a small "shared context" block (the preamble plus sections
about prerequisites, configuration, definitions, etc.) so that scenarios
extracted from one section can still pick up setup stated in another.
"""

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

CONTEXT_KEYWORDS = (
    "prerequisite", "precondition", "configuration", "config", "setting",
    "parameter", "definition", "glossary", "terminology", "overview",
    "introduction", "setup", "environment", "compatib", "assumption",
    "scope", "background", "note",
)


@dataclass(frozen=True)
class Section:
    index: int
    path: tuple[str, ...]
    text: str  # includes the heading line


@dataclass(frozen=True)
class Chunk:
    section_path: str
    text: str
    context: str
    section_indexes: tuple[int, ...]


def parse_sections(document: str) -> list[Section]:
    """Split Markdown/plain text into sections at heading lines."""
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    current_path: tuple[str, ...] = ()
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            sections.append(Section(len(sections), current_path, text))
        buffer.clear()

    for line in document.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        match = None if in_fence else HEADING_RE.match(line)
        if match:
            flush()
            level, title = len(match.group(1)), match.group(2)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current_path = tuple(t for _, t in stack)
        buffer.append(line)
    flush()
    return sections


def split_text(text: str, max_chars: int) -> list[str]:
    """Split text into pieces of at most max_chars, preferring paragraph
    boundaries, then line boundaries, then a hard character split."""
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        candidates = [paragraph]
        if len(paragraph) > max_chars:
            candidates = []
            line_buf = ""
            for line in paragraph.splitlines():
                while len(line) > max_chars:
                    if line_buf:
                        candidates.append(line_buf)
                        line_buf = ""
                    candidates.append(line[:max_chars])
                    line = line[max_chars:]
                if len(line_buf) + len(line) + 1 > max_chars and line_buf:
                    candidates.append(line_buf)
                    line_buf = ""
                line_buf = f"{line_buf}\n{line}" if line_buf else line
            if line_buf:
                candidates.append(line_buf)
        for part in candidates:
            if current and len(current) + len(part) + 2 > max_chars:
                pieces.append(current)
                current = part
            else:
                current = f"{current}\n\n{part}" if current else part
    if current:
        pieces.append(current)
    return pieces


def _is_context_section(section: Section) -> bool:
    if not section.path:  # preamble before the first heading
        return True
    title = section.path[-1].lower()
    return any(keyword in title for keyword in CONTEXT_KEYWORDS)


def _build_context(
    sections: list[Section], exclude: set[int], max_chars: int
) -> str:
    parts: list[str] = []
    remaining = max_chars
    for section in sections:
        if section.index in exclude or not _is_context_section(section):
            continue
        if remaining <= 0:
            break
        snippet = section.text[:remaining]
        parts.append(snippet)
        remaining -= len(snippet) + 2
    return "\n\n".join(parts)


def chunk_document(
    document: str,
    max_chars: int = 6000,
    max_context_chars: int = 2000,
) -> list[Chunk]:
    """Chunk a document along headings.

    A document that already fits in max_chars becomes one chunk with no
    extra context, so short inputs behave exactly as before.
    """
    document = document.strip()
    if not document:
        return []
    if len(document) <= max_chars:
        return [Chunk("(whole document)", document, "", ())]

    sections = parse_sections(document)

    # Break oversized sections into parts, remembering the owning section.
    pieces: list[tuple[int, str, str]] = []  # (section index, label, text)
    for section in sections:
        label = " > ".join(section.path) or "(preamble)"
        parts = split_text(section.text, max_chars)
        for number, part in enumerate(parts, 1):
            suffix = f" (part {number}/{len(parts)})" if len(parts) > 1 else ""
            pieces.append((section.index, label + suffix, part))

    # Pack adjacent pieces greedily up to max_chars.
    groups: list[list[tuple[int, str, str]]] = []
    size = 0
    for piece in pieces:
        if groups and size + len(piece[2]) + 2 <= max_chars:
            groups[-1].append(piece)
            size += len(piece[2]) + 2
        else:
            groups.append([piece])
            size = len(piece[2])

    chunks = []
    for group in groups:
        indexes = tuple(dict.fromkeys(p[0] for p in group))
        chunks.append(
            Chunk(
                section_path=" | ".join(p[1] for p in group),
                text="\n\n".join(p[2] for p in group),
                context=_build_context(
                    sections, set(indexes), max_context_chars
                ),
                section_indexes=indexes,
            )
        )
    return chunks


REQUIREMENT_HEADING_RE = re.compile(
    r"^(?:SRS|FR|REQ|US)[-_]?\d+\b",
    re.IGNORECASE,
)


def chunk_by_requirement(
    document: str,
    max_chars: int = 6000,
    max_context_chars: int = 2000,
) -> list[Chunk]:
    """Create focused extraction chunks for numbered requirements.

    Falls back to ordinary heading-aware chunking when the document
    does not contain multiple numbered requirement headings.
    """
    sections = parse_sections(document)

    requirement_sections = [
        section
        for section in sections
        if section.path
        and REQUIREMENT_HEADING_RE.match(section.path[-1])
    ]

    if len(requirement_sections) < 2:
        return chunk_document(
            document,
            max_chars=max_chars,
            max_context_chars=max_context_chars,
        )

    requirement_indexes = {
        section.index for section in requirement_sections
    }

    shared_sections = [
        section for section in sections
        if section.index not in requirement_indexes
        and (
            _is_context_section(section)
            or any(
                "data requirement" in title.lower()
                or "data validation" in title.lower()
                or "data relationship" in title.lower()
                for title in section.path
            )
        )
    ]

    context_parts = []
    remaining = max_context_chars

    for section in shared_sections:
        if remaining <= 0:
            break

        snippet = section.text[:remaining]
        context_parts.append(snippet)
        remaining -= len(snippet) + 2

    shared_context = "\n\n".join(context_parts)

    chunks = []

    for section in requirement_sections:
        parts = split_text(section.text, max_chars)

        for part_number, part in enumerate(parts, start=1):
            chunks.append(
                Chunk(
                    section_path=" > ".join(section.path),
                    text=part,
                    context=shared_context,
                    section_indexes=(section.index,),
                )
            )

    return chunks
