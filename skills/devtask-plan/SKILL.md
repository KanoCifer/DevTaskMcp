---
name: devtask-plan
description: '调研需求形成 spec，再拆解为多个可执行的具体 task（输出 = spec + 子任务树）。当用户抛出一个预计改动 >5 文件、或需要跨层/多步骤的需求/功能/想法时使用——先明确做什么、怎么做，再落库为 spec + 子任务树。典型触发："做个 X 功能"、"规划一下这个需求"、"我有个想法想拆成几个 task"。不适合：简单的小修/小加/单文件改动（用 devtask-simple）；价值/判断类（用 devtask-simple 的 Evaluation 模式）。'
argument-hint:
  [Requirement / feature / idea to be specified and broken into tasks]
disable-model-invocation: true
---

# devtask-plan

把模糊需求变成 **spec（做什么 + 方案）** 和一组可执行的具体 task。

**核心：** spec → tasks。先达成共享理解，再拆为独立可执行的子任务。

## 流程

### 1. 探索

- 模块名 → codegraph_explore / Read / grep
- "接 XXX 功能" → 找对应 endpoint / handler / service
- 涉及框架能力时优先查官方方案

**退出条件：** 知道改哪些文件、怎么改、影响范围
**Gate：** 探索完发现 ≤5 文件且单层次 → 建议降级 `/devtask-simple`，终止

### 2. 方案 Grilling

摊开探索成果，沿方案树逐枝拷问，一次一问，附推荐答案 + 理由，等回答再出下一个。

顺序：方案选型 → 关键决策 → 实现步骤 → 验收条件 → 脆弱假设 → 约束红线

原则：能从代码回答的不问；具体到"另一个工程师能据此实现"；hard-to-reverse 决策必须明确确认。

方案确定后用 `AskUserQuestion` 收集 title / type / priority / blocked_by（第一选项推荐值）。scope 从讨论中确定不单独提问。

### 3. Spec 落库

`devtask_create_task` 落为 parent（`for_agent=true`，避免反悔不拆时产生 dead task）。

### 4. 拆子任务

**a. 草案：** 基于 spec 一次性推导全部子任务的 title / acceptance_criteria / constraints / context_pointers。type/priority/scope 从 parent 继承。

子任务要求：独立可执行、单 scope、不跨 5 文件/1 服务。

**b. 确认：** `AskUserQuestion` 打包确认拆分方案和所有子任务字段（有歧义的决策点单独追问，不混问卷）。选"不拆"时评估降级 simple。

**c. 落库：** `devtask_batch_create_tasks`（kind=subtask, parent_slug=spec, for_agent=true, blocked_by=留空）。超 20 条分批。

**d. 补依赖：** `devtask_update_task` 补子任务间的 blocked_by。

**e. 更新 parent：** acceptance_criteria 改为 `- [ ] task-N1: ... verify 通过` 列表。parent.for_agent = false。

### 5. 交付

```
Spec: task-N (kind: spec)
├── task-N1: <title> [parent: task-N]
├── task-N2: <title> [parent: task-N]
└── task-N3: <title> [parent: task-N]

Approved？启动：/devtask:devtask-doit task-N1
```

用户确认后可推进到待排期。

## Rules

- **Spec 必须拆** — 不允许只产出计划文档不落库
- **子任务不循环依赖** — blocked_by 只指同层前置；归属用 parent_slug
- **Parent ≠ worker** — 拆后 parent.for_agent = false
- **Fall fast** — 核心假设不成立 → 已搁置，detail 记录原因
- **Source of truth** — 走 `update_task` 修改，不重新 create
- **AskUserQuestion** — 第一选项推荐值；options 必须有 label + description
- **context_pointers** — 只列 read 过的文件，`path:line` 格式
