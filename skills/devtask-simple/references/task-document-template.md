```yaml
---
title: "<动词 + 目标>"
task_type: 问题        # 或 功能需求 / 优化 / 技术债
priority: P1 高         # 或 P0 紧急 / P2 中 / P3 低
scope: "<层>-<技术>"
kind: subtask
for_agent: true       # 不填自定义slug字段
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

`Goal` 和 `Acceptance Criteria` 必填。AC 必须 `- [ ]` 开头。`Context Pointers` 必须是 `path:line` 格式。MCP 边界会校验中文 enum 并拒绝非 `/tmp` 下的文件。
