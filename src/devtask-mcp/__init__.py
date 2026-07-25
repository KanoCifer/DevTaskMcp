"""devtask-mcp: MCP server wrapping the kanocifer-chat dev-task API (v3).

FastMCP server exposing tools over stdio.  Every tool accepts the
``slug`` form (``task-N``) as the human-facing identifier.

The MCP surface is intentionally narrow.  Workflow orchestration lives
in skills (``devtask-doit``, ``devtask-plan``, ``devtask-simple``,
``devtask-review``, …) — agents should call those skills rather than
chaining MCP tools directly.

Tools
-----
- get_task — GET /dev-tasks/:slug?with_parent=true (rendered through
  the v3 view layer; default ``summary``)
- list_children — GET /dev-tasks?kind=subtask filtered by parent_slug
  (always returns summary records)
- create_task — POST /dev-tasks with inline parameters (for subtasks)
- create_task_document — POST /dev-tasks with the body compiled from a
  Task Document under ``/tmp`` (for spec / simple tasks)
- update_task — PATCH /dev-tasks/:slug (state + optional detail)
- complete_task — mark a single task or a list of tasks ``已完成``

Run with:  uv run python -m devtask_mcp.server
"""