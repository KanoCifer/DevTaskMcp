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

拿到任务后做以下判断：

- **`kind == "spec"`** → parent spec（追踪节点）。**拒绝执行**。用 `list_children(slug)` 列出子 task 的 slug + title，建议用户执行非 `已完成` 的子任务。
- **`blocked_by` 非空** → 存在同层前置依赖。检查每个 blocker 状态：未完成则建议先执行 blocker，已完成则正常继续。
- **`blocked_by` 为空** → 正常继续。

### 步骤 2：读上下文

按 `context_pointers` 读代码 / 文档。**不靠记忆，靠读文件**。没覆盖但明显相关的文件，补读。

如果当前任务是子任务（`parent_slug` 非空），还要读 **parent spec** 获取整体方案上下文。

### 步骤 3：执行

按 spec 的 `constraints` 红线内实现功能。每完成一个逻辑 milestone 就 git commit 一次（遵循 Conventional Commits）。

- 不碰 `constraints` 列出的禁区
- 不改变 spec 之外的代码行为
- 改动紧贴 spec，不顺手重构

### 步骤 4：验证 + 更新状态

**逐条验证 acceptance_criteria**，记录证据：

```
| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | <文本>     | ✅/❌/❉ | <文件:行号 / 命令输出 / diff 片段> |
```

- 代码类 → 读文件确认，记录 `path:line`
- 运行时 → 执行命令，记录输出
- 不确定 → 标记 ❉，记录原因

**先全部验证再修，修完再跑一遍。** 直到全部 ✅ 或 ❉。

所有条件通过后，用 `update_dev_task` 把状态推进到 `已完成`，并在 `detail` 字段追加执行摘要（做了哪些关键决策、改了哪些文件）。

如果当前是子任务（`parent_slug` 非空），用 `list_children(parent_slug)` 检查同组兄弟：全部完成 → 自动把 parent 也标 `已完成`；否则在交付中列出剩余。

### 步骤 5：交付

输出给用户：

1. **当前任务**：slug + 状态 + 验证表 + commit 列表
2. **后续动作**：
   - 有未完成的兄弟子任务 → 建议下一个执行 slug
   - parent 已全部完成 → "整个 spec 已完成"
   - 有任务被当前任务阻塞 → 列出下一个可执行的 task

## 失败处理

**遇到 blocker**（spec 有歧义、依赖没完成、技术死胡同）→ 停止，用 `update_dev_task` 把状态改为 `已搁置`，向用户描述具体 blocker。不要把半成品推成 `已完成`。

**对 parent task 调用 doit** → 拒绝执行。列出可执行子任务引导用户。
