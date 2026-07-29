```yaml
---
title: "<spec 标题>"
task_type: 功能需求      # 或 优化 / 问题 / 技术债
priority: P1 高           # 或 P0 紧急 / P2 中 / P3 低
scope: "<层>-<技术>"
kind: spec
---

## Goal

spec 级别的公共目标。

## Decisions

- 关键决策 1：<结论 + 理由>
- 关键决策 2：<结论 + 理由>

## Constraints

- 硬性边界（技术栈、性能红线等）

## Context Pointers

- `path/to/file.py:line`（只列 read 过的文件）
```

spec 只放公共内容（Goal / Decisions / Constraints / Context Pointers），不放子任务的 Plan / AC。子任务各写各的增量内容（Goal / Plan / Acceptance Criteria）。
