"""FastMCP server exposing tools over stdio.

Tools
-----
- list_dev_tasks      — GET  /dev-tasks   (filter + paginate, per_page cap 20)
- get_dev_task_by_slug — GET  /dev-tasks/:slug?with_parent=true 附带父 spec
- create_dev_task     — POST /dev-tasks
- batch_create_tasks  — POST /dev-tasks × N（并发封装，上限 20）
- update_dev_task     — PATCH /dev-tasks/:slug
- get_frontier_tasks  — GET  /dev-tasks/frontier
- list_children       — GET  /dev-tasks?kind=subtask (走客户端 parent_slug 过滤)
- batch_update_status — POST /dev-tasks/batch-status (多 slug 批量改状态)
- transition_plan     — 一步推 spec + 子任务到目标状态（封装 slug 拼合 + batch_status)

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
from .models import BatchTaskRequest, TaskKind, TaskPriority, TaskScope, TaskStatus, TaskType

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
            logger.error(
                "工具 %s API 错误 [%s]: %s", func.__name__, exc.status, exc.message
            )
            raise ToolError(f"API 错误（HTTP {exc.status}）：{exc.message}") from exc
        except DevTaskError as exc:
            logger.error("工具 %s 配置错误: %s", func.__name__, exc)
            raise ToolError(str(exc)) from exc
        except Exception as exc:
            logger.exception("工具 %s 发生未预期错误", func.__name__)
            raise ToolError("服务器内部错误，请查看日志") from exc

    return wrapper


# -------------------------------------------------------------------------- #
# Shared helpers
# -------------------------------------------------------------------------- #

MAX_BATCH_CREATE = 20  # 与 client.MAX_PER_PAGE 同值，单写一份用于入口校验


def _task_body(t: BatchTaskRequest) -> dict[str, Any]:
    """把 BatchTaskRequest 转成 POST /dev-tasks 的 JSON body。

    单一改动点：create_dev_task 与 batch_create_tasks 都经这里，
    后端增字段时只改一处。
    """
    body: dict[str, Any] = {
        "title": t.title,
        "type": t.task_type,
        "priority": t.priority,
        "scope": t.scope,
        "for_agent": t.for_agent,
    }
    if t.description is not None:
        body["description"] = t.description
    if t.detail is not None:
        body["detail"] = t.detail
    if t.due_date is not None:
        body["due_date"] = t.due_date
    if t.acceptance_criteria is not None:
        body["acceptance_criteria"] = t.acceptance_criteria
    if t.constraints is not None:
        body["constraints"] = t.constraints
    if t.context_pointers is not None:
        body["context_pointers"] = t.context_pointers
    if t.blocked_by is not None:
        body["blocked_by"] = t.blocked_by
    if t.kind is not None:
        body["kind"] = t.kind
    if t.parent_slug is not None:
        body["parent_slug"] = t.parent_slug
    return body


# -------------------------------------------------------------------------- #
# Tool: list_dev_tasks
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def list_dev_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    task_type: Optional[TaskType] = None,
    kind: Optional[TaskKind] = None,
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
        kind: Filter by role. One of: 'spec', 'subtask'.
            None = no filter.
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
        kind=kind,
        for_agent=for_agent,
        include_deleted=include_deleted,
        page=page,
        per_page=per_page,
    )
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: get_dev_task_by_slug
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def get_dev_task_by_slug(slug: str, with_parent: bool = False) -> str:
    """Fetch a single dev-task by its slug (task-1, task-2...).

    The slug is the unique, human-readable identifier for a task — use it
    for all conversation, kanban UI, and MCP tool references. 后端已
    slug 化，不再接受 ObjectID。

    The response includes spec fields (acceptance_criteria, constraints,
    context_pointers), dependency info (for_agent, blocked_by), role
    (kind), parent link (parent_slug), and slug. Read them before starting
    work. context_pointers short-circuits file discovery by telling you
    exactly which paths are relevant.

    当任务为子任务（parent_slug 非空）且 with_parent=True 时，后端额
    外在响应的 "parent" 字段里嵌套返回父 spec 的完整数据——省去客户端
    用 parent_slug 再查一次的往返。默认 False 保持轻量。

    Args:
        slug: The task slug, e.g. "task-42".
        with_parent: 是否附带父 spec 数据（仅对带 parent_slug 的子任务
            生效）。默认 False。
    """
    raw = await client.get_task_by_slug(slug, with_parent=with_parent)
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
    kind: Optional[TaskKind] = None,
    parent_slug: Optional[str] = None,
) -> str:
    """Create a new dev-task. New tasks start at status '待评估'.

    The response includes a slug (e.g. "task-1") — use it for all future
    references. It is more readable in conversation, kanban UI, and MCP
    tool calls.

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
        blocked_by: List of same-level task slugs that must be done before
            this one (execution-order precedence). Pass [] when no
            dependencies. 注意：不再用于指向 parent——子→父的结构归属
            用 parent_slug 承载。
        kind: Task role. 'spec' = 规划节点，
            'subtask' = 可执行子任务。None 时后端默认 spec。
        parent_slug: 子任务归属的 spec slug（如 "task-5"）。spec 自身
            留 None。设置后 list_children(parent_slug) 直接索引返回子任务。
    """
    body = _task_body(
        BatchTaskRequest(
            title=title,
            task_type=task_type,
            priority=priority,
            scope=scope,
            description=description,
            detail=detail,
            due_date=due_date,
            acceptance_criteria=acceptance_criteria,
            constraints=constraints,
            context_pointers=context_pointers,
            for_agent=for_agent,
            blocked_by=blocked_by,
            kind=kind,
            parent_slug=parent_slug,
        )
    )

    raw = await client.create_task(body)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: batch_create_tasks
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def batch_create_tasks(tasks: list[BatchTaskRequest]) -> str:
    """Batch-create multiple dev-tasks in a single MCP round-trip.

    Internally dispatches all creates concurrently (asyncio.gather) and
    returns a per-item summary. Partial failures are **not** rolled back —
    they are reported in the ``failed`` list so the agent can retry only
    the failing items.

    单次上限 20 条；超出会被截断，只处理前 20 条。

    Important constraint: tasks in a single batch must be **independent**
    of each other. References via ``blocked_by`` to slugs that do not
    yet exist (e.g. a sibling in the same batch) will fail on the
    backend. For execution-order dependencies, create the batch first,
    then use ``update_dev_task`` to wire up ``blocked_by`` afterwards.
    ``parent_slug`` may reference an already-existing spec without
    restriction.

    The response includes a ``succeeded`` list (index + slug + title),
    a ``failed`` list (index + title + error message), and a ``summary``
    string like ``"7/10 created"``.

    Args:
        tasks: List of task creation requests (1..20 items). Each item
            uses the same fields as ``create_dev_task``: title,
            task_type, priority, scope are required; all other fields
            are optional. New tasks always start at status '待评估'.
    """
    if len(tasks) > MAX_BATCH_CREATE:
        raise ToolError(
            f"单次最多 {MAX_BATCH_CREATE} 条，当前 {len(tasks)} 条，请分批创建"
        )

    bodies = [_task_body(t) for t in tasks]
    raw = await client.batch_create_tasks(bodies)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: update_dev_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def update_dev_task(
    slug: str,
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
    kind: Optional[TaskKind] = None,
    parent_slug: Optional[str] = None,
) -> str:
    """Partially update a dev-task. Omitted fields are left unchanged.

    All text fields (description, detail, acceptance_criteria, constraints,
    context_pointers) support **Markdown formatting** — conventions match
    create_dev_task.

    Args:
        slug: The task slug, e.g. "task-42".
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
        blocked_by: Replace same-level dependency list entirely. Pass [] to
            clear. 注意：不再用于指向 parent——子→父结构归属用
            parent_slug 承载。
        kind: Update task role ('spec' / 'subtask').
        parent_slug: Update parent spec slug; None leaves it unchanged.
            Note: the backend DTO treats null as "no-op" rather than "clear",
            so this param cannot detach a child from its parent — only
            re-parent it to a different spec slug.
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
    if kind is not None:
        body["kind"] = kind
    if parent_slug is not None:
        body["parent_slug"] = parent_slug

    raw = await client.update_task(slug, body)
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
    - 角色为 subtask（kind == "subtask"，即可执行单元）
    - in status '待排期' (backlog)
    - have no unfinished dependency blockers —— blocked_by 现在只含
      同层前置依赖（执行顺序），不再指向 parent，因此不需要 hack 跳过
      "for_agent=false 的 blocked_by"
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
    """Return all child tasks of a parent (spec) task.

    走后端 parent_slug 索引查询，直接返回所有 parent_slug == 给定
    slug 的子任务（kind == "subtask"）。不再解析 blocked_by。
    Handles pagination internally — no client-side loop needed.
    Returns the full task objects (including acceptance_criteria,
    context_pointers, etc.) so callers never need a follow-up
    get_dev_task_by_slug per child.

    Use this in skills wherever you need a parent's children: finding the
    next task to execute, aggregating sibling completion, or recursive verify.

    Args:
        parent_slug: The parent (spec) task slug, e.g. "task-42".
    """
    raw = await client.find_children(parent_slug)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: batch_update_status
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def batch_update_status(slugs: list[str], status: TaskStatus) -> str:
    """Batch-update multiple dev-tasks to the same status in one call.

    Use this to move a group of related tasks from one lifecycle state to
    another — e.g. after planning, flip a spec + all its subtasks from
    '待评估' to '待排期' in a single round-trip.

    后端未做状态机校验，任意 → 任意都允许（与单条 update_dev_task 一致）。
    已处于目标状态的任务会被跳过，不触发多余的 DB 写。

    Args:
        slugs: 要修改状态的任务 slug 列表（1..20）。
            例：["task-5", "task-6", "task-7"]。
        status: 目标状态。
            One of: '待评估', '待排期', '进行中', '已搁置', '已完成'.
    """
    raw = await client.batch_status(slugs, status)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: transition_plan
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def transition_plan(parent_slug: str, status: TaskStatus = "待排期") -> str:
    """一步把 spec + 所有子任务翻到目标状态（默认 待排期）。

    典型场景：devtask-plan 产出后，把 spec 和它的子任务从「待评估」
    批量推进到「待排期」，让它们出现在 frontier 里可被领取。

    内部实现：list_children(parent_slug) 取全部子任务 slug → 拼上
    parent 自身 → 调 batch_status 一次性写入。

    后端未做状态机校验，任意 → 任意都允许。

    Args:
        parent_slug: spec 的 slug（如 "task-5"）。
        status: 目标状态，默认 '待排期'。
            One of: '待评估', '待排期', '进行中', '已搁置', '已完成'.
    """
    raw = await client.transition_plan(parent_slug, status)
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
