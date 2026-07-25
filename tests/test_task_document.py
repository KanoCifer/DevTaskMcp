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
    assert "src/devtask-mcp/server.py:235" in doc.section("context pointers")


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


def test_rejects_missing_goal():
    with pytest.raises(DocumentError, match="Goal"):
        parse_task_document_file(FIXTURES / "missing_goal.md")


def test_rejects_missing_acceptance_criteria():
    with pytest.raises(DocumentError, match="Acceptance Criteria"):
        parse_task_document_file(FIXTURES / "missing_ac.md")


def test_rejects_duplicate_section():
    with pytest.raises(DocumentError, match="section 重复"):
        parse_task_document_file(FIXTURES / "duplicate_section.md")


def test_acceptance_criteria_requires_checkbox_syntax():
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
    with pytest.raises(DocumentError, match="Acceptance Criteria"):
        parse_task_document(raw)
