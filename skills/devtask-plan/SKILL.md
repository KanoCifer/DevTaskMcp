---
name: devtask-plan
description: "Research a requirement into a spec and break it into executable subtasks. Use when planning a complex feature, breaking down a requirement, creating a spec, discussing a multi-file change, or when the user says 'plan this out' or 'break this into tasks'."
argument-hint:
  [Requirement / feature / idea to be specified and broken into tasks]
---

# devtask-plan

把模糊需求变成 **spec** 和一组可执行的子任务。spec 用
`create_task(document_file=<path_to_file>)`（文件式 YAML front matter + Markdown）
落库，每个 subtask 用 `create_task`（内联 detail 参数）创建。

## 流程

### 1. 探索

- 模块名 → codegraph_explore / Read / grep
- "接 XXX 功能" → 找对应 endpoint / handler / service
- 涉及框架能力时优先查官方方案

**Gate：** 探索完发现 ≤5 文件且单层次 → 建议降级 `/devtask-simple`，终止

### 2. 方案 Grilling

调用 `/devtask:devtask-grill` skill 沿方案树逐枝拷问，一次一问，附推荐答案 + 理由，等回答再出下一个。

顺序：方案选型 → 关键决策 → 实现步骤 → 验收条件 → 脆弱假设 → 约束红线

原则：能从代码回答的不问；具体到"另一个工程师能据此实现"；hard-to-reverse 决策必须明确确认。

### 3. 写 spec 的 Task Document

用 `Write` 写一份 spec 的 Task Document 到 `/tmp/devtask-plan-<短名称>.md`，使用 `references/spec-template.md`。

### 4. 落库 spec

通过文件路径创建spec

```text
create_task(document_file="/tmp/devtask-plan-<短名称>.md")
```

记下返回的 `slug`（即 spec slug）。

### 5. 逐个创建 subtask

```text
create_task(
    title="<子任务标题>",
    task_type="功能需求",      # 或 优化 / 问题 / 技术债
    priority="P1 高",
    scope="Backend-Python",
    kind="subtask",
    parent_slug="<spec-slug>",   # 上一步返回的 slug
    slug="task-42",              # 可选，仅子任务，必须配合 parent_slug
    blocked_by=["task-N1"],      # 同层依赖（可选）
    detail="## Goal\n...\n\n## Plan\n...\n\n## Acceptance Criteria\n- [ ] ..."
)
```

每个 subtask 只放增量内容，重复的不抄父。

### 6. 交付

```text
Spec: task-N (kind: spec)
├── task-N1: <title> [parent: task-N]
├── task-N2: <title> [parent: task-N]
└── task-N3: <title> [parent: task-N]

Approved? 启动：/devtask:devtask-doit task-N1
```

## Rules

- **Spec 必须拆** — 不允许只产出计划文档不落库
- **父不放子任务的 Plan / AC** — 父只保留公共信息，子任务各写各的
- **Fall fast** — 核心假设不成立 → 已搁置，detail 记录原因
- **Source of truth** — 修改走 `update_task(slug, detail=...)`；状态变更走 `update_task(slug, status=...)`
- **Context Pointers** — 只列 read 过的文件，`path:line` 格式
