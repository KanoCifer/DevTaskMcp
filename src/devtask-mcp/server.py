from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .client import DevTaskAPIError, DevTaskClient, DevTaskError
from .models import (
    BatchTaskRequest,
    TaskKind,
    TaskPriority,
    TaskStatus,
    TaskType,
)

logger = logging.getLogger("devtask-mcp")

# -------------------------------------------------------------------------- #
# 工具调用次数统计 —— 存活期内累计,退出时刷盘到 ~/.claude/devtask-mcp-usage.json
# -------------------------------------------------------------------------- #

USAGE_PATH = Path.home() / ".claude" / "devtask-mcp-usage.json"
_usage_counts: dict[str, int] = {}


def _load_usage() -> None:
    global _usage_counts
    if USAGE_PATH.exists():
        try:
            _usage_counts = json.loads(USAGE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("usage 文件损坏,重置计数: %s", exc)
            _usage_counts = {}


def _save_usage() -> None:
    try:
        USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        USAGE_PATH.write_text(
            json.dumps(_usage_counts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("写 usage 文件失败: %s", exc)


def _count_tool(func: Callable) -> Callable:
    """在 _handle_errors 之内再包一层,仅成功调用才计入统计。"""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await func(*args, **kwargs)
        _usage_counts[func.__name__] = _usage_counts.get(func.__name__, 0) + 1
        return result

    return wrapper


_load_usage()

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

    单一改动点：create_task 与 batch_create_tasks 都经这里，
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
# Tool: list_tasks
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def list_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    task_type: Optional[TaskType] = None,
    kind: Optional[TaskKind] = None,
    for_agent: Optional[bool] = None,
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 10,
) -> str:
    """List dev-tasks with optional filters. Results are JSON-serialized.

    Args: see type hints for field values and allowed strings.
        per_page: capped at 20.
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
# Tool: get_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def get_task(slug: str, with_parent: bool = False) -> str:
    """Fetch a single task by slug. Returns all fields (spec, deps, parent link).

    Args:
        slug: e.g. "task-42".
        with_parent: When True, includes parent spec data for subtasks.
    """
    raw = await client.get_task_by_slug(slug, with_parent=with_parent)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: create_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def create_task(
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
    """Create a dev-task (status: 待评估). Response includes a slug for references.

    Text fields (description, detail, acceptance_criteria, constraints,
    context_pointers) support Markdown. title is plain text.

    Args:
        scope: "<layer>-<tech>" format, e.g. "Backend-Go".
        blocked_by: Same-level deps. child→parent via parent_slug.
        kind: "spec" (planning) or "subtask" (executable). Default: spec.
        parent_slug: Attach as child of a spec slug.
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
@_count_tool
@_handle_errors
async def batch_create_tasks(tasks: list[BatchTaskRequest]) -> str:
    """Batch-create 1-20 dev-tasks in one round-trip. Partial failures are reported.

    blocked_by refs to same-batch slugs will fail (slugs not yet assigned).
    Use update_task to wire deps after creation.

    Args:
        tasks: 1-20 items, same fields as create_task.
    """
    if len(tasks) > MAX_BATCH_CREATE:
        raise ToolError(
            f"单次最多 {MAX_BATCH_CREATE} 条，当前 {len(tasks)} 条，请分批创建"
        )

    bodies = [_task_body(t) for t in tasks]
    raw = await client.batch_create_tasks(bodies)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: update_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def update_task(
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
    """Partially update a dev-task. Omitted fields left unchanged.
    Text fields support Markdown (same conventions as create_task).
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
# Tool: complete_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def complete_task(slug: str | list[str]) -> str:
    """把单个或多个任务标记为 已完成。

    Args:
        slug: e.g. "task-42"；或多个 ["task-42","task-43"]。
    """
    slugs = [slug] if isinstance(slug, str) else slug
    results = await asyncio.gather(
        *[client.update_task(s, {"status": "已完成"}) for s in slugs],
        return_exceptions=True,
    )
    succeeded: list[str] = []
    failed: list[dict] = []
    for s, r in zip(slugs, results):
        if isinstance(r, Exception):
            msg = r.message if isinstance(r, DevTaskAPIError) else str(r)
            failed.append({"slug": s, "error": msg})
        else:
            succeeded.append(s)
    return json.dumps(
        {"succeeded": succeeded, "failed": failed},
        ensure_ascii=False,
        default=_to_jsonable,
    )


# -------------------------------------------------------------------------- #
# Tool: get_frontier_tasks
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def get_frontier_tasks(limit: int = 10) -> str:
    """Return for_agent=true subtasks in 待排期, sorted by sort_order ASC.
    Use this to find the next task ready to work.

    Args:
        limit: Max tasks (default 10).
    """
    raw = await client.find_frontier(limit=limit)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: list_children
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def list_children(parent_slug: str) -> str:
    """Return all child tasks (kind=subtask) of a parent spec. Full task objects.
    No pagination loop needed on client side.

    Args:
        parent_slug: The spec slug, e.g. "task-42".
    """
    raw = await client.find_children(parent_slug)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: batch_update_status
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def batch_update_status(slugs: list[str], status: TaskStatus) -> str:
    """Batch-update multiple tasks to the same status in one call.
    Tasks already at target status are skipped.

    Args:
        slugs: 1-20 task slugs.
        status: One of the TaskStatus enum values.
    """
    raw = await client.batch_status(slugs, status)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: transition_plan
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def transition_plan(parent_slug: str, status: TaskStatus = "待排期") -> str:
    """Move spec + all its subtasks to target status (default: 待排期).
    Combines list_children + batch_status in one call.

    Args:
        parent_slug: The spec slug.
        status: Target status, default "待排期".
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
    finally:
        _save_usage()  # 进程退出时把累计计数刷盘
    exit(0)
