# DevTaskMcp

Agent 原生的 dev 任务看板 — 把需求调研成规格清晰的任务，端到端执行并验证验收条件。基于 Pocock 的 frontier 模式，含 spec/slug/dependency 字段和 scope 分类。

## 技能列表

| 技能               | 用途                                                | 触发                                                     |
| ------------------ | --------------------------------------------------- | -------------------------------------------------------- |
| `devtask-setup`    | 初始化项目：检查环境、写 CLAUDE.md 引导、可选落库    | 首次引入 devtask / "初始化 devtask" / "setup devtask"    |
| `devtask-grill`    | 正式规划前探讨方案选型、权衡和风险                  | 用户说"这个需求有什么方案" / "探讨一下几种方案优劣"      |
| `devtask-plan`     | 调研需求、访谈式产出规格、创建任务                  | 用户说"我想做个…" / "加个功能" / "修个 bug"              |
| `devtask-simple`   | 简单任务快速方案→落库一段流                         | 用户说"修个 X 的 bug" / "加个 Y 按钮" / 小优化          |
| `devtask-doit`     | 端到端执行任务，自检验收条件，verify 通过后标记完成 | 用户说"做 task-N" / "执行任务" / "work on the next task" |
| `devtask-review`   | 验收条件 + 四视角清理审查 + 正确性审查，能修就修 | 用户说"review task-N" / "verify task-N" / "验收 task-N" |

## 安装

### Claude Code Plugin（推荐）

单 plugin 包含 MCP server + 3 个技能，一次安装即可：

```bash
# 添加市场
claude plugins marketplace add KanoCifer/DevTaskMcp

# 安装插件
claude plugins install devtask@devtask
```

安装后 3 个技能均自动可用。MCP server 走 `.mcp.json` 定义的远程 URL —— 部署后把 `.mcp.json` 里的域名和 token 换成真实值，本地即通过远程实例提供服务。

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
# 1. 配置 MCP server（添加到 ~/.claude.json 或项目 .mcp.json，指向已部署的远程实例）
#    "type": "http",
#    "url": "https://你的域名/mcp/",
#    "headers": { "Authorization": "Bearer 你的MCP_AUTH_TOKEN" }

# 2. 链接技能目录
# 作为 user-level 技能（全局可用）
ln -s /path/to/DevTaskMcp/skills/devtask-setup ~/.claude/skills/devtask-setup
ln -s /path/to/DevTaskMcp/skills/devtask-grill ~/.claude/skills/devtask-grill
ln -s /path/to/DevTaskMcp/skills/devtask-plan ~/.claude/skills/devtask-plan
ln -s /path/to/DevTaskMcp/skills/devtask-simple ~/.claude/skills/devtask-simple
ln -s /path/to/DevTaskMcp/skills/devtask-doit ~/.claude/skills/devtask-doit
ln -s /path/to/DevTaskMcp/skills/devtask-review ~/.claude/skills/devtask-review

# 或作为 project-level 技能（放在项目 .claude/skills/ 下）
mkdir -p .claude/skills
ln -s /path/to/DevTaskMcp/skills/devtask-setup .claude/skills/devtask-setup
ln -s /path/to/DevTaskMcp/skills/devtask-grill .claude/skills/devtask-grill
ln -s /path/to/DevTaskMcp/skills/devtask-plan .claude/skills/devtask-plan
ln -s /path/to/DevTaskMcp/skills/devtask-simple .claude/skills/devtask-simple
ln -s /path/to/DevTaskMcp/skills/devtask-doit .claude/skills/devtask-doit
ln -s /path/to/DevTaskMcp/skills/devtask-review .claude/skills/devtask-review
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

然后在 `.mcp.json` 中指向远程实例（同「手动安装」第 1 步的 URL 配置）。

## 远程部署（streamable-http）

`devtask_mcp.server` 以 **streamable-http** transport 运行：一个长驻进程服务所有调用方，供外部 agent（Claude Code remote、Cursor 等）通过 URL 调用。

**1. 构建并启动（本机验证）**

```bash
cp .env.example .env       # 填 DEVTASK_API_KEY、MCP_AUTH_TOKEN
docker compose up --build
```

compose 只把端口绑到 `127.0.0.1:8003` —— 服务不直接暴露公网。

**2. 反向代理 + TLS（Nginx/Caddy 等，自行部署）**

把 `127.0.0.1:8003` 转发到 `https://你的域名/mcp/`（streamable-http 的标准端点路径是 `/mcp/`）。请求头必须原样透传，尤其是 `Authorization` 和 streamable-http 需要的 `Mcp-Session-Id`。

**3. 客户端连接**

```json
{
  "mcpServers": {
    "devtask": {
      "type": "http",
      "url": "https://你的域名/mcp/",
      "headers": { "Authorization": "Bearer 你的MCP_AUTH_TOKEN" }
    }
  }
}
```

> `MCP_AUTH_TOKEN` 留空时服务不启用应用层鉴权 —— 生产务必设置，并在反代层额外加 IP 白名单/限流。

## 配置

```bash
cp .env.example .env
# 填写 DEVTASK_API_KEY（必填）和 DEVTASK_API_BASE（可选）
```

`DEVTASK_API_KEY` 是 kanocifer-chat API 的 Bearer <REDACTED> 为空时 server 启动会报错。

远程部署时还需配置：

- `MCP_AUTH_TOKEN` — 外部 MCP 客户端调用时携带的 Bearer token。留空则关闭应用层鉴权（仅本地/内网）。
- `MCP_HOST` / `MCP_PORT` — HTTP 监听地址与端口，默认 `0.0.0.0:8003`。

## 使用

技能以 plugin 名命名空间：

