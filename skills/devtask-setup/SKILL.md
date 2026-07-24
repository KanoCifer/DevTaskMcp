---
name: devtask-setup
description: "初始化项目使用 devtask 看板：检查环境连通性、在 CLAUDE.md 中写入工作流引导。"
argument-hint: [none]
disable-model-invocation: true
---

# devtask-setup

让一个新项目具备 devtask 工作流——环境检查 → 写引导 → 可选落库第一批 task。

## 流程

### 1. 环境检查

- 检查环境变量是否存在且 `DEVTASK_API_KEY` 非空
- 调用 `get_task("task-1")` 验证 API 连通性（任意已知 slug 即可，404 也表明连通）

**失败处理：**

- `DEVTASK_API_KEY` 为空 → 告知用户需要从 kanocifer.chat 获取 API Key，终止
- API 调用失败（`DevTaskAPIError`）→ 报告错误信息，终止

### 2. 写 CLAUDE.md 引导

在项目的 `CLAUDE.md`（或 `~/.claude/CLAUDE.md`）中写入 devtask 工作流引导，使后续 agent session 自动遵循。

**检查：** 先读取现有 CLAUDE.md，若已包含 `## devtask 工作流` 章节则告知用户并跳过写入。

**写入内容如下（根据项目实际情况调整 scope 示例），追加到 CLAUDE.md 末尾：**

    ## devtask 工作流

    本项目使用 devtask 看板管理开发任务。MCP server `devtask` 已注册以下工具：`create_task` / `batch_create_tasks` / `get_task` / `update_task` / `complete_task` / `list_children`。

    ### 工作流

    需求 → /devtask:devtask-plan（复杂）或 /devtask:devtask-simple（简单）
        → 落库为 spec + 子任务树
        → /devtask:devtask-doit task-N（执行指定任务）
        → /devtask:devtask-review（验收条件 + 代码审查）
        → 标已完成

    ### 何时使用

    | 场景 | 技能 |
    |------|------|
    | 预计改动 >5 文件、跨层、需要拆子任务 | `/devtask:devtask-plan` |
    | 预计改动 ≤5 文件、单意图 | `/devtask:devtask-simple` |
    | 执行已落库的任务 | `/devtask:devtask-doit task-N` |
    | 验收已完成任务 | `/devtask:devtask-review` |
    | 探讨方案选型 | `/devtask:devtask-grill` |

    ### 引用规范

    - spec 是规划节点（kind=spec），subtask 是可执行单元（kind=subtask）
    - `parent_slug` 承载结构归属，`blocked_by` 承载同层执行顺序依赖
    - 状态推进统一走 `complete_task`；其他字段修改走 `update_task`

**写入方式：** 追加到 CLAUDE.md 末尾（若已有 devtask 章节则不重复写入）。写入后告知用户已添加引导。

### 3. 交付

```
✅ devtask 初始化完成

环境: 已连通（API Key 有效）
引导: 已写入 CLAUDE.md（或已存在）
任务: <已创建 task-N / 暂未创建>

下一步: /devtask:devtask-plan 或 /devtask:devtask-simple 创建第一个任务
```

## Rules

- **幂等** — 重复运行不重复写入 CLAUDE.md，不重复创建 task
- **先检查再写** — 环境不通不写引导，避免无效配置
- **不覆盖用户内容** — 只追加 devtask 章节，不改动 CLAUDE.md 已有内容
