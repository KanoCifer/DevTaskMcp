---
name: devtask-setup
description: "Set up devtask kanban for a new project: verify API connectivity and write workflow guidance into CLAUDE.md. Use when initializing devtask in a project for the first time, setting up the kanban board, or configuring the devtask workflow."
argument-hint: [none]
disable-model-invocation: true
---

# devtask-setup

让一个新项目具备 devtask 工作流：检查环境，追加 CLAUDE.md 引导，交付初始化结果。

## 流程

### 1. 环境检查

- 检查 `DEVTASK_API_KEY` 非空
- 调用 `get_task("task-1")` 验证连通性（404 也算连通）

**失败处理：**

- `DEVTASK_API_KEY` 为空 → 提示从 kanocifer.chat 获取后终止
- API 调用失败 → 报告错误并终止

### 2. 写 CLAUDE.md 引导

读取项目的 `CLAUDE.md`（或 `~/.claude/CLAUDE.md`）。若已有 `## devtask 工作流`，跳过；否则将 `references/claude-md-template.md` 调整项目 scope 示例后追加到末尾。

### 3. 交付

```
✅ devtask 初始化完成

环境: 已连通（API Key 有效）
引导: 已写入 CLAUDE.md（或已存在）
任务: <已创建 task-N / 暂未创建>

下一步: /devtask:devtask 创建第一个任务
```

## Rules

- **幂等** — 重复运行不重复写入 CLAUDE.md，不重复创建 task
- **先检查再写** — 环境不通不写引导，避免无效配置
- **不覆盖用户内容** — 只追加 devtask 章节，不改动 CLAUDE.md 已有内容
