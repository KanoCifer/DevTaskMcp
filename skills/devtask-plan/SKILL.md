---
name: devtask-plan
description: 调研需求并产出完整的 dev-task 规格。当用户说"我想做个..."、"加个功能"、"修个 bug"、"记个任务"，或抛出一个应该被跟踪的任务想法时使用。
---

# devtask-plan

**关键词：spec。** 每次运行把一个模糊的需求变成一份紧凑的任务规格——标题、验收条件、约束、上下文指针、范围、依赖——然后通过 devtask MCP 工具持久化。产出的任务是"可直接执行"级别的：agent（或未来的你）不需要重新推导原始意图就能执行。

## 三步流程

### 步骤 1：探索 — 从代码里捞事实

拿到用户的原始意图后，**先探索代码，把能确认的事实全部捞出来**。不要急着问用户——能从代码里找到的答案就别问。

探索路径：

- 用户说 XXX 模块 → `codegraph_explore` / grep / Read 定位 `XXX` 相关文件和调用链
- 用户说"接 XXX 功能" → 找对应 endpoint / handler / service
- 用户说 bug → 搜索相关 error log / 代码路径 / 最近改动
- 用户提了一个模糊目标 → 跑一遍相关模块，搞清楚现有结构和边界

**目标：把"未知"压缩到最小。** 最后只把真正需要用户做决策的事项留给步骤 2。

**Completion criterion:** 已确认的相关文件路径列表；已识别出用户的真实目标（不是字面措辞）；剩余未决事项已归类为"决策"而非"事实"。

### 步骤 2：拷问 — 逐个击破决策点

把步骤 1 探索到的成果摊开给用户，然后**就剩下的决策点进行逐一拷问**。拷问原则沿用 `/grilling`：一次只问一个、每个问题附带推荐答案、事实是你的而决策是用户的、沿设计树先上游后下游。

落库字段模板（对应 `DevTaskOut` 模型，`create_dev_task` 需要的字段）：

| 字段 | 是否必填 | 说明 |
|------|----------|------|
| `title` | ✅ | 一句话执行摘要，动词开头 |
| `type` | ✅ | `问题` / `功能需求` / `优化` / `技术债` |
| `priority` | ✅ | `P0 紧急` / `P1 高` / `P2 中` / `P3 低` |
| `acceptance_criteria` | ✅ | 2-4 条可检查的完成条件 |
| `constraints` | 可选 | 红线：禁动文件、禁用技术、不可回退的 benchmark |
| `context_pointers` | 可选 | 相关代码路径 / 文档 / ADR |
| `scope` | 可选 | `<层>-<技术>` 格式，如 `后端-Go` |
| `for_agent` | ✅ | 默认 `true`；spec 不完整或需人工判断则劝 `false` |
| `blocked_by` | 可选 | 依赖的任务 slug 列表，无则空数组 |

拷问顺序（按依赖关系排列，不是闭包枚举）：

1. **title** — 一句话执行摘要。推荐动词开头："Add X"、"Fix Y"、"Refactor Z"。
2. **type** — `问题` / `功能需求` / `优化` / `技术债`。根据意图推荐一个。
3. **priority** — `P0 紧急` / `P1 高` / `P2 中` / `P3 低`。默认 `P2 中`，除非用户明确表态。
4. **acceptance_criteria** — 完成时验证什么？推荐 2-4 条可检查的条件（"feature flag is on"、"all 3 endpoints return 200"、"no regression in X"）。
5. **constraints** — 红线：不能动哪些文件、不能用哪些技术、benchmark 不能回退。用户没提则问"有没有硬性约束？"
6. **context_pointers** — 相关代码路径 / 文档 / ADR。把步骤 1 检索到的路径写进来让用户确认补充。
7. **scope** — 推荐 `<层>-<技术>` 格式（`前端-React`、`后端-Go`、`AI-LangChain`）。用户可以自定义。
8. **for_agent** — 是否 agent 可执行？默认 `true`（spec 够完整）；spec 不完整或需人工判断则劝 `false`。
9. **blocked_by** — 依赖哪些任务？用户说 slug（`task-42`），空数组表示没有。

**不要提前落库。** 在用户确认所有决策点已达成的共享理解之前，不调用 `create_dev_task`。

**Completion criterion:** 所有必填字段各自有用户明确确认（或用户说"你的推荐就行"）；用户表示"这就是我想要的"。

### 步骤 3：落库 — 写入 devtask

用户确认后，用 MCP tool `create_dev_task` 把确认后的字段落库。

**Completion criterion:** 返回体含 `slug`（如 `task-5`）。

### 步骤 4：交付

向用户展示：slug + title + acceptance_criteria 列表。提示后续动作（`/grill-me` 复审 / `/devtask-doit <slug>` 直接执行）。

**Completion criterion:** 用户看到完整 spec 快照。

## MCP 字段格式

通过 `create_dev_task` / `update_dev_task` 写入的文本字段（`title`、`acceptance_criteria`、`constraints`、`context_pointers`、`description`、`detail`），**内容使用 Markdown 格式**。

格式规范：
- `acceptance_criteria` → **有序或无序列表**，每条条件独立一行，可加粗关键断言
- `constraints` → **列表**，每条红线一条；或表格（禁动文件 | 原因）
- `context_pointers` → **列表**，路径用代码块包裹（`src/devtask_mcp/server.py`），可附简要说明
- `description` / `detail` → 支持 Markdown（标题、列表、代码块、链接）
- `title` → 纯文本，不加 Markdown 标记

**例外：** 用户明确说"纯文本"时按用户要求。

## 唯一真相源

落库后的 spec 是唯一真相。后续修改走 `update_dev_task`，不重新 create。
