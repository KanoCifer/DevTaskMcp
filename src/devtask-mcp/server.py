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
from .models import TaskKind, TaskPriority, TaskStatus, TaskType
from .task_document import DocumentError, parse_task_document
from .views import VIEWS, ViewError, render_view

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
    """成功调用才计入统计,每次成功后增量刷盘(保证崩溃/强杀不丢数据)。"""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await func(*args, **kwargs)
        _usage_counts[func.__name__] = _usage_counts.get(func.__name__, 0) + 1
        _save_usage()
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

MAX_MARKDOWN_FILE_BYTES = 2 * 1024 * 1024


def _read_temp_markdown(file_path: str) -> str:
    """Read Markdown staged in the shared temporary directory.

    File-backed text avoids sending the same long plan once to the model and
    again in an MCP argument.  Restricting reads to the temporary directory
    prevents this convenience parameter from becoming an arbitrary file-read
    primitive when the MCP server calls the remote API.
    """
    candidate = Path(file_path)
    if not candidate.is_absolute():
        raise ToolError("document_file 必须是 /tmp 下的绝对路径")

    try:
        resolved = candidate.resolve(strict=True)
        temp_root = Path("/tmp").resolve()
        resolved.relative_to(temp_root)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise ToolError(
            "document_file 必须指向 /tmp 下存在的 Markdown 文件"
        ) from exc

    if resolved.suffix.lower() != ".md" or not resolved.is_file():
        raise ToolError("document_file 必须指向 /tmp 下的 .md 文件")

    try:
        if resolved.stat().st_size > MAX_MARKDOWN_FILE_BYTES:
            raise ToolError(
                f"document_file 不能超过 {MAX_MARKDOWN_FILE_BYTES // 1024 // 1024} MB"
            )
        return resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError(
            "document_file 必须是 UTF-8 编码的 Markdown 文件"
        ) from exc
    except OSError as exc:
        raise ToolError(f"无法读取 document_file: {exc}") from exc


