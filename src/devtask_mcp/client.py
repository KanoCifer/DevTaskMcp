"""Async HTTP client wrapping the kanocifer-chat dev-task API.

Design notes
------------
* Strips the go-backend envelope  ({code, message, data})  at the boundary
  so MCP tools never burn tokens on wrapper fields.
* Raises `DevTaskAPIError` on non-2xx — the server layer lets this propagate
  so the agent sees the backend's message text verbatim (Q16 decision).
* Per-page cap of 20 enforced here (Q17 decision) regardless of caller input.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.environ.get("DEVTASK_API_BASE", "https://api.kanocifer.chat/api/v3")
API_KEY = os.environ.get("DEVTASK_API_KEY", "")

MAX_PER_PAGE = 20


class DevTaskError(RuntimeError):
    """Base for all devtask-mcp errors so callers can catch one type."""


class DevTaskAPIError(DevTaskError):
    """Raised when the backend returns a non-2xx response or envelope code != 0."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class DevTaskConfigError(DevTaskError):
    """Raised when the client is misconfigured (e.g. missing API key)."""


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _unwrap(payload: dict) -> dict | list:
    """Strip {code, message, data} — return `data`."""
    if payload.get("code", 0) != 0:
        raise DevTaskAPIError(status=0, message=payload.get("message", "unknown error"))
    return payload.get("data")


class DevTaskClient:
    """Thin async wrapper around the kanocifer-chat dev-task API."""

    def __init__(self, base_url: str = API_BASE, api_key: str = API_KEY) -> None:
        if not api_key:
            raise DevTaskConfigError(
                "DEVTASK_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base, headers=_headers(), timeout=15.0
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # --------------------------------------------------------------- request

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict | list:
        """Execute an HTTP call, converting httpx errors and non-2xx into
        DevTaskAPIError so the server layer only ever sees our exception type.
        """
        try:
            resp = await self._client.request(
                method, path, params=params, json=json
            )
        except httpx.TimeoutException as exc:
            raise DevTaskAPIError(
                status=0, message=f"请求超时（15s）：{exc}"
            ) from exc
        except httpx.ConnectError as exc:
            raise DevTaskAPIError(
                status=0, message=f"无法连接到 {self._base}，请检查网络或 API 地址"
            ) from exc
        except httpx.HTTPError as exc:
            raise DevTaskAPIError(
                status=0, message=f"网络错误：{exc}"
            ) from exc

        if resp.status_code >= 400:
            raise DevTaskAPIError(status=resp.status_code, message=resp.text)
        return _unwrap(resp.json())

    # ------------------------------------------------------------------ list

    async def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        task_type: Optional[str] = None,
        for_agent: Optional[bool] = None,
        include_deleted: bool = False,
        page: int = 1,
        per_page: int = 10,
    ) -> dict:
        per_page = min(per_page, MAX_PER_PAGE)
        params: dict = {
            "page": page,
            "per_page": per_page,
            "include_deleted": str(include_deleted).lower(),
        }
        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority
        if task_type:
            params["type"] = task_type
        if for_agent is not None:
            params["for_agent"] = str(for_agent).lower()

        return await self._request("GET", "/dev-tasks", params=params)

    # ------------------------------------------------------------------- get

    async def get_task(self, task_id: str) -> dict:
        return await self._request("GET", f"/dev-tasks/{task_id}")

    async def get_task_by_slug(self, slug: str) -> dict:
        return await self._request("GET", f"/dev-tasks/by-slug/{slug}")

    # ----------------------------------------------------------------- create

    async def create_task(self, body: dict) -> dict:
        return await self._request("POST", "/dev-tasks", json=body)

    # ----------------------------------------------------------------- update

    async def update_task(self, task_id: str, body: dict) -> dict:
        return await self._request("PATCH", f"/dev-tasks/{task_id}", json=body)

    # --------------------------------------------------------------- frontier

    async def find_frontier(self, limit: int = 10) -> list:
        """Return agent-claimable tasks (for_agent=true + backlog + unblocked)."""
        data = await self._request("GET", "/dev-tasks/frontier", params={"limit": limit})
        if isinstance(data, list):
            return data
        # Backend may wrap as { "data": [...] }; handle both shapes.
        if isinstance(data, dict) and "data" in data:
            inner = data["data"]
            return inner if isinstance(inner, list) else []
        return []

    # --------------------------------------------------------------- children

    async def find_children(self, parent_slug: str) -> list:
        """Return all tasks whose blocked_by contains parent_slug.

        Paginates through list_dev_tasks(for_agent=true) and filters
        client-side. Returns the full task objects so callers don't need
        a second get_dev_task_by_slug round-trip.
        """
        children: list = []
        page = 1
        while True:
            data = await self.list_tasks(for_agent=True, page=page, per_page=MAX_PER_PAGE)
            tasks = data.get("tasks", []) if isinstance(data, dict) else []
            for task in tasks:
                blocked_by = task.get("blocked_by", [])
                if isinstance(blocked_by, list) and parent_slug in blocked_by:
                    children.append(task)
            pagination = data.get("pagination", {}) if isinstance(data, dict) else {}
            if not pagination.get("has_next", False):
                break
            page += 1
        return children
