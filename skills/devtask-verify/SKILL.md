---
name: devtask-verify
description: 对照实际代码和运行时行为验证 dev-task 的验收条件。当用户说"verify task-N"、"check task-42"、"does task-7 pass?"、"验收 task-N"，或询问某任务的验收条件是否满足时使用。与 /devtask-doit（执行任务）和 /devtask-plan（创建任务）配套。对于没有 task slug 的通用代码变更验证，请用内置的 /verify。
---

# devtask-verify

**关键词：verify。** 给定一个 task slug，从任务板上拉取规格，然后逐条检查验收条件是否在实际代码和运行时行为中成立。产出每条条件的通过/失败报告并附证据（命令输出、diff、截图）。不修改代码——这是一次只读检查。

### 何时用、何时不用

- **使用场景：** 任务已标 `已完成`（或声称完成），需要确认验收条件确实成立。
- **使用场景：** 执行中途检查进度，在把状态翻到 `已完成` 之前。- **不使用：** 任务没有 `acceptance_criteria`——没有可验证的内容，直接告知用户。
- **不使用：** 没有绑定 task slug 的通用代码变更——用内置的 `/verify`。

## 步骤

### 步骤 1：拉取任务

调用 `get_dev_task_by_slug(slug)`。如果 slug 解析不到，列一下 frontier（`get_frontier_tasks`）并建议一个任务。

**Completion criterion:** 手上有任务的 `acceptance_criteria`、`constraints`、`context_pointers`、`status`、`detail`。

### 步骤 2：解析验收条件

把 `acceptance_criteria` 拆成单条。该字段是自由文本——常见格式有编号列表（`1. ... 2. ...`）、清单项（`- ...` / `* ...`）、或一行一条。如果字段为空或缺失，停下来告知用户没有可验证的内容。

对每条条件，分类其验证方式：
- **代码检查** — "函数 X 返回 Y"、"文件 Z 包含..." → 读文件、grep 匹配。
- **运行时 / 行为** — "server 返回 200"、"CLI 输出..." → 执行命令并捕获输出。
- **Diff / git** — "新增了对...的测试"、"删除了废弃的..." → 检查 `git diff` 或 `git log`。

**Completion criterion:** 条件列表，每条都标注了验证方式。

### 步骤 3：读上下文

按 `context_pointers` 读相关源码。不靠记忆——读实际文件。如果某条条件引用了 `context_pointers` 没覆盖的代码，也读一下。

**Completion criterion:** 所有条件涉及的代码都已读过。

### 步骤 4：逐条验证

对每条条件执行对应检查：

- **代码检查：** 读文件，确认模式存在（或不存在）。捕获相关行号作为证据。
- **运行时：** 执行命令（`uv run python -m devtask_mcp.server`、curl 等），捕获 stdout/stderr/退出码。MCP server 走 stdio——要做冒烟测试，通过 MCP client 调用其工具，或用 `uv run python -c "from devtask_mcp.server import mcp; print('ok')"` 确认模块能正常导入。
- **Diff / git：** `git diff <since>..HEAD` 或 `git log --oneline <since>..HEAD`。用任务的 `updated_at` 或 `detail` 里的记录来锚定时间范围。

记录通过/失败及具体证据（file:line、命令输出、diff 片段）。如果某条条件有歧义，标记为 **UNCLEAR** 而不是猜——让用户澄清。

**Completion criterion:** 每条条件都有 pass/fail/unclear 结论并附证据。

### 步骤 5：报告

按以下结构输出报告：

```
## 验证：<slug> — <title>

板上状态：<status>
条件：共 <N> 条，<P> 通过，<F> 失败，<U> 不明确

| # | 条件 | 结论 | 证据 |
|---|------|------|------|
| 1 | <文本> | ✅/❌/❉ | <file:line 或输出片段> |
...

### 总结
- **通过：** 所有条件都是 ✅。
- **失败：** 有条件是 ❌ — 列出还需要做什么。
- **需澄清：** 有条件是 ❉ — 列出需要用户确认的问题。
```

**不要修改任务状态。** 如果全部通过且任务还不是 `已完成`，建议用户跑 `/devtask-doit <slug>` 收尾（或手动更新状态）。如果有失败的，按失败条件建议下一步。

**Completion criterion:** 用户看到带证据的逐条结论表。

## 失败处理

- **任务找不到：** 告知用户，提供 frontier 列表。
- **无 acceptance_criteria：** 告知用户该任务没有可验证的内容；建议编辑任务补上验收条件。
- **运行时检查无法执行**（如没有 API key、server 起不来）：** 把该条标记为 ❉ 并记录原因；不要伪造通过。
- **条件是主观的**（"看起来不错"、"感觉快"）：标记为 ❉，请用户把它改写成可度量的表述。

## MCP 字段格式

本技能只读不写，不直接调用 `create_dev_task` / `update_dev_task`。但若验证过程中需要修正 acceptance_criteria（如将模糊条件改写为可度量表述），写入时**内容使用 Markdown 格式**：

- `acceptance_criteria` → **有序或无序列表**，每条条件独立一行，关键断言加粗
- `constraints` → **列表**或表格
- `context_pointers` → 路径用代码块包裹，附简要说明

**例外：** 用户明确说"纯文本"时按用户要求。

## 唯一真相源

任务规格在 MongoDB 里。本技能只读不写——验证是只读的。如果用户想根据验证结果更新任务，走 `/devtask-doit` 或手动调 `update_dev_task`。
