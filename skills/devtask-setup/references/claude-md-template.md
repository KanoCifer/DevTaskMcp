## devtask 工作流

本项目使用 devtask 看板管理开发任务。MCP server `devtask` 提供 v3 工具，**优先用 skill 而不是直接拼工具调用**。

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
- 状态推进统一走 `update_task(slug, status=...)` 或 `update_task(slugs=[...])`；其它字段修改走 `update_task(slug, detail=...)`
