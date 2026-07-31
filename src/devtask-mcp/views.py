"""Read-side view layer for Task Document v1.

The v3 MCP surface should never dump a long ``detail`` blob back into an
agent's context unless the agent asked for it.  This module renders a
task as one of two views:

* ``summary`` — only structured fields, no detail
* ``full`` — everything
"""

from __future__ import annotations

from typing import Any

VIEWS: tuple[str, ...] = ("summary", "full")


class ViewError(ValueError):
    """Raised for invalid view arguments."""


def render_view(task: dict[str, Any], view: str) -> dict[str, Any]:
    """Return a serialisable view of a task.

    Unknown views raise :class:`ViewError`.  ``summary`` never includes
    ``detail``; ``full`` returns the original payload unchanged.
    """
    if view not in VIEWS:
        raise ViewError(f"未知 view: {view!r}，必须是 {VIEWS}")
    if view == "full":
        return dict(task)
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
    return {k: task[k] for k in structured_keys if k in task}
