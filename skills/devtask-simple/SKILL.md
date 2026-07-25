---
name: devtask-simple
description: '为简单任务（小功能、bug fix、小优化）快速探索代码、形成方案、落库为一个可执行 task（for_agent=true, 原子粒度）。当用户抛出预计改动 ≤5 文件、不需要拆分为多个子任务的小意图时使用。典型触发："修一下 X 的 bug"、"加个 Y 按钮"、"这段代码能不能优化"。不适合：跨层改动、3+ 独立诉求、架构决策（用 devtask-plan）；价值/判断类（Evaluation 模式可覆盖）。'
argument-hint: [Brief description of the small task, bug fix, or improvement]
disable-model-invocation: true
---

# devtask-simple

把简单意图快速变成**一个落库的可执行 task**。

v3 工作流：唯一长文本是 `detail`（Markdown）。方案、验收标准、约束、上下文指针
都写在 **Task Document** 里面。

## 模式选择

```
修/加某物，问题已定义  →  Lightweight（方案 → 落库一段流）
价值/存在判断          →  Evaluation（Keep / Kill / Pivot）
3+ 独立诉求            →  Triage（分类 → accepted 批量落库——每个走 create_task）
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

**Lightweight：** 列出文件路径 + 每文件改动概要。推荐方案默认采用。3+ 种真正不同路径时让用户选。→ 用 `Write` 写一份 Task Document 到 `/tmp/devtask-simple-<短名称>.md`（YAML front matter + 固定章节）→ `create_task(document_file=...)` → MCP 完成后只回报 slug。

**Triage：** 每项分 Bug / Already works / Accepted / Cosmetic / Out of scope。展示分类表确认 → Accepted 各项逐个调 `create_task(title=..., task_type=..., priority=..., scope=..., detail="## Goal...")` 创建。不要合并成一个 task。

**Evaluation：** 输出 Keep / Kill / Pivot（第一行结论，不要开场白，三条理由）。Kill 不落库；Pivot 落库新方向；Keep 落库 task。Evaluation 模式落库也用 Task Document。

### Task Document 模板

```yaml
---
title: "<动词 + 目标>"
task_type: 问题        # 或 功能需求 / 优化 / 技术债
priority: P1 高         # 或 P0 紧急 / P2 中 / P3 低
scope: "<层>-<技术>"
kind: subtask
for_agent: true
---

## Goal

一两句目标。

## Plan

1. 步骤 1
2. 步骤 2

## Acceptance Criteria

- [ ] 可检查的验收项 1
- [ ] 可检查的验收项 2

## Constraints

- 硬性边界（可选）

## Context Pointers

- `path/to/file.py:line`（只列 read 过的文件）
```

`Goal` 和 `Acceptance Criteria` 必填。AC 必须 `- [ ]` 开头。`Context Pointers`
必须是 `path:line` 格式。MCP 边界会校验中文 enum 并拒绝非 `/tmp` 下的文件。

## Rules

- **>5 files → upgrade** — 不硬塞 simple；方案超预期复杂也升级
- **Simple 无 parent** — 独立可执行，不写 parent_slug
- **Evaluation 不用于 bug** — "判断这个报错" = Lightweight 修复
- **Source of truth** — 修改走 `update_task(slug, detail=...)`；状态类变更走 `update_task(slug, status=...)` 或 `update_task(slugs=[...])`
- **信任 MCP 视图** — detail 正文、AC 列表、context pointers 由 MCP 解析，不要重复解析或复述
