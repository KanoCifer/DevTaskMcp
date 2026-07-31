# Task Document v1

A Task Document is a UTF-8 Markdown file with a YAML front matter
block. It is the only long-text source of truth for `devtask-mcp` v3.

```
---
schema: devtask/v1
title: "..."             # required
task_type: "..."         # required, Chinese literal
priority: "..."          # required, Chinese literal
scope: "..."             # required, "<layer>-<tech>"
slug: "task-xxx"         # optional, client-specified slug
kind: subtask            # optional, "spec" or "subtask"
for_agent: true          # optional, default true
parent_slug: "..."       # optional
blocked_by: ["..."]      # optional
due_date: "2026-09-30"   # optional, ISO 8601
---

## Goal

Short paragraph of what this task is for.

## Plan

Step-by-step implementation plan.

## Acceptance Criteria

- [ ] First checkable condition
- [ ] Second checkable condition

## Constraints

- Hard boundary 1
- Hard boundary 2

## Context Pointers

- `path/to/file.py:line`

## Decisions

- Recorded decision that needs to persist

## Out of Scope

- What is explicitly not part of this task
```

## Rules

- The front matter is parsed with PyYAML (`yaml.safe_load`) and validated
  strictly (mapping shape, required fields, Chinese enum literals). The
  same convention is used by skill `SKILL.md` files, so the model can
  reuse one mental model.
- Optional `slug` requests a client-specified slug (must match `task-xxx`,
  no whitespace or `/`); omit it to let the server assign one.
- Only the front matter is enforced. The Markdown body is a convention,
  not a requirement: `Goal`, `Plan`, `Acceptance Criteria`, etc. are
  parsed when present but never required, so free-form detail is
  accepted.
- `Acceptance Criteria` items conventionally use `- [ ]` syntax, but the
  parser never rejects other formats.
- `Context Pointers` items conventionally match `path:line`.
- Sections are matched case-insensitively on the heading.
- Unknown sections are kept verbatim and surfaced in `full` views.
- Repeated sections are allowed; the last occurrence wins.
- `detail` from a Task Document becomes the task's `detail` after the
  front matter is stripped.
- Front-matter fields override the API body's structured columns; if a
  field is missing from both the front matter and the API call, it is an
  error.
- Maximum size: 2 MB, same as the legacy `detail_file` cap.
- The file (`document_file`) must live under `/tmp` (the MCP server
  enforces this for security).  `create_task(.., document_file=...)`
  reads the file and parses its YAML front matter automatically.
