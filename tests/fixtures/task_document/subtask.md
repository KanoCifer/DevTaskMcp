---
schema: devtask/v1
title: Slim MCP contract
task_type: 优化
priority: P1 高
scope: 后端-Python
kind: subtask
for_agent: true
---

## Goal

Drop the legacy long-text fields from the MCP create/update surface.

## Plan

1. Remove parameters.
2. Update tests.
3. Migrate skills.

## Acceptance Criteria

- [ ] `create_task` no longer accepts `description`
- [ ] `update_task` no longer accepts inline `acceptance_criteria`
- [ ] Skills only use the document-based tools

## Constraints

- Keep the Chinese enum validation at the boundary
- Do not break existing tasks stored in the backend

## Context Pointers

- `src/devtask_mcp/server.py:235`
- `skills/devtask-plan/SKILL.md:35`

## Out of Scope

- Frontend changes