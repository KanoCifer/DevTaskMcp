"""Read-side view layer for Task Document v1.

The v3 MCP surface should never dump a long ``detail`` blob back into an
agent's context unless the agent asked for it.  This module parses a
task's ``detail`` (a Markdown body in the canonical Task Document
format) and renders it as one of four views:

* ``summary`` — only structured fields, no detail
* ``execute`` — structured fields + Goal/Plan/Acceptance Criteria/Constraints/Context Pointers
* ``review`` — structured fields + Acceptance Criteria/Constraints/Context Pointers
* ``full`` — everything (current behaviour)

The parser reuses the Task Document front-matter splitter, but is
tolerant of legacy detail bodies that lack a front matter block.  In
that case, the raw Markdown is returned in ``full`` and unknown
sections fall back to the body of the document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .task_document import (
    CANONICAL_SECTIONS,
    REQUIRED_SECTIONS,
    SECTION_ORDER,
    DocumentSection,
    _parse_sections,
    _split_front_matter,
    _validate_metadata,
    _validate_sections,
)

VIEWS: tuple[str, ...] = ("summary", "execute", "review", "full")

EXECUTE_SECTIONS: tuple[str, ...] = (
    "goal",
    "plan",
    "acceptance criteria",
    "constraints",
    "context pointers",
)
REVIEW_SECTIONS: tuple[str, ...] = (
    "acceptance criteria",
    "constraints",
    "context pointers",
)


class ViewError(ValueError):
    """Raised for invalid view arguments."""


@dataclass
class ParsedTaskDocument:
    metadata: dict[str, Any]
    sections: dict[str, str] = field(default_factory=dict)
    extras: list[DocumentSection] = field(default_factory=list)
    raw_markdown: str = ""
    has_front_matter: bool = False


def _split_acceptance_criteria(text: str) -> list[dict[str, str]]:
    """Extract the AC checklist as a list of {text, checked} dicts.

    Items must use the ``- [ ]`` (unchecked) or ``- [x]`` (checked)
    syntax.  Anything else is ignored to keep the contract honest.
    """
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not (stripped.startswith("- [ ]") or stripped.startswith("- [x]")):
            continue
        checked = stripped.startswith("- [x]")
        body = stripped[5:].strip()
        out.append({"text": body, "checked": "yes" if checked else "no"})
    return out


def _split_context_pointers(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("-"):
            continue
        candidate = stripped[1:].strip()
        if ":" in candidate and "\\" not in candidate.split(":", 1)[0]:
            out.append(candidate)
        else:
            out.append(candidate)
    return out


def _parse_detail(detail: Optional[str]) -> ParsedTaskDocument:
    if not detail:
        return ParsedTaskDocument(metadata={}, raw_markdown=detail or "")
    metadata, body = _split_front_matter(detail)
    if not metadata:
        return ParsedTaskDocument(metadata={}, raw_markdown=detail)
    try:
        metadata = _validate_metadata(metadata)
        sections, extras, _ = _parse_sections(body)
        # Don't enforce required sections here — this is a read-side
        # parser, so legacy detail bodies with weird structure must
        # still be readable in ``full`` view.
        _ = (REQUIRED_SECTIONS, CANONICAL_SECTIONS, SECTION_ORDER)
    except Exception:
        return ParsedTaskDocument(metadata={}, raw_markdown=detail)
    return ParsedTaskDocument(
        metadata=metadata,
        sections=sections,
        extras=extras,
        raw_markdown=detail,
        has_front_matter=True,
    )


def render_view(task: dict[str, Any], view: str) -> dict[str, Any]:
    """Return a serialisable view of a task.

    Unknown views raise :class:`ViewError`.  ``summary`` never includes
    ``detail``; ``full`` returns the original payload unchanged.
    """
    if view not in VIEWS:
        raise ViewError(f"未知 view: {view!r}，必须是 {VIEWS}")
    structured_keys = (
        "slug",
        "title",
        "type",
        "priority",
        "scope",
        "status",
        "kind",
        "parent_slug",
        "blocked_by",
        "for_agent",
        "due_date",
        "sort_order",
        "is_deleted",
        "created_at",
        "updated_at",
        "id",
    )
    structured: dict[str, Any] = {k: task[k] for k in structured_keys if k in task}
    if view == "summary":
        return structured
    if view == "full":
        return dict(task)
    # execute / review → blend structured fields with parsed sections.
    parsed = _parse_detail(task.get("detail"))
    out: dict[str, Any] = dict(structured)
    if view == "execute":
        target = EXECUTE_SECTIONS
    else:
        target = REVIEW_SECTIONS
    sections: dict[str, Any] = {}
    for canonical in target:
        if canonical not in parsed.sections:
            continue
        if canonical == "acceptance criteria":
            sections["acceptance_criteria"] = _split_acceptance_criteria(
                parsed.sections[canonical]
            )
        elif canonical == "context pointers":
            sections["context_pointers"] = _split_context_pointers(
                parsed.sections[canonical]
            )
        else:
            sections[canonical.replace(" ", "_")] = parsed.sections[canonical].strip()
    if sections:
        out["sections"] = sections
    return out