```
/devtask:devtask-setup                   # 初始化：检查环境 + 写 CLAUDE.md 引导
/devtask:devtask-grill                   # 探讨方案选型与权衡
/devtask:devtask-plan                    # 调研需求，创建任务
/devtask:devtask-simple                  # 简单任务快速落库
/devtask:devtask-doit                    # 领取 frontier 最前排任务执行
/devtask:devtask-doit task-42            # 执行指定 slug 的任务
/devtask:devtask-review task-42          # 验收条件 + 四视角代码审查
```

## 工作流程

```
/devtask:devtask-setup                      ← 首次：初始化 + 写引导
    │
    ▼
需求描述
    │
    ▼
/devtask:devtask-grill
    │  探讨方案 → 选定方向
    │  (方案明确后进入 plan 或 simple)
    ▼
/devtask:devtask-plan / /devtask:devtask-simple
    │  访谈式调研 → 产出规格 → 创建任务
    ▼
/devtask:devtask-doit [task-N]
    │  端到端执行 → 自检验收条件 → /devtask:devtask-review
    ▼
/devtask:devtask-review [task-N]
    │  验收条件 + 四视角清理审查 + 正确性审查
    ▼
标记已完成
```

## 任务模型（v3 — Task Document）

v3 把所有长文本统一到一个 **Task Document**。`detail` 是唯一长文本字段，
正文必须使用固定章节：Goal / Plan / Acceptance Criteria / Constraints /
Context Pointers（外加 Decisions / Out of Scope）。其它结构化字段保持不变。

### MCP 工具

| 工具                               | 用途                                                    |
| ---------------------------------- | ------------------------------------------------------- |
| `create_task`                      | 内联参数或 `document_file` 创建任务（取代旧的两个工具）   |
| `update_task`                      | 修改状态字段 + 可选 detail 正文；`slugs=[]` 批量完成     |
| `get_task(slug, view=...)`         | `summary` / `full`                                        |
| `list_children`                    | 永远返回 summary 记录                                    |

### 视图

| view       | 返回内容                                                |
| ---------- | ------------------------------------------------------- |
| `summary`  | 结构化字段，不包含 detail                               |
| `full`     | 原始任务对象（含完整 detail）                            |

默认 `view=summary`，防止 agent 误把长文拉进上下文。

### 字段表

| 字段           | 必填 | 含义                                    | 形式           |
| -------------- | ---- | --------------------------------------- | -------------- |
| `slug`         | 自动 | `task-ID`，人类可读，单调递增           | —              |
| `title`        | 是   | 一行摘要，动词开头                      | plain          |
| `type`         | 是   | `问题` / `功能需求` / `优化` / `技术债` | —              |
| `priority`     | 是   | `P0 紧急` / `P1 高` / `P2 中` / `P3 低` | —              |
| `scope`        | 是   | `<层>-<技术>` 自由格式                  | —              |
| `kind`         | 否   | `spec` / `subtask`                      | —              |
| `parent_slug`  | 否   | 子任务归属的 spec slug                  | —              |
| `due_date`     | 否   | ISO-8601 截止日期                        | —              |
| `blocked_by`   | 否   | 同层前置依赖                            | —              |
| `for_agent`    | 是   | Agent 可认领标志                        | —              |
| `detail`       | 否   | Task Document 渲染后的 Markdown         | Markdown       |

枚举值使用 Go 后端期望的**中文字面量**——不要使用英文键。详细 Task Document
规范见 `docs/task-document-v1.md`。

## 目录结构

```
DevTaskMcp/
├── .claude-plugin/
│   ├── plugin.json              # Plugin 清单（元数据 + MCP server 引用）
│   └── marketplace.json         # 市场发布配置（3 个技能）
├── .mcp.json                    # MCP server 定义（plugin 自动加载）
├── skills/
│   ├── devtask-setup/SKILL.md   # 初始化：检查环境 + 写 CLAUDE.md 引导
│   ├── devtask-grill/SKILL.md   # 探讨方案选型与权衡
│   ├── devtask-plan/SKILL.md    # 需求 → 规格 → 创建
│   ├── devtask-simple/SKILL.md  # 简单任务快速落库
│   ├── devtask-doit/SKILL.md    # 端到端执行 + verify 门控
│   └── devtask-review/SKILL.md  # 验收条件 + 四视角清理审查 + 正确性审查
├── src/devtask_mcp/             # MCP server Python 包
│   ├── __init__.py
│   ├── client.py                # HTTP client，信封剥离
│   ├── models.py                # Pydantic 模型 + 中文枚举
│   └── server.py                # FastMCP，6 个工具注册（已 slug 化）
├── Dockerfile                 # 容器镜像（uv slim + 锁文件）
├── docker-compose.yml         # 单服务编排，端口回环绑定 8003
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

## 架构备注

- **边界剥离信封：** Go 后端用 `{code, message, data}` 包裹响应；`client._unwrap` 在边界剥离，MCP 工具不会浪费 token 在包装字段上。
- **错误原样传播：** 非 2xx 或 `code != 0` 抛出 `DevTaskAPIError`，错误信息原样呈现给 agent。
- **`per_page` 上限 20**，无论调用方传入多大值。
- **HTTP 超时：** 15.0 秒。
- **单例长连接 client** 在模块级别——streamable-http 下单个长驻进程服务所有调用方，client 无会话状态，共享安全。
- **Slug 是规范的人类 ID**——在所有 UI、对话和 MCP 工具引用中使用 `task-N`。后端已全面 slug 化，不再接受 ObjectID 输入。
- **`kind` / `parent_slug` 语义分离：** `parent_slug` 承载子→父的结构归属（`devtask_list_children` 走此索引），`blocked_by` 只承载同层前置依赖（执行顺序）。

## License

[MIT](LICENSE)
