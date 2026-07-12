---
name: devtask-plan
description: Investigate a need and produce a well-specified dev-task. Use when the user says "我想做个...", "加个功能", "修个 bug", "记个任务", or drops an idea that should become a tracked task.
---

# devtask-plan

**Leading word: spec.** Every run turns a fuzzy need into a tight task spec — title, acceptance criteria, constraints, context pointers, scope, and dependencies — then persists it via the devtask MCP tools. The task it produces is `ready-for-agent` grade: an agent (or future you) can execute it without re-deriving the original intent.

## 步骤

### 步骤 1：理解需求边界

读用户描述的原始意图。**先做事实检索，再问决策**——能从代码里确认的事实不要问用户。

检索路径：
- 用户说 XXX 模块 → codegraph / grep 定位 `XXX` 相关文件
- 用户说"接 XXX 功能" → 找对应 endpoint / handler
- 用户说 bug → 搜索相关 error log / 代码路径

**Completion criterion:** 已确认的相关文件路径列表；已识别出用户的真实目标（不是字面措辞）。

### 步骤 2：补充 spec 字段（逐个提问）

**一次只问一个**，等用户回答后再问下一个。每个问题给出你的推荐答案。顺序：

1. **title** — 任务标题，一句话执行摘要。推荐动词开头："Add X", "Fix Y", "Refactor Z"。
2. **acceptance_criteria** — 完成时验证什么？推荐 2-4 条可检查的条件（"feature flag is on", "all 3 endpoints return 200", "no regression in X"）。
3. **constraints** — 红线：不能动哪些文件、不能用哪些技术、benchmark 不能回退。用户没提则问"有没有硬性约束？"
4. **context_pointers** — 相关代码路径 / 文档 / ADR。把步骤 1 检索到的路径写进来让用户确认补充。
5. **scope** — 推荐 `<层>-<技术>` 格式（`前端-React`, `后端-Go`, `AI-LangChain`）。**不是闭包枚举**，用户可自定义。
6. **for_agent** — 是否 agent 可执行？默认 `true`（spec 够完整）；spec 不完整或需人工判断则劝 `false`。
7. **blocked_by** — 依赖哪些任务？用户说 slug（`task-42`），空数组表示没有。

**Completion criterion:** 7 个字段各自有用户明确确认（或用户说"你的推荐就行"）。

### 步骤 3：调用 create_dev_task 落库

用 MCP tool `create_dev_task` 把确认后的字段落库。

**Completion criterion:** 返回体含 `slug`（如 `task-5`）。

### 步骤 4：交付

向用户展示：slug + title + acceptance_criteria 列表。提示后续动作（`/grill-me` 复审 / `/devtask-doit <slug>` 直接执行）。

**Completion criterion:** 用户看到完整 spec 快照。

## 唯一真相源

落库后的 spec 是唯一真相。后续修改走 `update_dev_task`，不重新 create。
