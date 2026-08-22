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

按 `../references/task-contract.md` 读取 Task Document 和 MCP 契约。
如果 `kind == "spec"`，先 `list_children(parent_slug=slug)` 拿子任务列表，挑下一个 subtask 执行；不要执行 spec 自身。
### 2. 读上下文

按 `## Context Pointers` 章节里的 `path:line` 读代码/文档。不靠记忆。

### 3. 执行

按 `## Plan` 章节实现。改动紧贴 spec，不顺手重构。
`## Constraints` 是硬性边界，违反之前先确认。

### 4. 验证 + 更新

逐条检查 `## Acceptance Criteria` 的验收项；先检查再修，修完重跑直到全过。

需要固化决策时用 `update_task(slug, detail=...)`；普通执行日志不要写回 task。

当前任务全部通过 → `update_task(slug, status="已完成")`。
spec 的全部子任务完成后，可用 `update_task(slugs=[...])` 批量标记；该接口仅更新状态为 `已完成`。
### 5. 交付

1. 当前任务：slug + 状态
2. 后续：未完成兄弟 → 建议下一个 slug；parent 完成 → "spec 已完成"

## Rules

- **Source of truth** — 状态用 `update_task`；正文用 `update_task(slug, detail=...)`
- **不扩大范围** — 紧贴 spec 和 AC，不顺手重构
- **记录决策** — 关键变更写入 `Decisions`，不要写执行日志
