# DevTaskMcp

Agent 原生的 dev 任务看板 — 把需求调研成规格清晰的任务，端到端执行并验证验收条件。基于 Pocock 的 frontier 模式，含 spec/slug/dependency 字段和 scope 分类。

## 技能列表

| 技能             | 用途                                                | 触发                                                     |
| ---------------- | --------------------------------------------------- | -------------------------------------------------------- |
| `devtask-plan`   | 调研需求、访谈式产出规格、创建任务                  | 用户说"我想做个…" / "加个功能" / "修个 bug"              |
| `devtask-doit`   | 端到端执行任务，自检验收条件，verify 通过后标记完成 | 用户说"做 task-N" / "执行任务" / "work on the next task" |
| `devtask-verify` | 对照实际代码和运行时行为独立验证验收条件            | 用户说"verify task-N" / "验收 task-N"                    |

## 安装

### Claude Code Plugin（推荐）

单 plugin 包含 MCP server + 3 个技能，一次安装即可：

```bash
# 添加市场
claude plugins marketplace add KanoCifer/DevTaskMcp

# 安装插件
claude plugins install devtask@devtask
```

安装后 3 个技能均自动可用，MCP server 自动启动，无需手动配置 `.mcp.json`。

或在 Claude 对话框中交互完成：

```
/plugin marketplace add KanoCifer/DevTaskMcp
/plugin install devtask@devtask
```

本地开发加载：

```bash
claude --plugin-dir /path/to/DevTaskMcp
```

默认通过 `uv run` 启动 server，自动解析依赖。如果机器上没有 `uv`，参考下方「无 uv」章节。

### 手动安装（不用 plugin）

把技能目录链接到 Claude Code 的技能路径，并手动配置 MCP server：

```bash
# 1. 配置 MCP server（添加到 ~/.claude.json 或项目 .mcp.json）
#    带 uv：
#      "command": "uv",
#      "args": ["run", "--directory", "/path/to/DevTaskMcp", "python", "-m", "devtask_mcp.server"]
#    不带 uv：
#      "command": "/path/to/DevTaskMcp/.venv/bin/python",
#      "args": ["-m", "devtask_mcp.server"]

# 2. 链接技能目录
# 作为 user-level 技能（全局可用）
ln -s /path/to/DevTaskMcp/skills/devtask-plan ~/.claude/skills/devtask-plan
ln -s /path/to/DevTaskMcp/skills/devtask-doit ~/.claude/skills/devtask-doit
ln -s /path/to/DevTaskMcp/skills/devtask-verify ~/.claude/skills/devtask-verify

# 或作为 project-level 技能（放在项目 .claude/skills/ 下）
mkdir -p .claude/skills
ln -s /path/to/DevTaskMcp/skills/devtask-plan .claude/skills/devtask-plan
ln -s /path/to/DevTaskMcp/skills/devtask-doit .claude/skills/devtask-doit
ln -s /path/to/DevTaskMcp/skills/devtask-verify .claude/skills/devtask-verify
```

注意：手动安装时技能不带有 `devtask:` 命名空间前缀。

### 无 uv

如果机器上没有 `uv`，两种方式准备 Python 环境：

**方式 A — 初始化脚本（推荐）：**

```bash
scripts/setup.sh              # 创建 .venv 并安装依赖
# 或指定解释器：
PYTHON=python3.11 scripts/setup.sh
```

**方式 B — 手动 pip install：**

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

然后在 `.mcp.json` 中指向 `.venv/bin/python`：

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

## 配置

```bash
cp .env.example .env
# 填写 DEVTASK_API_KEY（必填）和 DEVTASK_API_BASE（可选）
```

`DEVTASK_API_KEY` 是 kanocifer-chat API 的 Bearer <REDACTED> 为空时 server 启动会报错。

## 使用

技能以 plugin 名命名空间：

```
/devtask:devtask-plan                    # 调研需求，创建任务
/devtask:devtask-doit                    # 领取 frontier 最前排任务执行
/devtask:devtask-doit task-42            # 执行指定 slug 的任务
/devtask:devtask-verify task-42          # 验证任务的验收条件
```

