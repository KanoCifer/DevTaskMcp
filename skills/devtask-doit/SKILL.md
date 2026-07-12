---
name: devtask-doit
description: Execute a dev-task end-to-end. Use when the user says "做 task-N", "执行任务", "work on the next task", "do task-42", or gives a slug to execute. With no argument, claims the top frontier task.
---

# devtask-doit

**Leading word: execute.** Every run takes a task spec from "ready" to "done" — reads the spec, examines the pointed code, implements, checks against acceptance criteria, updates status. A run either completes the task or surfaces a specific blocker (and stops).

Two modes:
- **Slug given** (`/devtask-doit task-42`) → execute that exact task.
- **No slug** (`/devtask-doit`) → claim the top frontier task (Pocock's frontier: `for_agent=true`, status=`待排期`, no open blockers, first by `sort_order`).

## 步骤

### 步骤 1：拿到任务

有 slug → `get_dev_task_by_slug(slug)`。
没 slug → `get_frontier_tasks(limit=1)`，取第一个。返回空则告知用户"frontier 为空，没有可执行的任务"并结束。

**Completion criterion:** 手上有任务的完整 spec（acceptance_criteria, constraints, context_pointers, blocked_by）。

### 步骤 2：读上下文

按 `context_pointers` 列出的路径读代码 / 文档。**不靠记忆，靠读文件**。context_pointers 没覆盖但明显相关的文件，补读。

**Completion criterion:** 已读到实现所需的所有相关源码。

### 步骤 3：执行

按 spec 的 `constraints` 红线内实现功能。每完成一个逻辑 milestone 就 git commit 一次（遵循 Conventional Commits）。

遵守：
- 不碰 `constraints` 列出的禁区
- 不改变 spec 之外的代码行为
- 改动紧贴 spec，不顺手重构

**Completion criterion:** 代码改动完，本地能编译 / 通过相关测试。

### 步骤 4：自检 acceptance_criteria

逐条对 `acceptance_criteria`。每条都过截图 / 命令输出 / diff 作证。不通过的条先修再继续。

**Completion criterion:** acceptance_criteria 全部通过；有命令输出或 diff 为证。

### 步骤 5：更新任务状态

调用 `update_dev_task` 把状态推进到 `已完成`。同时写一段执行摘要（用 `detail` 字段追加做了哪些关键决策）。

**Completion criterion:** 任务状态已变为 `已完成`。

### 步骤 6：交付

展示：slug + 最终状态 + 满足了哪些 acceptance_criteria + commit 列表。若有后续任务（被当前任务阻塞的），提示用户。

**Completion criterion:** 用户看到执行结果与 commit 列表。

## 失败处理

**遇到 blocker**（spec 有歧义、依赖没完成、技术死胡同）→ 停止执行，用 `update_dev_task` 把状态改为 `已搁置`，向用户描述具体 blocker，等用户决策后再决定是否继续。不要把半成品推成 `已完成`。

## 唯一真相源

任务 spec 在 MongoDB 里。执行过程中的中间决策追加到 `detail` 字段，不另开文档。
