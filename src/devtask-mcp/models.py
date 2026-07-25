"""Pydantic models mapping the go-backend DevTask DTOs.

v3: the legacy long-text fields (``description``, ``acceptance_criteria``,
``constraints``, ``context_pointers``) still appear on the wire while the
backend completes its migration.  This module keeps them in
:class:`DevTaskOut` so the API client can still parse the backend
response, but the MCP tools and view layer never surface them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Enums — string literals matching the Go backend's Chinese constants.
# ---------------------------------------------------------------------------

TaskType = Literal["问题", "功能需求", "优化", "技术债"]
TaskPriority = Literal["P0 紧急", "P1 高", "P2 中", "P3 低"]
# Scope 去 enum 化：仍是 str，Literal 仅作常见示例提示，不限制值。
TaskScope = str
TaskStatus = Literal["待评估", "待排期", "进行中", "已搁置", "已完成"]
TaskKind = Literal["spec", "subtask"]

# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class DevTaskOut(BaseModel):
    """A single dev-task as returned by the API.

    v3: ``detail`` is the only long-text field.  ``description``,
    ``acceptance_criteria``, ``constraints`` and ``context_pointers``
    are kept here purely for the wire format and should be ignored by
    new code.  The view layer parses ``detail`` into structured
    sections.
    """

    id: str
    user_id: int
    title: str
    description: Optional[str] = None
    detail: Optional[str] = None
    type: TaskType
    priority: TaskPriority
    scope: TaskScope
    status: TaskStatus
    sort_order: int = 0
    due_date: Optional[datetime] = None
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime
    # Spec
    acceptance_criteria: Optional[str] = None
    constraints: Optional[str] = None
    context_pointers: Optional[str] = None
    # Who / Dependencies
    for_agent: bool = False
    blocked_by: list[str] = []
    # Slug —— task-N 格式，人类可读引用
    slug: str = ""
    # 角色：spec / subtask；parent 自身为 spec 时为空，兼容旧数据
    kind: Optional[TaskKind] = None
    # 子任务归属的 spec slug；spec 自身为 None
    parent_slug: Optional[str] = None
    # with_parent=true 且 parent_slug 非空时返回的父 spec 数据。
    # 自引用 Optional —— 无父或未请求时为 None。
    parent: Optional["DevTaskOut"] = None


class PaginationOut(BaseModel):
    """Pagination envelope from list responses."""

    page: int
    per_page: int
    total: int
    pages: int
    has_prev: bool
    has_next: bool
    prev_num: Optional[int] = None
    next_num: Optional[int] = None


class DevTaskListOut(BaseModel):
    """Top-level `data` payload of GET /dev-tasks."""

    tasks: list[DevTaskOut]
    pagination: PaginationOut
