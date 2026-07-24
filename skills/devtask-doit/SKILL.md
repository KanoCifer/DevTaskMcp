---
name: devtask-doit
description: '端到端执行一个可执行的（for_agent=true）dev-task。当用户说"做 task-N"、"执行任务"、"work on the next task"、"do task-42"，或给出一个 slug 来执行时使用。遇到 parent task 时拒绝执行并引导到子任务。'
argument-hint: [Which Task do you want to execute?<task-N>]
disable-model-invocation: true
---

# devtask-doit

**关键词：execute。** 每次运行把一个可执行任务从当前状态推进到已完成。

## 流程

### 1. 拿到任务

`get_task(slug, with_parent=True)`。

`blocked_by` 非空 → 检查 blocker 状态：未完成则建议先执行 blocker。

### 2. 读上下文

按 `context_pointers` 读代码/文档。不靠记忆。

### 3. 执行

按 spec 的 constraints 实现。改动紧贴 spec，不顺手重构。

### 4. 验证 + 更新

逐条检查 acceptance_criteria。先全部检查再修，修完重跑直到全过。

全部通过 → `complete_task(slug)` 标已完成（专用快捷工具，比 update_task 更明确）。

子任务：`list_children(parent_slug)` 检查兄弟。全部完成 → parent 也标已完成（同样走 `complete_task`，支持数组 slug 一次完成多个，可把 parent + 剩余兄弟一并传入）。

### 5. 交付

1. 当前任务：slug + 状态
2. 后续：未完成兄弟 → 建议下一个 slug；parent 完成 → "spec 已完成"

## Rules

- **Source of truth** — 任务状态推进统一走 `complete_task`（单 slug 或数组）；其他字段修改才用 `update_task`
