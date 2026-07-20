---
name: devtask-review
description: '端到端审查 dev-task：(1) 逐条验证验收条件 ✓/❌/❓ (2) 并行四视角代码质量审查(复用/简化/效率/海拔) (3) 正确性+安全审查 (4) 能修的改、不能修的 skip 并说明。当用户说"review task-N"、"verify task-N"、"check task-42"、"验收 task-N"、"审查任务"、"does task-7 pass"、"这个 spec 完了吗"，或询问某任务的验收条件是否满足时使用。对 parent task（kind=spec）会自动递归审查所有子任务。与 /devtask:devtask-doit（执行任务）和 /devtask:devtask-plan（创建任务）配套。涉及时尚未收敛的设计决策时，引导用户先走 /devtask:devtask-grill。'
argument-hint: [task slug to review, e.g. task-N]
disable-model-invocation: true
---

# devtask-review

**关键词：review / verify。** 把任务从"自称完成"变成"可被证成的完成"——验收条件表 + 四视角清理审查 + 正确性审查，可修的当场修，不能修的显式 skip。

只读验证 + 轻量清理修复；不做大范围重构。

## 流程

### 1. 拉取任务

`get_task(slug, with_parent=True)`。

kind=spec → `list_children` 获取全部子任务(权威来源，不从 AC 文本解析 slug)，后续递归审查。
kind=subtask → 直接进入逐条验证。

`blocked_by` 非空 → 检查 blocker 状态：未完成则建议先执行 blocker，**不继续往下审**。

### 2. 验收条件验证(只读)

把 `acceptance_criteria` 拆为单条。空则告知用户无可验证内容但仍继续后续视角。

分类验证方式：

- **代码检查** — Read / grep 确认模式存在
- **运行时** — 发请求 / 执行命令，断言输出
- **子任务完成**(parent 特有) — 子任务各自 AC 全部 ✅ 则本条 ✅

每条记录 ✅ / ❌ / ❓ 并附证据(file:line、命令输出、diff 片段)。歧义 → ❓ 不猜。

### 3. 四视角清理审查(并行)

从任务绑定的分支/PR 或上下文指针(context_pointers)里找到被改动的代码。**改动范围不明时跳过本节并在报告里注明**。

按 `/simplify` 的范式,沿四个视角各派一个审查视角并行跑(单消息多 Agent 并发)。每个视角返回 `file:line` + 一句话 `summary` + 代价(what is duplicated/wasted/harder to maintain) + 具体修法。

| 视角               | 抓什么                                                                                 |
| ------------------ | -------------------------------------------------------------------------------------- |
| **Reuse**          | 新代码重复了 codebase 已有能力——指出已有的 helper 可改调                               |
| **Simplification** | 冗余/可推导状态/复制粘贴变体/深层嵌套/留下死代码——指出等价更简形式                     |
| **Efficiency**     | 冗余计算/可并行的串行/热路径阻塞/闭包大包(吃光外层作用域 = 内存泄漏)——指出更便宜的写法 |
| **Altitude**       | 修复深度不够的特殊 case——偏好通用化底层机制而非叠特殊 case                             |

每个视角独立判断；每个 finding 必须带 `file:line` + 改法。**小改动合并为单 Agent**,避免为用而用。

### 4. 正确性 + 安全审查

单 Agent 扫:

- 边界条件 / 错误路径 / 资源泄漏
- 注入 / 鉴权 / 敏感信息泄露
- 并发 / 竞态

只报不修(正确性/安全修改须经用户确认)。

### 5. 应用清理修复

等四视角全部回来后：

1. **去重** — 多视角指向同一机制只改一次
2. **逐条真改** — 按 finding 的修法落地
3. **显式 skip** — 以下情况不修,记录 skip + 一句话 reason:
   - 修法会改变意图或 AC 已定义的行为
   - 越出本次改动范围的大范围重构
   - 误报(判断后)

正确性/安全类 finding **永远不自动修**,只在报告里给建议。

### 6. 状态修正

parent: 子任务 AC 全部 ✅ + 自身 AC 全部 ✅ → `devtask_complete_task` 翻到已完成。

### 7. 报告

```
## Review: <slug> — <title>

板上状态: <status> → <最终状态(若变动)>
验收条件: 共 N 条,P 通过,F 失败,U 不明确

| # | 条件 | 结论 | 证据 |
|---|------|------|------|
| 1 | ... | ✅/❌/❓ | file:line |

### 清理审查(四视角)
| 视角 | file:line | 修法 | 结论 |
|------|-----------|------|------|
| Reuse | ... | applied: ... | fixed |
| Simplification | ... | 会改行为 | skipped: <reason> |
| Efficiency | ... | applied: ... | fixed |
| Altitude | — | — | clean |

### 正确性 + 安全
- [severity] file:line — 建议(不自动修)

### 子任务概览(parent)
| slug | title | AC | 清理 | 正确性 |
|------|-------|----|------|--------|
| task-N1 | ... | ✅ | clean | — |
```

全 AC 通过 + 清理全 clean → 末尾一句话总结"可以被证成完成"；否则明确remaining work。

## Rules

- **正确性/安全永不自动改** — 单列表报告,由用户决策
- **改动范围不明时跳过清理节** — 不要凭记忆去猜 diff
- **显式 skip > 默默跳过** — 每个不修的 finding 必有 一句话 reason
- **Parent 递归** — 子任务全部 ✅ + 自身 AC 全部 ✅ 才翻 parent
