"""Tests for the v3 read views (summary/full)."""

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


def test_full_view_returns_original_payload():
    task = _task(detail="anything")
    rendered = render_view(task, "full")
    assert rendered == task


def test_removed_views_are_rejected():
    for view in ("execute", "review"):
        with pytest.raises(ViewError):
            render_view(_task(), view)


def test_unknown_view_raises():
    with pytest.raises(ViewError):
        render_view(_task(), "nope")
