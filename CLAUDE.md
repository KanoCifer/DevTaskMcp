# CLAUDE.md

## Project

DevTaskMcp is an MCP server (Python, FastMCP) that wraps the kanocifer.chat dev-task API as Task Document v3 tools for AI agents. It implements a "frontier" pattern — agents claim and execute the next ready task from a kanban board. The v3 protocol collapses all long-form text into a single `detail` Markdown body; structured fields are passed as inline tool parameters.

## Commands

```bash
# Run the MCP server (streamable-http, binds 0.0.0.0:8003, endpoint /mcp/)
uv run python -m devtask_mcp.server

# Docker deploy
docker compose up --build

# Run the test suite
uv run --group dev python -m pytest tests -q
```

Server env: `MCP_HOST`/`MCP_PORT` (default `0.0.0.0:8003`), `MCP_AUTH_TOKEN` (static Bearer token; empty disables app-level auth). The container binds loopback only — a reverse proxy in front terminates TLS.

## Environment

`.env` (gitignored, copy from `.env.example`) provides:

- `DEVTASK_API_KEY` — **required**, Bearer <REDACTED> for the API. `DevTaskClient` raises `RuntimeError` at construction if empty.
- `DEVTASK_API_BASE` — defaults to `https://api.kanocifer.chat/api/v3`.

## Code style

- `from __future__ import annotations` in every source file (PEP 604 union syntax).
- Google-style docstrings with `Args:` sections.
- Logger name: `"devtask-mcp"`.

## Critical: Chinese literal enums

Task model enum values are **Chinese strings, not English constants**. Validating at the Python boundary prevents bad values from wasting API round-trips:

| Field          | Canonical values                                                        |
| -------------- | ----------------------------------------------------------------------- |
| `TaskType`     | `"问题"`, `"功能需求"`, `"优化"`, `"技术债"`                            |
| `TaskPriority` | `"P0 紧急"`, `"P1 高"`, `"P2 中"`, `"P3 低"`                            |
| `TaskStatus`   | `"待评估"`, `"待排期"`, `"进行中"`, `"已搁置"`, `"已完成"`              |
| `TaskScope`    | free-form `str`, recommended format `"<层>-<技术>"` e.g. `"前端-React"` |

Always use the Chinese literals when creating or filtering tasks — never invent English keys.

## Task references

Use the slug (`task-N`) as the human-facing ID in conversation, UI, and MCP contexts. ObjectIds are internal.

## Skills location

Skills live in the repo-root `skills/` directory (`skills/devtask/`, `skills/doit/`), **not** `.claude/skills/`. The README's structure diagram is stale on this point. Symlink to `~/.claude/skills/` for global use.

## Architectural notes

- The Go backend wraps responses in `{code, message, data}`. `client._unwrap` strips this envelope at the boundary — MCP tools never see wrapper fields.
- Non-2xx or `code != 0` raises `DevTaskAPIError` and propagates verbatim to the agent (by design).
- `per_page` is capped at 20 regardless of caller input.
- HTTP timeout: 15.0 s.
- A single long-lived `DevTaskClient` lives at module level — safe because the client holds no per-session state and one server process serves all streamable-http sessions.

## v3 architecture (Task Document)

- All long text lives in `detail` (a Task Document), structured as fixed Markdown sections (`Goal`, `Plan`, `Acceptance Criteria`, `Constraints`, `Context Pointers`, `Decisions`, `Out of Scope`). Structured fields (title, type, priority, scope, kind, parent_slug, …) are inline tool parameters.
- `create_task` / `update_task` are the core write tools. `create_task` takes only inline params; slug is always server-assigned — use `parent_slug` to link a subtask to its spec.
- `get_task(slug, view=...)` supports two views: `summary` (structured fields only) and `full` (raw task incl. detail). The default is `summary` so the agent never accidentally pulls the full body into context.
- `list_children` always returns summary records. Children are fetched with `full` only when needed.
- `update_task` covers state + detail edits. For full Task Document replacement pass `detail=`; for status changes pass `status=`.

See `docs/task-document-v1.md` for the full Task Document spec.
