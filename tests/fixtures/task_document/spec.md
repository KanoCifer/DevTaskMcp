---
schema: devtask/v1
title: Reduce DevTask workflow token cost
task_type: 优化
priority: P1 高
scope: 后端-Python
kind: spec
for_agent: false
---

## Goal

Make `devtask-mcp` cheap to drive for an agent without losing task fidelity.

## Decisions

- Use YAML front matter (PyYAML), same convention as skill `SKILL.md`.
- Keep `due_date` structured; everything else is in the document.

## Constraints

- The MCP server must never read paths outside `/tmp`.
- The Go backend is not modified in this repo.

## Context Pointers

- `CLAUDE.md:1`
- `README.md:160`