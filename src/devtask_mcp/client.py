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


class DevTaskAPIError(RuntimeError):
    """Raised when the backend returns a non-2xx response or envelope code != 0."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


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
            raise RuntimeError(
                "DEVTASK_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base, headers=_headers(), timeout=15.0
        )

    async def aclose(self) -> None:
        await self._client.aclose()

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

        resp = await self._client.get("/dev-tasks", params=params)
        if resp.status_code != 200:
            raise DevTaskAPIError(status=resp.status_code, message=resp.text)
        return _unwrap(resp.json())

    # ------------------------------------------------------------------- get

    async def get_task(self, task_id: str) -> dict:
        resp = await self._client.get(f"/dev-tasks/{task_id}")
        if resp.status_code != 200:
            raise DevTaskAPIError(status=resp.status_code, message=resp.text)
        return _unwrap(resp.json())

    async def get_task_by_slug(self, slug: str) -> dict:
        resp = await self._client.get(f"/dev-tasks/by-slug/{slug}")
        if resp.status_code != 200:
            raise DevTaskAPIError(status=resp.status_code, message=resp.text)
        return _unwrap(resp.json())

    # ----------------------------------------------------------------- create

    async def create_task(self, body: dict) -> dict:
        resp = await self._client.post("/dev-tasks", json=body)
        if resp.status_code != 200:
            raise DevTaskAPIError(status=resp.status_code, message=resp.text)
        return _unwrap(resp.json())

    # ----------------------------------------------------------------- update

    async def update_task(self, task_id: str, body: dict) -> dict:
        resp = await self._client.patch(f"/dev-tasks/{task_id}", json=body)
        if resp.status_code != 200:
            raise DevTaskAPIError(status=resp.status_code, message=resp.text)
        return _unwrap(resp.json())

    # --------------------------------------------------------------- frontier

    async def find_frontier(self, limit: int = 10) -> list:
        """Return agent-claimable tasks (for_agent=true + backlog + unblocked)."""
        params = {"limit": limit}
        resp = await self._client.get("/dev-tasks/frontier", params=params)
        if resp.status_code != 200:
            raise DevTaskAPIError(status=resp.status_code, message=resp.text)
        data = _unwrap(resp.json())
        if isinstance(data, list):
            return data
        # Backend may wrap as { "data": [...] }; handle both shapes.
        if isinstance(data, dict) and "data" in data:
            inner = data["data"]
            return inner if isinstance(inner, list) else []
        return []
