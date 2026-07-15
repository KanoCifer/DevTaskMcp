---
name: devtask-doit
description: '端到端执行一个可执行的（for_agent=true）dev-task。当用户说"做 task-N"、"执行任务"、"work on the next task"、"do task-42"，或给出一个 slug 来执行时使用。无参数时领取最前排的 frontier 任务。遇到 parent task 时拒绝执行并引导到子任务。'
argument-hint: [Which Task do you want to execute?<task-N>]
---

# devtask-doit

**关键词：execute。** 每次运行把一个可执行任务从`当前状态`推进到`已完成`——读规格、看上下文、实现、逐条验证验收条件、交付。一次运行要么完成任务，要么暴露一个具体 blocker（然后停下来）。

## 步骤

### 步骤 1：拿到任务

有 slug → `get_dev_task_by_slug(slug, with_parent=True)` —— 若为子任务可在同一次响应里拿到 parent spec 的 context_pointers/detail，省去后续二次查询。
没 slug → `get_frontier_tasks(limit=1)`，取第一个。返回空则告知用户"frontier 为空，没有可执行的任务"并结束。

拿到任务后判断：

- **`blocked_by` 非空** → 存在同层前置依赖。检查每个 blocker 状态：未完成则建议先执行 blocker，已完成则正常继续。
- **`blocked_by` 为空** → 正常继续。

### 步骤 2：读上下文

按 `context_pointers` 读代码 / 文档。**不靠记忆，靠读文件**。

### 步骤 3：执行

按 spec 的 `constraints` 红线内实现功能，改动紧贴 spec，不顺手重构

### 步骤 4：验证 + 更新状态

**逐条验证 acceptance_criteria**

先全部验证再修，修完再跑一遍，直到全部通过。

所有条件通过后，用 `update_dev_task` 把状态推进到 `已完成`。

如果当前是子任务，用 `list_children(parent_slug)` 检查同组兄弟：全部完成 → 自动把 parent 也标 `已完成`；否则在交付中列出剩余。

### 步骤 5：交付

输出给用户：

1. **当前任务**：slug + 状态
2. **后续动作**：
   - 有未完成的兄弟子任务 → 建议下一个执行 slug
   - parent 已全部完成 → "spec 已完成"
   - 有任务被当前任务阻塞 → 列出下一个可执行的 task
