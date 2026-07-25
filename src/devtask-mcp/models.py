"""Pydantic models mapping the go-backend DevTask DTOs.
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
    """A single dev-task as returned by the API."""

    id: str
    user_id: int
    title: str
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
    for_agent: bool = False
    blocked_by: list[str] = []
    slug: str = ""
    kind: Optional[TaskKind] = None
    parent_slug: Optional[str] = None
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