## 工作流程

```
需求描述
    │
    ▼
/devtask:devtask-plan
    │  访谈式调研 → 产出规格 → 创建任务
    ▼
/devtask:devtask-doit [task-N]
    │  端到端执行 → 自检验收条件 → /devtask:devtask-verify
    ▼
/devtask:devtask-verify [task-N]
    │  独立验证验收条件（对照代码 + 运行时）
    ▼
标记已完成
```

## 任务模型

所有文本字段（`description`、`detail`、`acceptance_criteria`、`constraints`、`context_pointers`）支持 **Markdown 格式**。

| 字段                  | 必填 | 含义                                    | Markdown    |
| --------------------- | ---- | --------------------------------------- | ----------- |
| `slug`                | 自动 | `task-ID`，人类可读，单调递增           | —           |
| `title`               | 是   | 一行摘要，动词开头                      | plain       |
| `type`                | 是   | `问题` / `功能需求` / `优化` / `技术债` | —           |
| `priority`            | 是   | `P0 紧急` / `P1 高` / `P2 中` / `P3 低` | —           |
| `scope`               | 是   | `<层>-<技术>` 自由格式，如 `后端-Go`    | —           |
| `kind`                | 否   | `spec`（规划节点）/ `subtask`（可执行） | —           |
| `parent_slug`         | 否   | 子任务归属的 spec slug；spec 自身留空   | —           |
| `acceptance_criteria` | 否   | "完成"的条件；doit 自检，verify 复检    | list        |
| `constraints`         | 否   | 硬性边界（文件、技术栈、基准）          | list/table  |
| `context_pointers`    | 否   | 相关代码路径 / 文档 / ADR               | code blocks |
| `for_agent`           | 是   | Agent 可认领标志（默认 `true`）         | —           |
| `blocked_by`          | 否   | 同层前置依赖的 slug 列表（执行顺序）    | —           |

枚举值使用 Go 后端期望的**中文字面量**——不要使用英文键。

**字段语义分离：** `parent_slug` 承载子→父的结构归属（`devtask_list_children` 走此索引），`blocked_by` 只承载同层前置依赖（执行顺序）。两者不再混用。

## 目录结构

```
DevTaskMcp/
├── .claude-plugin/
│   ├── plugin.json              # Plugin 清单（元数据 + MCP server 引用）
│   └── marketplace.json         # 市场发布配置（3 个技能）
├── .mcp.json                    # MCP server 定义（plugin 自动加载）
├── skills/
│   ├── devtask-plan/SKILL.md    # 需求 → 规格 → 创建
│   ├── devtask-doit/SKILL.md    # 端到端执行 + verify 门控
│   └── devtask-verify/SKILL.md  # 只读验收条件验证
├── src/devtask_mcp/             # MCP server Python 包
│   ├── __init__.py
│   ├── client.py                # HTTP client，信封剥离
│   ├── models.py                # Pydantic 模型 + 中文枚举
│   └── server.py                # FastMCP，6 个工具注册（已 slug 化）
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

## 架构备注

- **边界剥离信封：** Go 后端用 `{code, message, data}` 包裹响应；`client._unwrap` 在边界剥离，MCP 工具不会浪费 token 在包装字段上。
- **错误原样传播：** 非 2xx 或 `code != 0` 抛出 `DevTaskAPIError`，错误信息原样呈现给 agent。
- **`per_page` 上限 20**，无论调用方传入多大值。
- **HTTP 超时：** 15.0 秒。
- **单例长连接 client** 在模块级别——安全，因为 FastMCP stdio 每个 agent session 只运行一个 server。
- **Slug 是规范的人类 ID**——在所有 UI、对话和 MCP 工具引用中使用 `task-N`。后端已全面 slug 化，不再接受 ObjectID 输入。
- **`kind` / `parent_slug` 语义分离：** `parent_slug` 承载子→父的结构归属（`devtask_list_children` 走此索引），`blocked_by` 只承载同层前置依赖（执行顺序）。

## License

[MIT](LICENSE)
