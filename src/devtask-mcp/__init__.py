"""devtask-mcp: MCP server wrapping the kanocifer-chat dev-task API."""

"""FastMCP server exposing tools over stdio.

Tools
-----
- list_tasks      — GET  /dev-tasks   (filter + paginate, per_page cap 20)
- get_task — GET  /dev-tasks/:slug?with_parent=true 附带父 spec
- create_task     — POST /dev-tasks
- batch_create_tasks  — POST /dev-tasks × N（并发封装，上限 20）
- update_task     — PATCH /dev-tasks/:slug
- get_frontier_tasks  — GET  /dev-tasks/frontier
- list_children       — GET  /dev-tasks?kind=subtask (走客户端 parent_slug 过滤)
- batch_update_status — POST /dev-tasks/batch-status (多 slug 批量改状态)
- transition_plan     — 一步推 spec + 子任务到目标状态（封装 slug 拼合 + batch_status)
- complete_task       — 标记任务已完成（单 slug 或数组，底层复用 update_task）

Run with:  uv run python -m devtask-mcp.server
"""
