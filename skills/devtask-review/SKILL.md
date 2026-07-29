---
name: devtask-review
description: "Review and verify a completed devtask against its acceptance criteria. Use when the user asks to review a task, verify completion, check acceptance criteria, run a code review on a finished task, or says 'review task-N'."
argument-hint: [task slug to review, e.g. task-N]
---

# devtask-review

**关键词：review / verify。** 把任务从"自称完成"变成"可被证成的完成"——验收条件表 + 四视角清理审查 + 正确性审查，可修的当场修，不能修的显式 skip。

只读验证 + 轻量清理修复；不做大范围重构。

v3：只读 `get_task(slug, view="review")`，**不要**请求 `full` 视图。`review` 视图
已经返回结构化的 `sections.acceptance_criteria`（list）、`sections.constraints`、
`sections.context_pointers`，没有 Goal/Plan 等长文本。

## 流程

### 1. 拉取任务

```text
get_task(slug, view="review")
```

`kind == "spec"` → `list_children(parent_slug=slug)` 获取 summary 列表。
不要一次性拉所有 child 的 `review` 视图；只对需要审的 child 单独 `get_task(child, view="review")`。

`blocked_by` 非空 → 检查 blocker 状态：未完成则建议先执行 blocker，**不继续往下审**。

### 2. 验收条件验证（只读）

`sections.acceptance_criteria` 已经是 `[{text, checked}, ...]` 列表。空则告知用户无可验证内容但仍继续后续视角。

分类验证方式：

- **代码检查** — Read / grep 确认模式存在
- **运行时** — 发请求 / 执行命令，断言输出
- **子任务完成**（parent 特有）— 子任务各自 AC 全部 ✅ 则本条 ✅

每条记录 ✅ / ❌ / ❓ 并附证据（file:line、命令输出、diff 片段）。歧义 → ❓ 不猜。

### 3. 四视角清理审查（并行）

按 `sections.context_pointers` 找到被改动的代码。**改动范围不明时跳过本节并在报告里注明**。

沿四个视角各派一个审查视角并行跑（单消息多 Agent 并发）。每个视角返回 `file:line` + 一句话 `summary` + 代价 + 具体修法。

详见 `references/review-perspectives.md`。每个视角独立判断；每个 finding 必须带 `file:line` + 改法。**小改动合并为单 Agent**，避免为用而用。

### 4. 正确性 + 安全审查

单 Agent 扫：

- 边界条件 / 错误路径 / 资源泄漏
- 注入 / 鉴权 / 敏感信息泄露
- 并发 / 竞态

只报不修（正确性/安全修改须经用户确认）。

### 5. 应用清理修复

等四视角全部回来后：

1. **去重** — 多视角指向同一机制只改一次
2. **逐条真改** — 按 finding 的修法落地
3. **显式 skip** — 以下情况不修，记录 skip + 一句话 reason：
   - 修法会改变意图或 AC 已定义的行为
   - 越出本次改动范围的大范围重构
   - 误报（判断后）

正确性/安全类 finding **永远不自动修**，只在报告里给建议。

需要把决策固化回 spec 时用 `update_task(slug, detail=...)` 更新 Decisions 章节。

### 6. 状态修正

parent：子任务 AC 全部 ✅ + 自身 AC 全部 ✅ → `update_task(slugs=[...])` 批量翻到已完成。

### 7. 报告

按 `references/report-template.md` 格式输出。全 AC 通过 + 清理全 clean → 末尾一句话总结"可以被证成完成"；否则明确 remaining work。

## Rules

- **正确性/安全永不自动改** — 单列表报告，由用户决策
- **改动范围不明时跳过清理节** — 不要凭记忆去猜 diff
- **显式 skip > 默默跳过** — 每个不修的 finding 必有一句话 reason
- **Parent 递归** — 子任务全部 ✅ + 自身 AC 全部 ✅ 才翻 parent
- **永远用 review 视图** — 不要请求 full 视图拉长文本
