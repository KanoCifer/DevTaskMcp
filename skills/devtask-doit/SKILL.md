---
name: devtask-doit
description: '端到端执行一个可执行的（for_agent=true）dev-task。当用户说"做 task-N"、"执行任务"、"work on the next task"、"do task-42"，或给出一个 slug 来执行时使用。遇到 parent task（kind=spec）时会引导到子任务而不是执行 spec 本身。'
argument-hint: [Which Task do you want to execute?<task-N>]
disable-model-invocation: true
---

# devtask-doit

**关键词：execute。** 每次运行把一个可执行任务从当前状态推进到已完成。

v3：只读 `get_task(slug, view="execute")`，不要自己解析 Markdown，
也不要读取 `context_pointers` / `constraints` / `acceptance_criteria`
这些独立字段——v3 已把它们合并进 `detail`，MCP 服务端会按视图返回。

## 流程

### 1. 拿到任务

```text
get_task(slug, view="execute")
```

如果 `kind == "spec"`，先 `list_children(parent_slug=slug)` 拿子任务列表，
挑下一个 subtask 执行，**不要**执行 spec 自身。

`blocked_by` 非空 → 检查 blocker 状态：未完成则建议先执行 blocker。

### 2. 读上下文

按 `sections.context_pointers`（已经在视图里）读代码/文档。不靠记忆。

### 3. 执行

按 `sections.plan`（在 execute 视图里）实现。改动紧贴 spec，不顺手重构。
`sections.constraints` 是硬性边界，违反之前先确认。

### 4. 验证 + 更新

逐条检查 `sections.acceptance_criteria`（list，每条 `{text, checked}`）。
先全部检查再修，修完重跑直到全过。

需要把决策固化进 detail 时使用 `update_task(slug, detail=...)` 修改 Decisions 章节。
普通执行日志**不要**写回 task。

全部通过 → `complete_task(slug)` 标已完成（专用快捷工具）。

子任务：`list_children(parent_slug)` 检查兄弟。全部完成 → parent 也标已完成
（同样走 `complete_task`，支持数组 slug 一次完成多个，可把 parent + 剩余兄弟
一并传入）。

### 5. 交付

1. 当前任务：slug + 状态
2. 后续：未完成兄弟 → 建议下一个 slug；parent 完成 → "spec 已完成"

## Rules

- **Source of truth** — 任务状态推进统一走 `complete_task`（单 slug 或数组）；
  其他字段修改走 `update_task(slug, detail=...)`（替换整份 detail）
- **不要再解析 detail 字符串** — MCP 视图已经把 `goal` / `plan` / AC / constraints
  / context_pointers 切好了
- **不要把 AC 文本塞进对话** — `get_task(slug, view="execute")` 已经在响应里
  返回结构化 AC 列表
