---
name: devtask-plan
description: '调研需求形成 spec，再拆解为多个可执行的具体 task（输出 = spec + 子任务树）。当用户抛出一个预计改动 >5 文件、或需要跨层/多步骤的需求/功能/想法时使用——先明确做什么、怎么做，再落库为 spec + 子任务树。典型触发："做个 X 功能"、"规划一下这个需求"、"我有个想法想拆成几个 task"。不适合：简单的小修/小加/单文件改动（用 devtask-simple）；价值/判断类（用 devtask-simple 的 Evaluation 模式）。'
argument-hint:
  [Requirement / feature / idea to be specified and broken into tasks]
disable-model-invocation: true
---

# devtask-plan

把模糊需求变成 **spec** 和一组可执行的子任务。spec 用
`create_task_document`（文件式 YAML front matter + Markdown 章节）
落库，每个 subtask 用 `create_task`（内联 detail 参数）创建。
**不要在对话里输出完整 spec 正文** — 写一次文件即可。

## 流程

### 1. 探索

- 模块名 → codegraph_explore / Read / grep
- "接 XXX 功能" → 找对应 endpoint / handler / service
- 涉及框架能力时优先查官方方案

**Gate：** 探索完发现 ≤5 文件且单层次 → 建议降级 `/devtask-simple`，终止

### 2. 方案 Grilling

摊开探索成果，沿方案树逐枝拷问，一次一问，附推荐答案 + 理由，等回答再出下一个。

顺序：方案选型 → 关键决策 → 实现步骤 → 验收条件 → 脆弱假设 → 约束红线

原则：能从代码回答的不问；具体到"另一个工程师能据此实现"；hard-to-reverse 决策必须明确确认。

方案确定后用 `AskUserQuestion` 收集 title / type / priority / blocked_by（第一选项推荐值）。scope 从讨论中确定不单独提问。

### 3. 写 spec 的 Task Document

用 `Write` 写一份 spec 的 Task Document 到 `/tmp/devtask-plan-<短名称>.md`（YAML front matter + 固定章节）。

spec 只放公共内容（Goal / Decisions / Constraints / Context Pointers），不放子任务的 Plan / AC。

### 4. 落库 spec

```text
create_task_document(document_file="/tmp/devtask-plan-<短名称>.md")
```

记下返回的 `slug`（即 spec slug）。

### 5. 逐个创建 subtask

对每个子任务调用 `create_task`，内联 detail 参数传入子任务自身的 Markdown 正文。

```text
create_task(
    title="<子任务标题>",
    task_type="功能需求",      # 或 优化 / 问题 / 技术债
    priority="P1 高",
    scope="后端-Python",
    kind="subtask",
    parent_slug="<spec-slug>",   # 上一步返回的 slug
    blocked_by=["task-N1"],      # 同层依赖（可选）
    detail="## Goal\n...\n\n## Plan\n...\n\n## Acceptance Criteria\n- [ ] ..."
)
```

每个 subtask 只放增量内容（Goal / Plan / Acceptance Criteria），重复的不抄父。**不要在对话里拼好整篇 Markdown 再调 MCP** — 直接在 detail 参数传简洁正文即可。

### 6. 交付

```text
Spec: task-N (kind: spec)
├── task-N1: <title> [parent: task-N]
├── task-N2: <title> [parent: task-N]
└── task-N3: <title> [parent: task-N]

Approved? 启动：/devtask:devtask-doit task-N1
```

**只报告 slug 树，不要复述 Task Document 内容**。要查正文就
`get_task(slug, view="execute")`。

## Rules

- **Spec 必须拆** — 不允许只产出计划文档不落库
- **写一次文件** — spec 的 Task Document 写 /tmp 后不要再在对话里复述
- **子任务不依赖 spec slug 以外的东西** — blocked_by 用已知 slug，不要猜
- **父不放子任务的 Plan / AC** — 父只保留公共信息，子任务各写各的
- **Fall fast** — 核心假设不成立 → 已搁置，detail 记录原因
- **Source of truth** — 修改走 `update_task(slug, detail=...)`；状态变更走 `update_task(slug, status=...)`
- **AskUserQuestion** — 第一选项推荐值；options 必须有 label + description
- **Context Pointers** — 只列 read 过的文件，`path:line` 格式
