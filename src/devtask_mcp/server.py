"""FastMCP server exposing 6 tools over stdio.

Tools
-----
- list_dev_tasks   — GET  /dev-tasks   (filter + paginate, per_page cap 20)
- get_dev_task     — GET  /dev-tasks/:id
- get_dev_task_by_slug — GET  /dev-tasks/by-slug/:slug
- create_dev_task  — POST /dev-tasks
- update_dev_task  — PATCH /dev-tasks/:id
- get_frontier_tasks — GET  /dev-tasks/frontier

Run with:  uv run python -m devtask_mcp.server
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .client import DevTaskAPIError, DevTaskClient, DevTaskError
from .models import TaskPriority, TaskScope, TaskStatus, TaskType

logger = logging.getLogger("devtask-mcp")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP("devtask", mask_error_details=True)

# Module-level client — FastMCP stdio runs one server per agent session so a
# single long-lived client is fine.
client = DevTaskClient()


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _to_jsonable(obj: Any) -> Any:
    """Best-effort JSON-serialisable convert for arbitrary API payloads."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def _handle_errors(func: Callable) -> Callable:
    """Catch DevTask* errors → ToolError (shown to agent);
    catch everything else → mask + log."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except ToolError:
            # Already a ToolError — pass through untouched.
            raise
        except DevTaskAPIError as exc:
            logger.error("工具 %s API 错误 [%s]: %s", func.__name__, exc.status, exc.message)
            raise ToolError(f"API 错误（HTTP {exc.status}）：{exc.message}") from exc
        except DevTaskError as exc:
            logger.error("工具 %s 配置错误: %s", func.__name__, exc)
            raise ToolError(str(exc)) from exc
        except Exception as exc:
            logger.exception("工具 %s 发生未预期错误", func.__name__)
            raise ToolError("服务器内部错误，请查看日志") from exc

    return wrapper


# -------------------------------------------------------------------------- #
# Tool: list_dev_tasks
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def list_dev_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    task_type: Optional[TaskType] = None,
    for_agent: Optional[bool] = None,
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 10,
) -> str:
    """List dev-tasks from your kanocifer-chat board.

    Args:
        status: Filter by lifecycle status.
            One of: '待评估', '待排期', '进行中', '已搁置', '已完成'.
        priority: Filter by urgency.
            One of: 'P0 紧急', 'P1 高', 'P2 中', 'P3 低'.
        task_type: Filter by kind.
            One of: '问题', '功能需求', '优化', '技术债'.
        for_agent: When True, return only tasks ready for agent execution.
            When False, return only tasks for human. None = no filter.
        include_deleted: When True, soft-deleted tasks are also returned.
        page: Page number (1-based).
        per_page: Items per page, capped at 20.
    """
    raw = await client.list_tasks(
        status=status,
        priority=priority,
        task_type=task_type,
        for_agent=for_agent,
        include_deleted=include_deleted,
        page=page,
        per_page=per_page,
    )
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: get_dev_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def get_dev_task(task_id: str) -> str:
    """Fetch a single dev-task by its ObjectID.

    The response includes spec fields (acceptance_criteria, constraints,
    context_pointers), dependency info (for_agent, blocked_by), and slug.
    Read them before starting work. context_pointers short-circuits file
    discovery by telling you exactly which paths are relevant. Use the slug
    for all human-facing references (e.g. "work on task-42").

    Args:
        task_id: The task's ObjectId hex string (24 hex chars).
            Use get_dev_task_by_slug if you have a slug like "task-42".
    """
    raw = await client.get_task(task_id)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


@mcp.tool()
@_handle_errors
async def get_dev_task_by_slug(slug: str) -> str:
    """Fetch a single dev-task by its slug (task-1, task-2...).

    The slug is the human-readable short identifier for a task — prefer it
    over ObjectId for conversation, kanban UI, and MCP tool references.
    All other fields are identical to get_dev_task.

    Args:
        slug: The task slug, e.g. "task-42".
    """
    raw = await client.get_task_by_slug(slug)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: create_dev_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def create_dev_task(
    title: str,
    task_type: TaskType,
    priority: TaskPriority,
    scope: str,
    description: Optional[str] = None,
    detail: Optional[str] = None,
    due_date: Optional[str] = None,
    acceptance_criteria: Optional[str] = None,
    constraints: Optional[str] = None,
    context_pointers: Optional[str] = None,
    for_agent: bool = False,
    blocked_by: Optional[list[str]] = None,
) -> str:
    """Create a new dev-task. New tasks start at status '待评估'.

    The response includes a slug (e.g. "task-1") — use it for all future
    references instead of the ObjectId. It is more readable in conversation,
    kanban UI, and MCP tool calls.

    All text fields (description, detail, acceptance_criteria, constraints,
    context_pointers) support **Markdown formatting**. Suggested usage:
    acceptance_criteria as a Markdown list, constraints as a list or table,
    context_pointers with paths wrapped in code blocks. title stays plain
    text.

    Args:
        title: Task title (required). Plain text, no Markdown markup.
        task_type: One of '问题', '功能需求', '优化', '技术债'.
        priority: One of 'P0 紧急', 'P1 高', 'P2 中', 'P3 低'.
        scope: Task scope in "<scope>-<tech>" format (required).
            Examples: '前端-React', '后端-Go', 'AI-LangChain',
            'Docs-用户手册', '通用'. Free-form string — not a closed enum.
        description: Short description (optional). Supports Markdown.
        detail: Long-form detail (optional). Supports Markdown.
        due_date: ISO-8601 datetime string, e.g. '2026-09-01T00:00:00'.
            Pass whatever your JSON client gives; the backend parses RFC-3339.
        acceptance_criteria: Conditions that must be met for this task to be
            considered done. Agent uses these as a self-check before resolve.
            **Use a Markdown list**.
        constraints: Hard boundaries — files not to touch, tech stack
            requirements, etc. Agent treats these as non-negotiable.
            **Use a Markdown list or table**.
        context_pointers: Paths to relevant code / docs / ADRs, e.g.
            'internal/auth/, docs/adr/0003'. Saves agent a file-discovery pass.
            **Wrap paths in code blocks**.
        for_agent: When True, mark this task as ready for agent execution.
            Default False (human task).
        blocked_by: List of task IDs that must be done before this one.
            Pass [] when no dependencies.
    """
    body: dict[str, Any] = {
        "title": title,
        "type": task_type,
        "priority": priority,
        "scope": scope,
        "for_agent": for_agent,
    }
    if description is not None:
        body["description"] = description
    if detail is not None:
        body["detail"] = detail
    if due_date is not None:
        body["due_date"] = due_date
    if acceptance_criteria is not None:
        body["acceptance_criteria"] = acceptance_criteria
    if constraints is not None:
        body["constraints"] = constraints
    if context_pointers is not None:
        body["context_pointers"] = context_pointers
    if blocked_by is not None:
        body["blocked_by"] = blocked_by

    raw = await client.create_task(body)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: update_dev_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def update_dev_task(
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    detail: Optional[str] = None,
    task_type: Optional[TaskType] = None,
    priority: Optional[TaskPriority] = None,
    scope: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    sort_order: Optional[int] = None,
    due_date: Optional[str] = None,
    acceptance_criteria: Optional[str] = None,
    constraints: Optional[str] = None,
    context_pointers: Optional[str] = None,
    for_agent: Optional[bool] = None,
    blocked_by: Optional[list[str]] = None,
) -> str:
    """Partially update a dev-task. Omitted fields are left unchanged.

    All text fields (description, detail, acceptance_criteria, constraints,
    context_pointers) support **Markdown formatting** — conventions match
    create_dev_task.

    Args:
        task_id: The task's ObjectId hex string or slug (task-N).
        title: New title (optional). Plain text.
        description: New description (optional). Supports Markdown.
        detail: New detail (optional). Supports Markdown.
        task_type: One of '问题', '功能需求', '优化', '技术债'.
        priority: One of 'P0 紧急', 'P1 高', 'P2 中', 'P3 低'.
        scope: Free-form "<层>-<技术>" string (see create_dev_task docs).
        status: One of '待评估', '待排期', '进行中', '已搁置', '已完成'.
        sort_order: Integer sort key (optional).
        due_date: ISO-8601 datetime string.
        acceptance_criteria: Conditions for considering this task done.
            **Use a Markdown list**.
        constraints: Hard boundaries (files / tech stack / etc).
            **Use a Markdown list or table**.
        context_pointers: Paths to relevant code / docs / ADRs.
            **Wrap paths in code blocks**.
        for_agent: Toggle agent-claimable flag.
        blocked_by: Replace the dependency list entirely. Pass [] to clear.
    """
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if detail is not None:
        body["detail"] = detail
    if task_type is not None:
        body["type"] = task_type
    if priority is not None:
        body["priority"] = priority
    if scope is not None:
        body["scope"] = scope
    if status is not None:
        body["status"] = status
    if sort_order is not None:
        body["sort_order"] = sort_order
    if due_date is not None:
        body["due_date"] = due_date
    if acceptance_criteria is not None:
        body["acceptance_criteria"] = acceptance_criteria
    if constraints is not None:
        body["constraints"] = constraints
    if context_pointers is not None:
        body["context_pointers"] = context_pointers
    if for_agent is not None:
        body["for_agent"] = for_agent
    if blocked_by is not None:
        body["blocked_by"] = blocked_by

    raw = await client.update_task(task_id, body)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: get_frontier_tasks
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def get_frontier_tasks(limit: int = 10) -> str:
    """Return tasks the agent can claim next — Pocock's frontier.

    Frontier = tasks that are:
    - marked for_agent=true
    - in status '待排期' (backlog)
    - have no unfinished *dependency* blockers — parent links (blocked_by
      containing a slug whose task has for_agent=false) are ignored;
      only genuine precedence blockers (blocked_by containing a slug whose
      task has for_agent=true) count as blocking
    - not soft-deleted

    Ordered by sort_order ASC, then created_at DESC. Use this as your first
    call when the user says "do the next task" — it tells you exactly what's
    ready to be worked.

    Args:
        limit: Max tasks to return (default 10).
    """
    raw = await client.find_frontier(limit=limit)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: list_children
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def list_children(parent_slug: str) -> str:
    """Return all child tasks of a parent task.

    Finds every for_agent=true task whose blocked_by contains the given
    parent slug. Handles pagination internally — no client-side loop needed.
    Returns the full task objects (including acceptance_criteria,
    context_pointers, etc.) so callers never need a follow-up
    get_dev_task_by_slug per child.

    Use this in skills wherever you need a parent's children: finding the
    next task to execute, aggregating sibling completion, or recursive verify.

    Args:
        parent_slug: The parent task slug, e.g. "task-42".
    """
    raw = await client.find_children(parent_slug)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(mcp.run_stdio_async())
    except KeyboardInterrupt:
        pass
