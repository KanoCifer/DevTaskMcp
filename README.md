# Devtask MCP

Agent-native dev task board — investigate needs into well-specified tasks, execute them end-to-end. Pocock's frontier pattern with spec/slug/dependency fields and scope de-enum.

Combines:

- **MCP server** (`src/devtask_mcp/`) — wraps your kanocifer-chat dev-task API as 6 tools (`list_dev_tasks`, `get_dev_task`, `get_dev_task_by_slug`, `create_dev_task`, `update_dev_task`, `get_frontier_tasks`)
- **devtask-plan skill** (`.claude/skills/devtask-plan/`) — investigate a need, interview for spec, create the task
- **devtask-doit skill** (`.claude/skills/devtask-doit/`) — execute a task by slug or claim the frontier

## 安装

### 1. MCP server

配置到 Claude Code settings（`~/.claude.json`）：

```json
{
  "mcpServers": {
    "devtask": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/DevTaskMcp",
        "python",
        "-m",
        "devtask_mcp.server"
      ]
    }
  }
}
```

或 `.mcp.json` 项目根：

```json
{
  "devtask": {
    "command": "uv",
    "args": [
      "run",
      "--directory",
      "/path/to/DevTaskMcp",
      "python",
      "-m",
      "devtask_mcp.server"
    ]
  }
}
```

### 2. 环境变量

```bash
cp .env.example .env
# 编辑 .env 填 DEVTASK_API_KEY + DEVTASK_API_BASE
```

### 3. Skills

技能文件在 `.claude/skills/` 下，项目内自动加载。若想全局使用：

```bash
# 把软链或复制到全局 skills 目录
ln -s /path/to/DevTaskMcp/.claude/skills/devtask-plan ~/.claude/skills/devtask-plan
ln -s /path/to/DevTaskMcp/.claude/skills/devtask-doit ~/.claude/skills/devtask-doit
```

## 使用

```
/devtask-plan                          # 调研发明一个任务
/devtask-doit                          # 执行 frontier 里下一个
/devtask-doit task-42                  # 执行指定 slug 的任务
```

## 任务模型

| 字段                  | 语义                           |
| --------------------- | ------------------------------ |
| `slug`                | `task-N` 人类可读 ID，自增单调 |
| `acceptance_criteria` | 验收条件，doit 时逐条自检      |
| `constraints`         | 红线（不能动哪些文件）         |
| `context_pointers`    | 相关代码路径，省去文件探索     |
| `for_agent`           | 是否 agent 可执行              |
| `blocked_by`          | 依赖的任务 slug 列表           |
| `scope`               | `<层>-<技术>` 自由格式         |

## 结构

```
DevTaskMcp/
├── .claude-plugin/marketplace.json     # 插件市场清单
├── skills/
│   ├── devtask-plan/SKILL.md           # 技能：调研 → 生成 spec → 创建任务
│   └── devtask-doit/SKILL.md           # 技能：按 slug 执行任务
├── src/devtask_mcp/                    # MCP server Python 包
│   ├── __init__.py
│   ├── client.py                       # HTTP 封装，拆 envelope
│   ├── models.py                       # Pydantic 模型 + 中文 enum
│   └── server.py                       # FastMCP 6 tool 注册
├── pyproject.toml
└── README.md
```

## License

MIT
