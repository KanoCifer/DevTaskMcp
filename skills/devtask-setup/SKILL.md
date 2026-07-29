---
name: devtask-setup
description: "Set up devtask kanban for a new project: verify API connectivity and write workflow guidance into CLAUDE.md. Use when initializing devtask in a project for the first time, setting up the kanban board, or configuring the devtask workflow."
argument-hint: [none]
disable-model-invocation: true
---

# devtask-setup

让一个新项目具备 devtask 工作流——环境检查 → 写引导 → 可选落库第一批 task。

## 流程

### 1. 环境检查

- 检查环境变量是否存在且 `DEVTASK_API_KEY` 非空
- 调用 `get_task("task-1")` 验证 API 连通性（404 也表明连通）

**失败处理：**

- `DEVTASK_API_KEY` 为空 → 告知用户需要从 kanocifer.chat 获取 API Key，终止
- API 调用失败（`DevTaskAPIError`）→ 报告错误信息，终止

### 2. 写 CLAUDE.md 引导

在项目的 `CLAUDE.md`（或 `~/.claude/CLAUDE.md`）中写入 devtask 工作流引导，使后续 agent session 自动遵循。

**检查：** 先读取现有 CLAUDE.md，若已包含 `## devtask 工作流` 章节则告知用户并跳过写入。

**写入内容：** 读取 `references/claude-md-template.md`，根据项目实际情况调整 scope 示例后，追加到 CLAUDE.md 末尾。

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
