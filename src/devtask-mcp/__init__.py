"""devtask-mcp: MCP server wrapping the kanocifer-chat dev-task API."""

"""FastMCP server exposing tools over stdio.

Tools
-----
- get_task — GET  /dev-tasks/:slug?with_parent=true 附带父 spec
- create_task     — POST /dev-tasks
- batch_create_tasks  — POST /dev-tasks × N（并发封装，上限 20）
- update_task     — PATCH /dev-tasks/:slug
- list_children       — GET  /dev-tasks?kind=subtask (走客户端 parent_slug 过滤)
- complete_task       — 标记任务已完成（单 slug 或数组，底层复用 update_task）

Run with:  uv run python -m devtask-mcp.server
"""
