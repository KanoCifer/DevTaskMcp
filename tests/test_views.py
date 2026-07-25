"""Tests for the v3 read views (summary/execute/review/full)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: F401

import pytest

from devtask_mcp.views import ViewError, render_view


def _task(detail: str = "") -> dict:
    return {
        "id": "obj-1",
        "slug": "task-1",
        "title": "Example",
        "type": "优化",
        "priority": "P1 高",
        "scope": "后端-Python",
        "status": "待排期",
        "kind": "subtask",
        "parent_slug": None,
        "blocked_by": [],
        "for_agent": True,
        "due_date": None,
        "sort_order": 0,
        "is_deleted": False,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "detail": detail,
    }


def test_summary_view_never_includes_detail():
    rendered = render_view(_task(detail="very long body"), "summary")
    assert "detail" not in rendered
    assert rendered["slug"] == "task-1"


def test_execute_view_includes_goal_plan_and_ac():
    detail = (
        "---\n"
        'title: "x"\n'
        'task_type: "优化"\n'
        'priority: "P1 高"\n'
        'scope: "x-y"\n'
        "---\n\n"
        "## Goal\n\nReduce the cost of an agent round-trip.\n\n"
        "## Plan\n\n1. Drop legacy fields.\n\n"
        "## Acceptance Criteria\n\n- [ ] Done\n- [x] Tested\n\n"
        "## Constraints\n\n- Stay on v3 API.\n\n"
        "## Context Pointers\n\n- `src/foo.py:1`\n"
    )
    rendered = render_view(_task(detail=detail), "execute")
    assert rendered["sections"]["goal"].startswith("Reduce the cost")
    assert "1. Drop legacy fields." in rendered["sections"]["plan"]
    assert rendered["sections"]["acceptance_criteria"] == [
        {"text": "Done", "checked": "no"},
        {"text": "Tested", "checked": "yes"},
    ]
    assert "Stay on v3" in rendered["sections"]["constraints"]
    assert rendered["sections"]["context_pointers"] == ["`src/foo.py:1`"]


def test_review_view_omits_goal_and_plan():
    detail = (
        "---\n"
        'title: "x"\n'
        'task_type: "优化"\n'
        'priority: "P1 高"\n'
        'scope: "x-y"\n'
        "---\n\n"
        "## Goal\n\nLong background.\n\n"
        "## Plan\n\nMany steps.\n\n"
        "## Acceptance Criteria\n\n- [ ] Done\n\n"
        "## Constraints\n\n- Stay on v3 API.\n\n"
        "## Context Pointers\n\n- `src/foo.py:1`\n"
    )
    rendered = render_view(_task(detail=detail), "review")
    assert "goal" not in rendered["sections"]
    assert "plan" not in rendered["sections"]
    assert rendered["sections"]["acceptance_criteria"][0]["text"] == "Done"


def test_full_view_returns_original_payload():
    task = _task(detail="anything")
    rendered = render_view(task, "full")
    assert rendered is task or rendered == task


def test_unknown_view_raises():
    with pytest.raises(ViewError):
        render_view(_task(), "nope")


def test_legacy_detail_without_sections_is_tolerated():
    rendered = render_view(_task(detail="just paragraphs"), "execute")
    assert rendered.get("sections", {}) == {}