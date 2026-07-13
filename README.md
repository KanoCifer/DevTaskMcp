# Devtask MCP

Agent-native dev task board — investigate needs into well-specified tasks, execute them end-to-end, verify acceptance criteria. Pocock's frontier pattern with spec/slug/dependency fields and scope de-enum.

Combines:

- **MCP server** (`src/devtask_mcp/`) — wraps your kanocifer-chat dev-task API as 6 tools (`list_dev_tasks`, `get_dev_task`, `get_dev_task_by_slug`, `create_dev_task`, `update_dev_task`, `get_frontier_tasks`)
- **Plugin** (`.claude-plugin/`) — bundles the MCP server + 3 skills into a single installable unit; MCP server auto-starts when the plugin is enabled
- **devtask-plan skill** — investigate a need, interview for spec, create the task
- **devtask-doit skill** — execute a task by slug or claim the frontier
- **devtask-verify skill** — verify a task's acceptance criteria against real code and runtime behavior

## Plugin Installation (recommended)

The plugin packages the MCP server and skills together. Enable it via your Claude Code plugin manager, or load it directly:

```bash
# Load from local directory
claude --plugin-dir /path/to/DevTaskMcp
```

Once enabled, the `devtask` MCP server starts automatically — no manual `.mcp.json` or `~/.claude.json` configuration needed.

By default the server launches via `uv run`, which resolves dependencies automatically. If you don't have `uv` installed, use one of the alternatives below before loading the plugin.

### Prerequisites

```bash
cp .env.example .env
# Fill in DEVTASK_API_KEY (required) and DEVTASK_API_BASE (optional)
```

`DEVTASK_API_KEY` is a Bearer <REDACTED> for the kanocifer-chat API. The server raises at startup if it is empty.

### Without uv

Two options if `uv` is not available on your machine:

**Option A — bootstrap a local venv (one-time setup):**

```bash
scripts/setup.sh              # creates .venv and installs dependencies
# or pick a specific interpreter:
PYTHON=python3.11 scripts/setup.sh
```

Then edit `.mcp.json` to point at the venv's python instead of `uv`:

```json
{
  "mcpServers": {
    "devtask": {
      "command": "/path/to/DevTaskMcp/.venv/bin/python",
      "args": ["-m", "devtask_mcp.server"]
    }
  }
}
```

**Option B — manual pip install:**

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Then use the same `.mcp.json` as Option A ( pointing at `.venv/bin/python` ).

## Manual Installation (without plugin)

If you prefer to run the MCP server standalone and load skills individually:

### 1. MCP server

Add to `~/.claude.json` or project `.mcp.json`. With `uv`:

```json
{
  "mcpServers": {
    "devtask": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/DevTaskMcp", "python", "-m", "devtask_mcp.server"]
    }
  }
}
```

Without `uv` (use the venv python — see" Without uv" above):

```json
{
  "mcpServers": {
    "devtask": {
      "command": "/path/to/DevTaskMcp/.venv/bin/python",
      "args": ["-m", "devtask_mcp.server"]
    }
  }
}
```

### 2. Environment

```bash
cp .env.example .env
# Fill in DEVTASK_API_KEY + DEVTASK_API_BASE
```

### 3. Skills

Skills live in `skills/` at the repo root and load automatically when you work in-project. For global use, symlink them:

```bash
ln -s /path/to/DevTaskMcp/skills/devtask-plan ~/.claude/skills/devtask-plan
ln -s /path/to/DevTaskMcp/skills/devtask-doit ~/.claude/skills/devtask-doit
ln -s /path/to/DevTaskMcp/skills/devtask-verify ~/.claude/skills/devtask-verify
```

## Usage

```
/devtask-plan                            # Investigate a need, create a task
/devtask-doit                            # Execute the next frontier task
/devtask-doit task-42                     # Execute a specific task by slug
/devtask-verify task-42                   # Verify a task's acceptance criteria
```

### Typical Workflow

1. `/devtask-plan` — describe what you want; the skill interviews you for a spec, then creates the task on the board.
2. `/devtask-doit task-N` — implements the task end-to-end, self-checks each acceptance criterion, then runs `/devtask-verify task-N` as a final gate before marking it done.
3. `/devtask-verify task-N` — independently re-checks every acceptance criterion against the actual code and runtime; reports pass/fail per criterion with evidence.

## Task Model

All text fields (`description`, `detail`, `acceptance_criteria`, `constraints`, `context_pointers`) support **Markdown formatting**.

| Field                 | Required | Meaning                                                        | Markdown |
| --------------------- | -------- | -------------------------------------------------------------- | -------- |
| `slug`                | auto     | `task-ID`, human-readable, monotonically increasing            | —        |
| `title`               | yes      | One-line summary, verb-first                                   | plain    |
| `type`                | yes      | `问题` / `功能需求` / `优化` / `技术债`                         | —        |
| `priority`            | yes      | `P0 紧急` / `P1 高` / `P2 中` / `P3 低`                        | —        |
| `scope`               | yes      | `<层>-<技术>` free-form, e.g. `后端-Go`                         | —        |
| `acceptance_criteria` | no       | Conditions for "done"; doit self-checks, verify re-checks     | list     |
| `constraints`         | no       | Hard boundaries (files, tech stack, benchmarks)                | list/table |
| `context_pointers`    | no       | Relevant code paths / docs / ADRs                              | code blocks |
| `for_agent`           | yes      | Agent-claimable flag (default `true`)                          | —        |
| `blocked_by`          | no       | Slug list of prerequisite tasks                               | —        |

Enum values are the **Chinese literals** the Go backend expects — never use English keys.

## Structure

```
DevTaskMcp/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest (metadata + mcp server ref)
│   └── marketplace.json         # Marketplace listing (3 skills)
├── .mcp.json                    # MCP server definition (auto-loaded by plugin)
├── skills/
│   ├── devtask-plan/SKILL.md    # Need → spec → create
│   ├── devtask-doit/SKILL.md    # Execute end-to-end + verify gate
│   └── devtask-verify/SKILL.md  # Read-only acceptance-criteria verification
├── src/devtask_mcp/             # MCP server Python package
│   ├── __init__.py
│   ├── client.py                # HTTP client, envelope unwrapping
│   ├── models.py                # Pydantic models + Chinese literal enums
│   └── server.py                # FastMCP, 6 tool registrations (English schemas)
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

## Architecture Notes

- **Envelope stripping at the boundary:** the Go backend wraps responses in `{code, message, data}`; `client._unwrap` strips it so MCP tools never waste tokens on wrapper fields.
- **Errors propagate verbatim:** non-2xx or `code != 0` raises `DevTaskAPIError` and the message surfaces to the agent as-is.
- **`per_page` capped at 20** regardless of caller input.
- **HTTP timeout:** 15.0 s.
- **Single long-lived client** at module level — safe because FastMCP stdio runs one server per agent session.
- **Slug is the canonical human ID** — use `task-N` in all UI, conversation, and MCP tool references.

## License

MIT
