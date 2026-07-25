# Backend follow-up tasks for v3

The MCP server has been migrated to the Task Document v3 contract. The
following changes still need to happen in the Go backend that hosts the
dev-task API.  None of them block the MCP release; they are listed here
so the next backend change can pick them up without rediscovering the
work.

## 1. Drop the legacy long-text columns

- `description`
- `acceptance_criteria`
- `constraints`
- `context_pointers`

Conditions:

- The MCP server has stopped sending these fields.  Each legacy task
  needs its existing long-text content merged into the v3 Task Document
  body (Goal / Plan / Acceptance Criteria / Constraints / Context
  Pointers sections).  This is a one-shot backend migration; the
  resulting `detail` is the only long-text source of truth.
- Once the backend confirms no responses reference them for 30 days,
  the columns can be dropped from the DDL and the Go DTOs.

## 2. Tighten the `detail` contract

- Require `detail` to start with the `---` YAML front-matter delimiter
  for every newly created task.  The MCP server only creates documents
  in the new format, so existing legacy tasks must be migrated first.
- Reject `detail` payloads larger than the MCP cap (2 MB).

## 3. Drop the auto-`GET` after `PATCH`

The MCP server now treats the `PATCH` response as authoritative.  The
backend can keep the existing endpoint, but should document that the
response is allowed to return `data: null` and only the success flag.

## 4. Audit list endpoints

`list_tasks` and `list_children` should default to summary fields.  The
MCP server trims the response at the boundary today, but the backend
should add a `?fields=summary` query parameter so other clients don't
keep paying for full-body payloads.

## 5. Open issue checklist

When filing these in the backend repo, attach:

- The Task Document spec (`docs/task-document-v1.md`).
- A link to the MCP v3 changelog (this commit series).
- A reminder that the `devtask-mcp` server treats the backend as the
  source of truth for the structured columns and for the `detail`
  body, but does not rely on the legacy long-text columns any more.
