"""End-to-end MCP server tests against a fake DevTaskClient.

The v3 tools accept /tmp paths to Task Document files; they route those
through :func:`server._read_temp_markdown` so the ``/tmp`` boundary is
enforced before the parsers see any text.

Tests in this module assert:
- the ``/tmp`` reader rejects everything outside the boundary;
- the legacy long-text parameters are not surfaced on any tool schema;
- the v3 tool bodies wire correctly to the API client.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Ensure the hyphen-named package loads under its underscore alias.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: F401  (side effect: registers devtask_mcp)

import pytest
from fastmcp.exceptions import ToolError

from devtask_mcp import server


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    """Swap the module-level DevTaskClient for a recording fake."""

    class _FakeClient:
        def __init__(self):
            self.calls: list[tuple[str, dict]] = []
            self.responses: dict[str, object] = {
                "create_task": {"slug": "task-1", "title": "ok"},
                "update_task": {"slug": "task-3", "title": "ok"},
                "get_task_by_slug": {"slug": "task-4", "title": "ok", "detail": "..."},
                "find_children": [{"slug": "task-5", "title": "child", "detail": "..."}],
            }

        async def create_task(self, body):
            self.calls.append(("create_task", body))
            return self.responses["create_task"]

        async def update_task(self, slug, body):
            self.calls.append(("update_task", body))
            return {"slug": slug, "updated": True}

        async def get_task_by_slug(self, slug, with_parent=False):
            self.calls.append(("get_task", {"slug": slug, "with_parent": with_parent}))
            return self.responses["get_task_by_slug"]

        async def find_children(self, parent_slug):
            self.calls.append(("find_children", {"parent_slug": parent_slug}))
            return self.responses["find_children"]

    fake = _FakeClient()
    monkeypatch.setattr(server, "client", fake)
    return fake


# --- /tmp safety net -------------------------------------------------------


def test_read_temp_markdown_rejects_relative_path():
    with pytest.raises(ToolError):
        server._read_temp_markdown("plan.md")


def test_read_temp_markdown_rejects_outside_tmp(tmp_path):
    outside = tmp_path / "plan.md"
    outside.write_text("nope", encoding="utf-8")
    with pytest.raises(ToolError):
        server._read_temp_markdown(str(outside))


def test_read_temp_markdown_rejects_non_md():
    target = Path("/tmp/devtask-ct-test.txt")
    target.write_text("nope", encoding="utf-8")
    try:
        with pytest.raises(ToolError):
            server._read_temp_markdown(str(target))
    finally:
        target.unlink(missing_ok=True)


def test_read_temp_markdown_rejects_oversize():
    huge = Path("/tmp/devtask-ct-huge.md")
    huge.write_text("a" * (server.MAX_MARKDOWN_FILE_BYTES + 1), encoding="utf-8")
    try:
        with pytest.raises(ToolError):
            server._read_temp_markdown(str(huge))
    finally:
        huge.unlink(missing_ok=True)


def test_read_temp_markdown_accepts_tmp_file():
    target = Path("/tmp/devtask-ct-ok.md")
    target.write_text("hello", encoding="utf-8")
    try:
        assert server._read_temp_markdown(str(target)) == "hello"
    finally:
        target.unlink(missing_ok=True)


# --- tool signatures --------------------------------------------------------


def _tool_params(tool_name):
    tools = asyncio.run(server.mcp.list_tools())
    tool = next(t for t in tools if t.name == tool_name)
    return tool.parameters["properties"]


def test_create_task_tool_surfaces_detail():
    """create_task carries optional detail + all structured fields."""
    params = _tool_params("create_task")
    assert "detail" in params
    assert "title" in params
    assert "parent_slug" in params
    # No legacy long-text fields.
    for key in ("description", "acceptance_criteria", "constraints", "context_pointers"):
        assert key not in params, key


def test_update_task_tool_surfaces_detail():
    """update_task carries optional detail + all state fields."""
    params = _tool_params("update_task")
    assert "detail" in params
    assert "status" in params
    for key in ("description", "acceptance_criteria", "constraints", "context_pointers"):
        assert key not in params, key


# --- read-side contracts ----------------------------------------------------


def test_list_children_returns_summary_records(_patch_client):
    payload = json.loads(asyncio.run(server.list_children(parent_slug="task-1")))
    assert payload[0]["slug"] == "task-5"
    assert "detail" not in payload[0]


# --- write-side contracts ---------------------------------------------------


def test_create_task_sends_inline_detail(_patch_client):
    payload = json.loads(
        asyncio.run(
            server.create_task(
                title="My subtask",
                task_type="优化",
                priority="P1 高",
                scope="后端-Python",
                kind="subtask",
                parent_slug="task-1",
                detail="## Goal\n\nDo it.\n\n## Acceptance Criteria\n\n- [ ] done\n",
            )
        )
    )
    assert payload == {"slug": "task-1", "title": "ok"}
    method, body = _patch_client.calls[0]
    assert method == "create_task"
    assert body["title"] == "My subtask"
    assert body["kind"] == "subtask"
    assert body["parent_slug"] == "task-1"
    assert "## Goal" in body["detail"]


def test_create_task_omits_detail_when_not_given(_patch_client):
    payload = json.loads(
        asyncio.run(
            server.create_task(
                title="No detail",
                task_type="优化",
                priority="P2 中",
                scope="前端-React",
            )
        )
    )
    assert payload == {"slug": "task-1", "title": "ok"}
    assert "detail" not in _patch_client.calls[0][1]


def test_update_task_sends_status(_patch_client):
    payload = json.loads(
        asyncio.run(server.update_task(slug="task-1", status="进行中"))
    )
    assert payload == {"slug": "task-1", "updated": True}
    method, body = _patch_client.calls[0]
    assert method == "update_task"
    assert body == {"status": "进行中"}


def test_update_task_sends_detail(_patch_client):
    payload = json.loads(
        asyncio.run(
            server.update_task(
                slug="task-1",
                detail="## Goal\n\nRevised goal.\n\n## Acceptance Criteria\n\n- [ ] ok\n",
            )
        )
    )
    method, body = _patch_client.calls[0]
    assert method == "update_task"
    assert "## Goal" in body["detail"]


def test_create_task_via_document_file_sends_compiled_body(_patch_client):
    doc_path = Path("/tmp/devtask-ct-create.md")
    doc_path.write_text(
        "---\n"
        'title: "From doc"\n'
        'task_type: "优化"\n'
        'priority: "P1 高"\n'
        'scope: "后端-Python"\n'
        'kind: "subtask"\n'
        "for_agent: true\n"
        "---\n\n"
        "## Goal\n\nDo the thing.\n\n"
        "## Acceptance Criteria\n\n- [ ] it works\n",
        encoding="utf-8",
    )
    try:
        payload = json.loads(
            asyncio.run(server.create_task(document_file=str(doc_path)))
        )
        assert payload == {"slug": "task-1", "title": "ok"}
    finally:
        doc_path.unlink(missing_ok=True)

    method, body = _patch_client.calls[0]
    assert method == "create_task"
    assert body["title"] == "From doc"
    assert body["type"] == "优化"
    assert body["kind"] == "subtask"
    assert body["for_agent"] is True
    assert "## Goal" in body["detail"]
    for legacy in (
        "description",
        "acceptance_criteria",
        "constraints",
        "context_pointers",
    ):
        assert legacy not in body


def test_create_task_rejects_invalid_document_file(_patch_client):
    with pytest.raises(ToolError):
        asyncio.run(server.create_task(document_file="/etc/passwd"))


def test_update_task_bulk_completes(_patch_client):
    payload = json.loads(
        asyncio.run(
            server.update_task(
                slugs=["task-1", "task-2", "task-3"],
            )
        )
    )
    assert payload["succeeded"] == ["task-1", "task-2", "task-3"]
    assert payload["failed"] == []


def test_update_task_rejects_slug_and_slugs(_patch_client):
    with pytest.raises(ToolError):
        asyncio.run(
            server.update_task(
                slug="task-1",
                slugs=["task-1", "task-2"],
                status="进行中",
            )
        )
