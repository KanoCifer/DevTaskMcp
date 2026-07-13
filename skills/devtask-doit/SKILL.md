---
name: devtask-doit
description: 端到端执行一个 dev-task。当用户说"做 task-N"、"执行任务"、"work on the next task"、"do task-42"，或给出一个 slug 来执行时使用。无参数时领取最前排的 frontier 任务。
---

# devtask-doit

**关键词：execute。** 每次运行把一个任务从"待执行"推进到"已完成"——读规格、看上下文、实现、逐条验证验收条件、更新状态。一次运行要么完成任务，要么暴露一个具体的 blocker（然后停下来）。

两种模式：
- **给定 slug**（`/devtask-doit task-42`）→ 执行指定任务。
- **无 slug**（`/devtask-doit`）→ 领取最前排的 frontier 任务（Pocock's frontier：`for_agent=true`、状态 `待排期`、无未解决的阻塞、按 `sort_order` 取第一个）。

## 步骤

### 步骤 1：拿到任务

有 slug → `get_dev_task_by_slug(slug)`。
没 slug → `get_frontier_tasks(limit=1)`，取第一个。返回空则告知用户"frontier 为空，没有可执行的任务"并结束。

**Completion criterion:** 手上有任务的完整 spec（acceptance_criteria、constraints、context_pointers、blocked_by）。

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

逐条对 `acceptance_criteria`，按以下表格结构记录证据——这和 `/devtask-verify` 的验证报告格式一致，便于后续正式复核时复用：

```
| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | <文本>     | ✅/❌/❉ | <文件:行号 / 命令输出 / diff 片段> |
```

每条都需要：
- 代码类条件 → 读文件确认，记录 `path:line`
- 运行时条件 → 执行命令（如 `uv run python -c "..."`、curl、grep），记录输出
- 不确定 / 无法验证 → 标记 ❉，记录原因

不通过的条先修再继续，直到全部 ✅ 或 ❉（❉ 条必须在步骤 7 向用户明确披露）。

**Completion criterion:** acceptance_criteria 全部有 ✅/❉ 结论；有具体证据；该修的已修完。

### 步骤 5：更新任务状态

调用 `update_dev_task` 把状态推进到 `已完成`。同时写一段执行摘要（用 `detail` 字段追加做了哪些关键决策）。

**Completion criterion:** 任务状态已变为 `已完成`。

### 步骤 6：正式复核（/devtask-verify）

执行完毕后，调用 `/devtask-verify <slug>` 对同一份 acceptance_criteria 做一次独立的正式复核。这是状态已标 `已完成` 后的质量门——和步骤 4 自检互补：自检是你边做边查，复核是换一个视角再过一遍。

- 复核全部 ✅ → 进入步骤 7 交付。
- 复核出现 ❌ → 回到步骤 3/4 修复后重新复核。
- 复核出现 ❉ → 在交付中向用户明确披露，由用户决定是否接受。

**Completion criterion:** 正式复核结论已拿到；❌ 已修复或 ❉ 已向用户披露。

### 步骤 7：交付

展示：slug + 最终状态 + 步骤 4 自检表 + `/devtask-verify` 复核结论 + commit 列表。若有后续任务（被当前任务阻塞的），提示用户。

**Completion criterion:** 用户看到自检表、复核结论与 commit 列表。

## 失败处理

**遇到 blocker**（spec 有歧义、依赖没完成、技术死胡同）→ 停止执行，用 `update_dev_task` 把状态改为 `已搁置`，向用户描述具体 blocker，等用户决策后再决定是否继续。不要把半成品推成 `已完成`。

## MCP 字段格式

通过 `update_dev_task` 写入的文本字段（`detail`、`description`、`acceptance_criteria` 等），**内容使用 Markdown 格式**。

格式规范：
- `detail`（执行摘要、决策记录）→ 支持 Markdown：标题、列表、代码块、链接
- `acceptance_criteria` 如需更新 → **有序或无序列表**，每条条件独立一行
- `constraints` → **列表**或表格
- `context_pointers` → 路径用代码块包裹，附简要说明

**例外：** 用户明确说"纯文本"时按用户要求。

## 唯一真相源

任务 spec 在 MongoDB 里。执行过程中的中间决策追加到 `detail` 字段，不另开文档。
