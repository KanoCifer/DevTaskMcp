---
name: devtask-plan
description: "Research a requirement into a spec and break it into executable subtasks. Use when planning a complex feature, breaking down a requirement, creating a spec, discussing a multi-file change, or when the user says 'plan this out' or 'break this into tasks'."
argument-hint:
  [Requirement / feature / idea to be specified and broken into tasks]
---

# devtask-plan

把模糊需求变成 **spec** 和一组可执行的子任务。遵循 `../references/task-contract.md`：spec 用 `create_task(document_file=<path>)` 落库，subtask 用内联 `create_task` 创建。
## 流程

### 1. 探索

- 模块名 → codegraph_explore / Read / grep
- "接 XXX 功能" → 找对应 endpoint / handler / service
- 涉及框架能力时优先查官方方案

**Gate：** 探索完发现 ≤5 文件且单层次 → 建议降级 `/devtask-simple`，终止

### 2. 方案 Grilling

调用 `/devtask:devtask-grill`：每轮同时询问当前 frontier 的所有决策，给出推荐答案；等待用户回答后再扩展下一轮。

顺序：方案选型 → 关键决策 → 实现步骤 → 验收条件 → 脆弱假设 → 约束红线。

能从代码查到的事实不问；提问必须具体到另一个工程师可以据此实现。

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

- **Spec 必须拆并落库** — 不只产出计划文档
- **父只放公共信息** — 子任务各自写 Plan / AC
- **Fall fast** — 核心假设不成立则记录原因并 `已搁置`
- **Source of truth** — 正文用 `update_task(slug, detail=...)`，状态用 `update_task(slug, status=...)`
- **Context Pointers** — 只列实际读过的 `path:line`
