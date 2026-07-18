---
name: devtask-verify
description: '对照实际代码和运行时行为验证 dev-task 的验收条件。当用户说"verify task-N"、"check task-42"、"does task-7 pass?"、"验收 task-N"、"task 验收通过了吗"、"这个 spec 完了吗"，或询问某任务的验收条件是否满足时使用。对 parent task（kind=spec）会自动递归验证所有子任务。与 /devtask-doit（执行任务）和 /devtask-plan（创建任务）配套。对于没有 task slug 的通用代码变更验证，请用内置的 /verify。'
argument-hint: [task slug to verify, e.g. task-N]
disable-model-invocation: true
---

# devtask-verify

**关键词：verify。** 给定 task slug，拉取规格，逐条检查验收条件是否成立。只读，不修改代码。

Parent spec → 递归检查所有子任务。

## 流程

### 1. 拉取任务

`devtask_get_task(slug, with_parent=True)`。

kind=spec → `devtask_list_children` 获取全部子任务（权威来源，不从 AC 文本解析 slug），后续递归验证。
kind=subtask → 逐条验证。

### 2. 检查验收条件

把 `acceptance_criteria` 拆为单条。空则告知用户无可验证内容。

分类验证方式：

- **代码检查** — Read / grep 确认模式存在
- **运行时** — 发请求/执行命令，断言输出
- **子任务完成**（parent 特有）— 子任务各自 AC 全部 ✅ 则本条 ✅

### 3. 读上下文

按 `context_pointers` 读相关源码。不靠记忆。

### 4. 逐条验证

每条记录 ✅/❌/❉ 并附证据（file:line、命令输出、diff 片段）。歧义 → ❉ 不猜。

Parent：子任务全部 ✅ → 本条 ✅；任一 ❌ → ❌；有 ❉ → ❉。

### 5. 报告

```
## 验证：<slug> — <title>

板上状态：<status>
条件：共 N 条，P 通过，F 失败，U 不明确

| # | 条件 | 结论 | 证据 |
|---|------|------|------|
| 1 | ... | ✅/❌/❉ | file:line |
```

Parent 额外加：

```
### 子任务概览
| slug | title | 结论 |
|------|-------|------|
| task-N1 | ... | ✅ |
```

全通过但状态不是已完成调用tool修改任务状态。
