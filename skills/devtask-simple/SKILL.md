---
name: devtask-simple
description: '为简单任务（小功能、bug fix、小优化）快速探索代码、形成方案、落库为一个可执行 task（for_agent=true, 原子粒度）。当用户抛出预计改动 ≤5 文件、不需要拆分为多个子任务的小意图时使用。典型触发："修一下 X 的 bug"、"加个 Y 按钮"、"这段代码能不能优化"。不适合：跨层改动、3+ 独立诉求、架构决策（用 devtask-plan）；价值/判断类（Evaluation 模式可覆盖）。'
argument-hint: [Brief description of the small task, bug fix, or improvement]
---

# devtask-simple

把简单意图快速变成**一个落库的可执行 task**（`for_agent=true`、无 parent、原子粒度）。

## 模式选择

```
修/加某物，问题已定义  →  Lightweight（方案 → 落库一段流）
价值/存在判断          →  Evaluation（Keep / Kill / Pivot）
3+ 独立诉求            →  Triage（分类 → accepted 批量落库）
拿不准                 →  默认 Lightweight
```

## 流程

### 1. 探索

- 模块名 → codegraph_explore / Read / grep
- bug → 搜索 error path / 最近改动
- 涉及框架能力时优先查官方方案

**退出条件：** 知道改哪些文件、怎么改、影响范围
**Gate：** >5 文件复杂任务，建议 `/devtask-plan`

### 2. 方案 → 落库（一段流）

按模式处理，方案确定后立即落库，不拆分步骤：

**Lightweight：** 列出文件路径 + 每文件改动概要。推荐方案默认采用。3+ 种真正不同路径时让用户选。→ `AskUserQuestion` 收集 title/type/priority/scope → `devtask_create_task`

**Evaluation：** 输出 Keep / Kill / Pivot（第一行结论，不要开场白，三条理由）。Kill 不落库；Pivot 落库新方向；Keep 落库 task。

**Triage：** 每项分 Bug / Already works / Accepted / Cosmetic / Out of scope。展示分类表确认 → Accepted 用 `devtask_batch_create_tasks` 批量落库。

### 落库卡片

```
title / type / priority / scope
acceptance_criteria（2-4 条可检查条件）
context_pointers（只列 read 过的文件，path:line）
```

task 初始状态：待排期。

## Rules

- **>5 files → upgrade** — 不硬塞 simple；方案超预期复杂也升级
- **Simple 无 parent** — 独立可执行，不写 parent_slug
- **Evaluation 不用于 bug** — "判断这个报错" = Lightweight 修复
- **Source of truth** — 走 `update_task` 修改，不重新 create
- **context_pointers** — 只列 read 过的文件，`path:line` 格式
