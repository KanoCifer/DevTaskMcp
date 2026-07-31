---
name: devtask-doit
description: "End-to-end execute a devtask from the kanban board. Use when the user asks to execute a task, work on a task, do task-N, start the next task, or says 'let's do this task'."
argument-hint: [Which Task do you want to execute?<task-N>]
---

# devtask-doit

## 流程

### 1. 拿到任务

```text
get_task(slug, view="full")
```

从返回的 `detail` 里解析 Task Document 章节：`## Goal` / `## Plan` /
`## Acceptance Criteria`（`- [ ]` 检查项）/ `## Constraints` /
`## Context Pointers`。视图只有 `summary`（结构化字段）和 `full`
（含完整 detail）两种。

如果 `kind == "spec"`，先 `list_children(parent_slug=slug)` 拿子任务列表，
挑下一个 subtask 执行，**不要**执行 spec 自身。

`blocked_by` 非空 → 检查 blocker 状态：未完成则建议先执行 blocker。

### 2. 读上下文

按 `## Context Pointers` 章节里的 `path:line` 读代码/文档。不靠记忆。

### 3. 执行

按 `## Plan` 章节实现。改动紧贴 spec，不顺手重构。
`## Constraints` 是硬性边界，违反之前先确认。

### 4. 验证 + 更新

逐条检查 `## Acceptance Criteria` 的 `- [ ]` 检查项（`- [x]` 已勾选）。
先全部检查再修，修完重跑直到全过。

需要把决策固化进 detail 时使用 `update_task(slug, detail=...)` 修改 Decisions 章节。
普通执行日志**不要**写回 task。

全部通过 → `update_task(slug, status="已完成")` 标已完成。

子任务：`list_children(parent_slug)` 检查兄弟。全部完成 → parent 也标已完成
（走 `update_task(slugs=[...])` 批量标记，可把 parent + 剩余兄弟一并传入）。

### 5. 交付

1. 当前任务：slug + 状态
2. 后续：未完成兄弟 → 建议下一个 slug；parent 完成 → "spec 已完成"

## Rules

- **Source of truth** — 任务状态推进走 `update_task(slug, status=...)`；批量走 `update_task(slugs=[...])`；其他字段修改走 `update_task(slug, detail=...)`
