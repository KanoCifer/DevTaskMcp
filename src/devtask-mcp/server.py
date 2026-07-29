from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .client import DevTaskAPIError, DevTaskClient, DevTaskError
from .models import TaskKind, TaskPriority, TaskStatus, TaskType
from .task_document import DocumentError, parse_task_document
from .views import VIEWS, ViewError, render_view

logger = logging.getLogger("devtask-mcp")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP("devtask", mask_error_details=True)

# Module-level client — FastMCP stdio runs one server per agent session so a
# single long-lived client is fine.
client = DevTaskClient()


def _iso(dt: datetime | None) -> str | None:
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
        raise ToolError("document_file 必须指向 /tmp 下存在的 Markdown 文件") from exc

    if resolved.suffix.lower() != ".md" or not resolved.is_file():
        raise ToolError("document_file 必须指向 /tmp 下的 .md 文件")

    try:
        if resolved.stat().st_size > MAX_MARKDOWN_FILE_BYTES:
            raise ToolError(
                f"document_file 不能超过 {MAX_MARKDOWN_FILE_BYTES // 1024 // 1024} MB"
            )
        return resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError("document_file 必须是 UTF-8 编码的 Markdown 文件") from exc
    except OSError as exc:
        raise ToolError(f"无法读取 document_file: {exc}") from exc


# -------------------------------------------------------------------------- #
# Tool: get_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def get_task(
    slug: str,
    with_parent: bool = False,
    view: str = "summary",
) -> str:
    """Fetch a single task by slug. view: summary|execute|review|full (default summary)."""
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
# Tool: create_task
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def create_task(
    title: str | None = None,
    task_type: TaskType | None = None,
    priority: TaskPriority | None = None,
    scope: str | None = None,
    kind: TaskKind | None = None,
    parent_slug: str | None = None,
    for_agent: bool = False,
    blocked_by: list[str] | None = None,
    due_date: str | None = None,
    detail: str | None = None,
    document_file: str | None = None,
) -> str:
    """Create a task from inline params, or from a Task Document file (document_file takes precedence)."""
    if document_file is not None:
        text = _read_temp_markdown(document_file)
        try:
            document = parse_task_document(text)
        except DocumentError as exc:
            raise ToolError(f"Task Document 解析失败: {exc}") from exc
        body = document.to_body()
    else:
        if title is None or task_type is None or priority is None or scope is None:
            missing = [
                name
                for name, val in [
                    ("title", title),
                    ("task_type", task_type),
                    ("priority", priority),
                    ("scope", scope),
                ]
                if val is None
            ]
            raise ToolError(
                f"缺少必填参数: {', '.join(missing)}（使用 document_file 时除外）"
            )
        body = {
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
            "title": raw.get("title", body.get("title")),
        },
        ensure_ascii=False,
        default=_to_jsonable,
    )


# -------------------------------------------------------------------------- #
# Tool: update_task — state + detail edits, also bulk-complete
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def update_task(
    slug: str | None = None,
    slugs: list[str] | None = None,
    title: str | None = None,
    task_type: TaskType | None = None,
    priority: TaskPriority | None = None,
    scope: str | None = None,
    status: TaskStatus | None = None,
    sort_order: int | None = None,
    due_date: str | None = None,
    for_agent: bool | None = None,
    blocked_by: list[str] | None = None,
    kind: TaskKind | None = None,
    parent_slug: str | None = None,
    detail: str | None = None,
) -> str | None:
    """Update a task's fields and/or detail. Use slug (single) or slugs (batch status update, mutually exclusive)."""
    if slug is not None and slugs is not None:
        raise ToolError("slug 和 slugs 不能同时提供")
    if slugs is not None:
        # Batch mode: status-only update for multiple tasks.
        sem = asyncio.Semaphore(5)

        async def _update_one(s: str) -> dict:
            async with sem:
                try:
                    await client.update_task(s, {"status": status or "已完成"})
                    return {"slug": s, "ok": True}
                except DevTaskAPIError as exc:
                    return {"slug": s, "ok": False, "error": exc.message}
                except Exception as exc:  # noqa: BLE001
                    return {"slug": s, "ok": False, "error": str(exc)}

        results = await asyncio.gather(
            *[_update_one(s) for s in slugs], return_exceptions=True
        )
        succeeded = [r["slug"] for r in results if isinstance(r, dict) and r.get("ok")]
        failed = [
            {"slug": r["slug"], "error": r.get("error", "unknown")}
            for r in results
            if isinstance(r, dict) and not r.get("ok")
        ]
        return json.dumps(
            {"succeeded": succeeded, "failed": failed},
            ensure_ascii=False,
            default=_to_jsonable,
        )

    if slug is not None:
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
# Tool: list_children
# -------------------------------------------------------------------------- #


@mcp.tool()
@_handle_errors
async def list_children(parent_slug: str) -> str:
    """List summary records for all children of a parent spec slug."""
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
    sys.exit(0)
