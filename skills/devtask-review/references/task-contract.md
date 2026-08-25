# Task Document 共享契约

所有 DevTask 技能遵循以下约定。

## 工具

- `get_task(slug, view="full")`：读取完整 Task Document；验收和执行需要正文时使用。
- `list_children(parent_slug=slug)`：读取 spec 的子任务摘要。
- `create_task(...)`：内联参数创建任务，长文放 `detail`。
- `update_task(slug, status=...)`：更新单个任务状态。
- `update_task(slugs=[...])`：批量将状态设为 `已完成`。
- `update_task(slug, detail=...)`：替换完整 detail，用于更新 Plan、Decisions 等正文。

`blocked_by` 非空时，先检查 blocker 状态；未完成的 blocker 不执行。

## Task Document

结构化字段通过 `create_task` 的内联参数传入，`detail` 正文使用以下章节：

- `Goal`
- `Plan`
- `Acceptance Criteria`
- `Constraints`
- `Context Pointers`
- `Decisions`
- `Out of Scope`

验收项推荐使用 `- [ ]` / `- [x]`，解析器不强制 checkbox 格式。`Context Pointers` 使用 `path:line` 格式。

`create_task` 需要中文枚举：type 为 `问题`、`功能需求`、`优化` 或 `技术债`；priority 为 `P0 紧急`、`P1 高`、`P2 中` 或 `P3 低`。子任务必须提供 `parent_slug`；slug 由服务端分配，不能自行指定。
