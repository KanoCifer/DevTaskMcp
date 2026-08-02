"""Tests for the Task Document v1 parser/compiler."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: F401

import pytest

from devtask_mcp.task_document import (
    DocumentError,
    parse_task_document,
    parse_task_document_file,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "task_document"


def test_parses_valid_subtask_document():
    doc = parse_task_document_file(FIXTURES / "subtask.md")
    assert doc.metadata["title"] == "Slim MCP contract"
    assert doc.metadata["task_type"] == "优化"
    assert doc.metadata["priority"] == "P1 高"
    assert doc.metadata["scope"] == "后端-Python"
    assert doc.metadata["kind"] == "subtask"
    assert doc.metadata["for_agent"] is True
    assert doc.section("goal").startswith("Drop the legacy long-text fields")
    assert "- [ ]" in doc.section("acceptance criteria")
    assert "src/devtask_mcp/server.py:235" in doc.section("context pointers")


def test_compiles_to_api_body():
    doc = parse_task_document_file(FIXTURES / "subtask.md")
    body = doc.to_body()
    assert body["title"] == "Slim MCP contract"
    assert body["type"] == "优化"
    assert body["priority"] == "P1 高"
    assert body["scope"] == "后端-Python"
    assert body["kind"] == "subtask"
    assert body["for_agent"] is True
    assert "## Goal" in body["detail"]
    assert "## Acceptance Criteria" in body["detail"]
    # No legacy long-text fields leak into the body.
    for key in (
        "description",
        "acceptance_criteria",
        "constraints",
        "context_pointers",
    ):
        assert key not in body


def test_rejects_missing_front_matter():
    with pytest.raises(DocumentError, match="front matter"):
        parse_task_document("# No front matter\n\n## Goal\nx\n")


def test_rejects_bad_enum():
    with pytest.raises(DocumentError, match="task_type"):
        parse_task_document_file(FIXTURES / "bad_enum.md")


def test_front_matter_slug_pass_through():
    raw = (
        "---\n"
        'title: "Slugged"\n'
        'task_type: "优化"\n'
        'priority: "P1 高"\n'
        'scope: "后端-Python"\n'
        'slug: "task-42"\n'
        'parent_slug: "task-1"\n'
        "---\n\n"
        "## Goal\n\nx\n"
    )
    doc = parse_task_document(raw)
    assert doc.to_body()["slug"] == "task-42"


def test_rejects_front_matter_slug_without_parent():
    raw = (
        "---\n"
        'title: "Slugged"\n'
        'task_type: "优化"\n'
        'priority: "P1 高"\n'
        'scope: "后端-Python"\n'
        'slug: "task-42"\n'
        "---\n\n"
        "## Goal\n\nx\n"
    )
    with pytest.raises(DocumentError, match="parent_slug"):
        parse_task_document(raw)


def test_rejects_bad_front_matter_slug():
    raw = (
        "---\n"
        'title: "Slugged"\n'
        'task_type: "优化"\n'
        'priority: "P1 高"\n'
        'scope: "后端-Python"\n'
        'slug: "weird slug"\n'
        'parent_slug: "task-1"\n'
        "---\n\n"
        "## Goal\n\nx\n"
    )
    with pytest.raises(DocumentError, match="slug"):
        parse_task_document(raw)


def test_accepts_free_form_body_without_sections():
    """Body structure is a convention — no Goal/AC required."""
    doc = parse_task_document_file(FIXTURES / "missing_goal.md")
    assert doc.section("goal") is None
    assert doc.metadata["title"] == "Missing Goal"


def test_accepts_body_without_acceptance_criteria():
    doc = parse_task_document_file(FIXTURES / "missing_ac.md")
    assert doc.section("acceptance criteria") is None
    assert "Has a goal" in doc.section("goal")


def test_duplicate_section_last_wins():
    doc = parse_task_document_file(FIXTURES / "duplicate_section.md")
    assert doc.section("goal") == "Second."
    assert "Steps." in doc.section("plan")


def test_acceptance_criteria_requires_no_checkbox_syntax():
    """AC without `- [ ]` items is accepted (reference is optional)."""
    raw = (
        "---\n"
        'title: "t"\n'
        'task_type: "优化"\n'
        'priority: "P1 高"\n'
        'scope: "x-y"\n'
        "---\n\n"
        "## Goal\n\nstuff\n\n"
        "## Acceptance Criteria\n\n- Not a checkbox\n"
    )
    doc = parse_task_document(raw)
    assert "Not a checkbox" in doc.section("acceptance criteria")
