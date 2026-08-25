---
name: devtask
description: "Turn a requirement or bug into executable devtask(s) on the kanban board. Handles all scales: single fix (one task), batch triage (multiple tasks), keep/kill/pivot evaluation, and complex multi-file features (spec + subtasks with grilling). Use when the user wants to plan, create, or file tasks — e.g. 'plan this out', 'break this into tasks', 'just fix this', 'quick task', '加个功能', '修个 bug'."
argument-hint: [Requirement / bug / idea to be turned into devtask(s)]
---

# devtask

把需求或 bug 变成**落库的可执行 task**。遵循 `../references/task-contract.md` 的 Task Document 契约。

## 模式选择

探索后按规模路由：

```
单点改动，问题已定义（≤5 文件）   →  Lightweight（方案 → 落库一个 task）
3+ 独立诉求                      →  Triage（分类 → accepted 批量落库）
价值/存在判断                    →  Evaluation（Keep / Kill / Pivot）
多文件、多层次、需拆解（>5 文件）→  Spec + Subtasks（含 Grilling）
只想探讨方案，不立即落库         →  Grilling（references/grill.md）
拿不准                           →  默认 Lightweight；探索完发现复杂再升 Spec
```

## 流程

### 1. 探索

- 模块名 → codegraph_explore / Read / grep
- bug → 搜索 error path / 最近改动；"接 XXX 功能" → 找对应 endpoint / handler / service
- 涉及框架能力时优先查官方方案

**退出条件：** 知道改哪些文件、怎么改、影响范围。能从代码查到的事实不问。

### 2a. Lightweight — 单点改动

列出文件路径 + 每文件改动概要。推荐方案默认采用。3+ 种真正不同路径时让用户选。

→ 直接落库：

```text
create_task(
    title="...",
    task_type="问题",        # 问题 / 功能需求 / 优化 / 技术债
    priority="P2 中",
    scope="Backend-Python",
    detail="## Goal\n...\n\n## Acceptance Criteria\n- [ ] ..."
)
```

完成后只回报 slug。

### 2b. Triage — 批量杂项

每项分 Bug / Already works / Accepted / Cosmetic / Out of scope。展示分类表确认 → Accepted 各项逐个调 `create_task(...)` 创建。不要合并成一个 task。

### 2c. Evaluation — 存在判断

输出 Keep / Kill / Pivot（第一行结论，不要开场白，三条理由）。Kill 不落库；Pivot 落库新方向；Keep 落库 task。

### 2d. Spec + Subtasks — 复杂需求

**Grilling：** 按 `references/grill.md` 的 frontier 访谈协议执行：每轮同时询问当前 frontier 的所有决策，给出推荐答案；等待用户回答后再扩展下一轮。顺序：方案选型 → 关键决策 → 实现步骤 → 验收条件 → 脆弱假设 → 约束红线。提问必须具体到另一个工程师可以据此实现。

**落库 spec：**

```text
create_task(
    title="<spec 标题>",
    task_type="功能需求",    # 或 优化 / 问题 / 技术债
    priority="P1 高",
    scope="Backend-Python",
    kind="spec",
    detail="## Goal\n...\n\n## Plan\n...\n\n## Acceptance Criteria\n- [ ] ..."
)
```

记下返回的 `slug`。

**逐个创建 subtask：**

```text
create_task(
    title="<子任务标题>",
    task_type="功能需求",
    priority="P1 高",
    scope="Backend-Python",
    kind="subtask",
    parent_slug="<spec-slug>",   # spec 返回的 slug
    blocked_by=["task-N1"],      # 同层依赖（可选）
    detail="## Goal\n..."        # 只放增量内容，重复的不抄父
)
```

**交付：**

```text
Spec: task-N (kind: spec)
├── task-N1: <title> [parent: task-N]
├── task-N2: <title> [parent: task-N]
└── task-N3: <title> [parent: task-N]

Approved? 启动：devtask-doit task-N1
```

### Task Document 结构

`detail` 使用固定章节：`Goal` 和 `Acceptance Criteria` 必填；AC 推荐 `- [ ]` 格式。`Context Pointers` 使用 `path:line` 格式，只列实际读过的文件。

## Rules

- **Simple 无 parent** — Lightweight / Triage / Evaluation 产出的 task 独立可执行，不写 parent_slug
- **Evaluation 不用于 bug** — "判断这个报错" = Lightweight 修复
- **Spec 必须拆并落库** — 不只产出计划文档
- **父只放公共信息** — 子任务各自写 Plan / AC
- **Fall fast** — 核心假设不成立则记录原因并 `已搁置`
- **Source of truth** — 正文修改走 `update_task(slug, detail=...)`；状态类变更走 `update_task(slug, status=...)` 或 `update_task(slugs=[...])`
- **信任 MCP 视图** — detail 正文、AC 列表、context pointers 由 MCP 解析，不要重复解析或复述