# -------------------------------------------------------------------------- #
# Tool: get_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def get_task(
    slug: str,
    with_parent: bool = False,
    view: str = "summary",
) -> str:
    """Fetch a single task by slug. Returns parsed views (v3).

    Args:
        slug: e.g. "task-42".
        with_parent: When True, includes parent spec data for subtasks
            (rendered with view="summary" regardless of the caller's
            view choice, to keep parent lookups cheap).
        view: One of ``summary``, ``execute``, ``review``, ``full``.
            Defaults to ``summary`` so the agent never accidentally
            pulls the full detail into context.
    """
    if view not in VIEWS:
        raise ToolError(f"未知 view: {view!r}，必须是 {list(VIEWS)}")
    raw = await client.get_task_by_slug(slug, with_parent=with_parent)
    if view == "full":
        rendered = raw
    else:
        try:
            rendered = render_view(raw, view)
        except ViewError as exc:
            raise ToolError(str(exc)) from exc
    if with_parent and "parent" in raw and isinstance(raw["parent"], dict):
        parent_view = render_view(raw["parent"], "summary")
        rendered = dict(rendered)
        rendered["parent"] = parent_view
    return json.dumps(rendered, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: create_task — inline detail for subtasks
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def create_task(
    title: str,
    task_type: TaskType,
    priority: TaskPriority,
    scope: str,
    kind: Optional[TaskKind] = None,
    parent_slug: Optional[str] = None,
    for_agent: bool = False,
    blocked_by: Optional[list[str]] = None,
    due_date: Optional[str] = None,
    detail: Optional[str] = None,
) -> str:
    """Create a dev-task with optional inline Markdown body.

    For rich Task Documents with YAML front matter (spec / simple
    tasks), prefer ``create_task_document``.  This tool is designed
    for programmatic subtask creation where the content is already
    known — pass the Markdown body directly as ``detail``.

    Args:
        title: One-line summary, verb-first.
        task_type: Chinese literal.
        priority: Chinese literal.
        scope: ``<layer>-<tech>`` format.
        kind: ``subtask`` for child tasks; omit for standalone tasks.
        parent_slug: Required when kind=subtask.
        for_agent: Whether the task is claimable by an agent.
        blocked_by: List of same-layer dependency slugs.
        due_date: ISO-8601 date string.
        detail: Optional Markdown body (Goal / Plan / AC sections).
    """
    body: dict[str, Any] = {
        "title": title,
        "type": task_type,
        "priority": priority,
        "scope": scope,
        "for_agent": for_agent,
    }
    if kind is not None:
        body["kind"] = kind
    if parent_slug is not None:
        body["parent_slug"] = parent_slug
    if blocked_by is not None:
        body["blocked_by"] = blocked_by
    if due_date is not None:
        body["due_date"] = due_date
    if detail is not None:
        body["detail"] = detail

    raw = await client.create_task(body)
    return json.dumps(
        {
            "slug": raw.get("slug"),
            "title": raw.get("title", title),
        },
        ensure_ascii=False,
        default=_to_jsonable,
    )


# -------------------------------------------------------------------------- #
# Tool: update_task — state + detail edits
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def update_task(
    slug: str,
    title: Optional[str] = None,
    task_type: Optional[TaskType] = None,
    priority: Optional[TaskPriority] = None,
    scope: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    sort_order: Optional[int] = None,
    due_date: Optional[str] = None,
    for_agent: Optional[bool] = None,
    blocked_by: Optional[list[str]] = None,
    kind: Optional[TaskKind] = None,
    parent_slug: Optional[str] = None,
    detail: Optional[str] = None,
) -> str:
    """Update a task's structured fields and optional Markdown body.

    Status changes (e.g. ``进行中``, ``已搁置``) go here.
    For complete Task Document replacement with YAML front matter,
    only ``create_task_document`` is available — editing happens via
    ``create_task_document`` for new tasks and ``update_task`` with
    the ``detail`` parameter for existing ones.

    Args:
        slug: e.g. "task-42".
        title, task_type, priority, scope, etc.: fields to update.
        detail: Optional new Markdown body (replaces existing detail).
    """
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
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
    if for_agent is not None:
        body["for_agent"] = for_agent
    if blocked_by is not None:
        body["blocked_by"] = blocked_by
    if kind is not None:
        body["kind"] = kind
    if parent_slug is not None:
        body["parent_slug"] = parent_slug
    if detail is not None:
        body["detail"] = detail

    raw = await client.update_task(slug, body)
    return json.dumps(raw, ensure_ascii=False, default=_to_jsonable)


# -------------------------------------------------------------------------- #
# Tool: create_task_document — Task Document v1 entry point
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def create_task_document(document_file: str) -> str:
    """Create a dev-task from a Task Document file (v1 protocol).

    The document is a UTF-8 Markdown file under ``/tmp`` with a YAML front
    matter block delimited by ``---``. Structured fields (title, type,
    priority, scope, kind, due_date, blocked_by, parent_slug, for_agent)
    come from the front matter; the rendered Markdown body becomes the
    task's ``detail``.

    The response is a compact acknowledgement with just the new slug and
    title — agents should call ``get_task(slug, view="execute")`` if they
    need the parsed sections back.

    Args:
        document_file: Absolute path to a UTF-8 Task Document under /tmp.
    """
    text = _read_temp_markdown(document_file)
    try:
        document = parse_task_document(text)
    except DocumentError as exc:
        raise ToolError(f"Task Document 解析失败: {exc}") from exc

    body = document.to_body()
    raw = await client.create_task(body)
    return json.dumps(
        {
            "slug": raw.get("slug"),
            "title": raw.get("title", body.get("title")),
        },
        ensure_ascii=False,
        default=_to_jsonable,
    )


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
# Tool: list_children
# -------------------------------------------------------------------------- #


@mcp.tool()
@_count_tool
@_handle_errors
async def list_children(parent_slug: str) -> str:
    """Return summary records for every child of a parent spec.

    v3: never returns the full task object.  Each child is rendered
    with the ``summary`` view so callers can fan out to ``get_task``
    with a richer view if needed.

    Args:
        parent_slug: The spec slug, e.g. "task-42".
    """
    children = await client.find_children(parent_slug)
    summarised = [render_view(child, "summary") for child in children]
    return json.dumps(summarised, ensure_ascii=False, default=_to_jsonable)


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
