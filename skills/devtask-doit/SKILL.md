---
name: devtask-doit
description: '端到端执行一个可执行的（for_agent=true）dev-task。当用户说"做 task-N"、"执行任务"、"work on the next task"、"do task-42"，或给出一个 slug 来执行时使用。无参数时领取最前排的 frontier 任务。遇到 parent task 时拒绝执行并引导到子任务。'
---

# devtask-doit

**关键词：execute。** 每次运行把一个可执行任务从当前状态推进到`已完成`——读规格、看上下文、实现、逐条验证验收条件、独立复核、更新状态。一次运行要么完成任务，要么暴露一个具体的 blocker（然后停下来）。

**只执行可执行 task（`for_agent=true`、`kind=subtask`）。** Parent spec（`for_agent=false`、`kind=spec`）是追踪节点，不接受直接执行——遇到时拒绝并列出其可执行子任务。

两种模式（详见步骤 1）：指定 slug 执行，或无 slug 领取 frontier。

## Preflight

在执行前先做连通性检查：调一次 `list_dev_tasks(per_page=1)`。如果返回错误或异常，告知用户 MCP server 不可用（检查 `.env` 中 `DEVTASK_API_KEY` 和 server 状态），中止执行。

## 步骤

### 步骤 1：拿到任务

有 slug → `get_dev_task_by_slug(slug)`。
没 slug → `get_frontier_tasks(limit=1)`，取第一个。返回空则告知用户"frontier 为空，没有可执行的任务"并结束。

拿到任务后做以下判断：

- **`kind == "spec"`（或 `for_agent: false`）** → 这是 parent spec（追踪节点）。**拒绝执行**。用 `list_children(slug)` 获取其子任务集（走后端 `parent_slug` 索引查询），列出子 task 的 slug + title，建议用户执行其中状态非 `已完成` 的子任务。本技能不执行 parent。
- **`kind == "subtask"` + `parent_slug` 非空** → 这是归属在某 spec 下的子任务。
- **`kind == "subtask"` + `parent_slug` 为空** → 这是独立的原子任务（未归属任何 spec）。
- **`blocked_by` 非空** → 存在同层前置依赖（执行顺序）。检查每个 blocker 任务状态：
  - blocker 不是 `已完成` → 先执行 blocker（告知用户并建议 slug）
  - blocker 是 `已完成` / 已 verify → 正常继续
- **`blocked_by` 为空** → 无前置依赖，正常继续。

`blocked_by` **不再指向 parent**（parent 关系由 `parent_slug` 承载），因此不需要在 blocked_by 里 hack 跳过 for_agent=false 的项。

**Completion criterion:** 手上有任务的完整 spec（含 kind / parent_slug）；MCP 连通性已确认；parent 场景已获取完整子任务列表。

### 步骤 2：读上下文

按 `context_pointers` 列出的路径读代码 / 文档。**不靠记忆，靠读文件**。context_pointers 没覆盖但明显相关的文件，补读。

如果当前任务是子任务（`parent_slug` 非空），还要 **读 parent spec 获取整体方案上下文**——通过 `get_dev_task_by_slug(parent_slug)` 获取 parent 的 `context_pointers` 和 `detail`，其中包含需求阶段的方案描述，是理解"为什么这么做"的关键。

**Completion criterion:** 已读到实现所需的所有相关源码；子任务已读 parent spec。

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

如果当前任务是子任务（`parent_slug` 非空），**检查同组兄弟任务是否全部 `已完成`**：

1. 通过 `get_dev_task_by_slug(parent_slug)` 确认 parent 存在
2. 通过 `list_children(parent_slug)` 获取全部子任务（后端 parent_slug 索引查询）
3. 如果所有子任务都已 `已完成` → 用 `update_dev_task(parent_slug, status="已完成")` 自动完成 parent
4. 如果还有未完成的子任务 → 在交付中列出，提示用户可以继续执行下一个

**Completion criterion:** 当前任务状态已变为 `已完成`；如果是子任务，已检查并更新 parent 状态（如适用）。

### 步骤 6：独立复核

执行完毕后，**切换到独立视角**对同一份 acceptance_criteria 做一次正式复核。这是状态已标 `已完成` 后的质量门——和步骤 4 自检互补：自检是你边做边查，复核时假装你是第一次看这份代码。

按 `devtask-verify` 技能的验证逻辑独立执行：

1. 重新读相关源码（不看步骤 4 的笔记，从零开始）
2. 对每条 acceptance_criteria 独立执行检查（代码读文件、运行时执行命令、diff 查 git）
3. 记录通过/失败/❉ 及具体证据

- 复核全部 ✅ → 进入步骤 7 交付。
- 复核出现 ❌ → 回到步骤 3/4 修复后重新复核。
- 复核出现 ❉ → 在交付中向用户明确披露，由用户决定是否接受。

**Completion criterion:** 独立复核结论已拿到；❌ 已修复或 ❉ 已向用户披露。

### 步骤 7：交付

展示：

1. **当前任务**：slug + 最终状态 + 步骤 4 自检表 + `/devtask-verify` 复核结论 + commit 列表
2. **上下级关系**（如适用，通过 `parent_slug` 判定）：
   - 如果是子任务 → 展示 parent slug（`kind: spec`）+ 所有子任务完成进度（`3/5 已完成`）
   - 如果 parent 已被自动完成 → 告知用户"parent task-N（spec）已自动标完成"
3. **后续动作**：
   - 有未完成的兄弟子任务 → 提示"下一个建议执行：`devtask:devtask-doit <sibling-slug>`"
   - parent 已全部完成 → 提示"整个 spec 已完成"
   - 有其他任务被当前任务阻塞（出现在它们的 `blocked_by` 中） → 列出下一个可执行的 task

**Completion criterion:** 用户看到自检表、复核结论、commit 列表，以及后续动作建议。

## 失败处理

**遇到 blocker**（spec 有歧义、依赖没完成、技术死胡同）→ 停止执行，用 `update_dev_task` 把状态改为 `已搁置`，向用户描述具体 blocker，等用户决策后再决定是否继续。不要把半成品推成 `已完成`。

**对 parent task 调用 doit** → 拒绝执行，这不是 bug 而是预期行为。Parent 是追踪节点，只能通过子任务完成来推进。列出可执行子任务引导用户。

## MCP 字段格式

通过 `update_dev_task` 写入的文本字段（`detail`、`description`、`acceptance_criteria` 等），**内容使用 Markdown 格式**。

格式规范：

- `detail`（执行摘要、决策记录）→ 支持 Markdown：标题、列表、代码块、链接
- `acceptance_criteria` 如需更新 → **有序或无序列表**，每条条件独立一行
- `constraints` → **列表**或表格
- `context_pointers` → 路径用代码块包裹，附简要说明

**例外：** 用户明确说"纯文本"时按用户要求。

