# Task Document v1

A Task Document is the long-text convention for `devtask-mcp` v3:
structured fields would live in YAML front matter, and all long text
goes in a single `detail` Markdown body passed inline to
`create_task` / `update_task`.

```
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

Structured fields (title, type, priority, scope, kind, parent_slug,
blocked_by, due_date, …) are passed as inline parameters — never in
the Markdown body.

## Rules

- Slug is always server-assigned. Use `parent_slug` to link a subtask
  to its spec.
- The body structure is a convention, not a requirement: `Goal`,
  `Plan`, `Acceptance Criteria`, etc. are recognized when present but
  never required, so free-form detail is accepted.
- `Acceptance Criteria` items conventionally use `- [ ]` syntax.
- `Context Pointers` items conventionally match `path:line`.
- Sections are matched case-insensitively on the heading; repeated
  sections are allowed with the last occurrence winning.
