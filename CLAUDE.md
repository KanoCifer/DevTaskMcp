# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DevTaskMcp is an MCP server (Python, FastMCP) that wraps the kanocifer.chat dev-task API as six tools for AI agents. It implements a "frontier" pattern — agents claim and execute the next ready task from a kanban board. Two skills (`devtask-plan`, `devtask-doit`) round out the package.

## Commands

```bash
# Run the MCP server (stdio, one server per agent session)
uv run python -m devtask_mcp.server
```

There is no test suite, linter, formatter, or CI configured yet.

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

Skills live in the repo-root `skills/` directory (`skills/devtask-plan/`, `skills/doit/`), **not** `.claude/skills/`. The README's structure diagram is stale on this point. Symlink to `~/.claude/skills/` for global use.

## Architectural notes

- The Go backend wraps responses in `{code, message, data}`. `client._unwrap` strips this envelope at the boundary — MCP tools never see wrapper fields.
- Non-2xx or `code != 0` raises `DevTaskAPIError` and propagates verbatim to the agent (by design).
- `per_page` is capped at 20 regardless of caller input.
- HTTP timeout: 15.0 s.
- A single long-lived `DevTaskClient` lives at module level — safe because FastMCP stdio runs one server per agent session.
- Spec is the single source of truth: once created, tasks are mutated via `devtask_update_task`; execution appends decisions to the `detail` field.
