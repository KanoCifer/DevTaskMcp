---
name: devtask-simple
description: '为简单任务（小功能、bug fix、小优化）快速探索代码、形成方案、落库为一个可执行 task（for_agent=true, 原子粒度）。当用户抛出预计改动 ≤5 文件、不需要拆分为多个子任务的小意图时使用。典型触发："修一下 X 的 bug"、"加个 Y 按钮"、"这段代码能不能优化"。不适合：跨层改动、3+ 独立诉求、架构决策（用 devtask-plan）；价值/判断类（Evaluation 模式可覆盖）。'
argument-hint: [Brief description of the small task, bug fix, or improvement]
---

# devtask-simple

把简单意图快速变成**一个落库的可执行 task**（`for_agent=true`、无 parent、原子粒度）。

**三模式自动选择：**

| 意图                  | 模式            | 产出                           |
| --------------------- | --------------- | ------------------------------ |
| 修/加某物，问题已定义 | **Lightweight** | 一个推荐方案（2-3句） → 落库   |
| 判断应不应存在/保留   | **Evaluation**  | Keep / Kill / Pivot → 按需落库 |
| 一捆 3+ 独立诉求      | **Triage**      | 分类表 → accepted 项各自落库   |

## 任务追踪

探索和方案讨论阶段不建清单（事实没摸清，拆了也没用）。升级 `/devtask-plan` 则走它自己的流程，不建清单。

## 流程

### 步骤 1：探索

先探索代码再问用户——能从代码找的答案就别问。**进探索前先 `devtask_list_tasks` 检查是否有类似 task，已有则展示给用户判断是否继续**（避免白探索已跟踪的工作）。

- 模块名 → Read / grep / `codegraph_explore` 定位
- bug → 搜索 error path / 最近改动
- "加个 X" → 找现有类似实现复用模式
- 模糊目标 → 跑相关模块搞清结构

- 涉及框架能力时优先检查官方方案。

**退出条件：能回答以下三个问题时即进入步骤 2——① 改哪些文件 ② 大致怎么改 ③ 影响范围多大。**

### 步骤 2：方案

按意图类型激活模式。先**摊开步骤 1 成果**，再沿方案树逐枝推进——一次一问，附推荐答案 + 理由。

**模式选择：**

- 用户明确要"修"或"加某物" → Lightweight
- 用户在质疑价值/存在意义（"这个组件还有用吗"、"要不要删掉"） → Evaluation
- 用户抛出 3+ 独立且不相关的诉求 → Triage
- 拿不准时默认 Lightweight；探索中发现多诉求再转 Triage
- 注意："判断一下这个报错" = Debug，走 Lightweight 修掉；Evaluation 只用于**价值/存在判断**，不用于 bug 修复

#### Lightweight — 修/加某物

给一个推荐方案（改什么、在哪 `file:line`、为什么）。先给 brute-force 版本，默认采用。列出涉及文件，超 5 个则**升级到 `/devtask-plan`**。说一个风险。有 3+ 种真正不同路径时内部列出让用户选——不转交外部。

#### Evaluation — 判断应不应存在

当前状态快照后再表态。输出格式：

```
Keep / Kill /Pivot（第一行结论，不要开场白）

三条基于用户真实约束的理由
```

- Pivot → 逐一列出可操作新方向
- Kill → 先列影响范围和清理建议再确认；**Kill 不落库**（决策本身记录在聊天即可），若清理工作需要 task，作为独立诉求重新走流程
- 结论是 Keep 则落库 task，Kill 则不落，Pivot 则落库新方向

#### Triage — 一捆诉求

每个项分类：Bug / Already works / Accepted / Cosmetic / Out of scope。展示分类表等用户确认再逐项落库（先 grep 是否已有所需 affordance，避免误判缺口）。

分类指引：

- Cosmetic → 建议 drop 或积累到一定数量再批量处理
- Out of scope → 本次不建 task，记录拒绝原因
- Accepted → 批量用 `devtask_batch_create_tasks` 落库

### 步骤 3：Metadata 收集

方案确定后用 `AskUserQuestion`（Claude Code 内置交互组件，非 MCP 工具）一次收集所有字段：

```json
{
  "questions": [
    {
      "question": "Task 标题（动词开头）？",
      "header": "Title",
      "multiSelect": false,
      "options": [
        { "label": "<推荐>", "description": "..." },
        { "label": "其他" }
      ]
    },
    {
      "question": "任务类型？",
      "header": "Type",
      "multiSelect": false,
      "options": [
        { "label": "功能需求" },
        { "label": "优化" },
        { "label": "问题" },
        { "label": "技术债" }
      ]
    },
    {
      "question": "优先级？",
      "header": "Priority",
      "multiSelect": false,
      "options": [
        { "label": "P2 中" },
        { "label": "P1 高" },
        { "label": "P3 低" },
        { "label": "P0 紧急" }
      ]
    },
    {
      "question": "Scope？",
      "header": "Scope",
      "multiSelect": false,
      "options": [
        {
          "label": "<从代码库实际技术栈推导>",
          "description": "例如 前端-React / 后端-Python / 通用"
        },
        { "label": "其他" }
      ]
    }
  ]
}
```

规则：每个 Q 的第一个选项是 agent 推荐值；选"其他"返回后追加追问；`for_agent`/`kind=\"subtask\"` 默认不提问。

核心字段：`title`、`task_type`、`priority`、`scope` 来自 AskUserQuestion；`acceptance_criteria`（2-4 条可检查条件）、`context_pointers`（相关代码路径）来自方案讨论。

### 步骤 4：落库

**Triage accepted 项** → 用 `devtask_batch_create_tasks` 批量落库（每个 item 独立 task），避免多次 Metadata 收集。

其余模式 → `devtask_create_task` 一次性落库为原子 task。

展示卡片（title / type / priority / scope / acceptance_criteria / context_pointers），启动提示 `devtask:devtask-doit task-N`。

落库后 task 初始状态为 **待评估**。**可选：** 用户确认「可以推进」→ `devtask_update_task` 把状态推进到待排期，进入 frontier。

## Hard Rules

- **禁止重复落库：** 已有类似 task 先展示让用户判断
- **>5 文件/跨层 → 升级到 `/devtask-plan`**，不硬塞
- **禁止占位符（TBD/TODO）：** 含则 `for_agent=false` 标注未决项
- **唯一真相源：** 走 `devtask_update_task` 修改，不重新 create
- **攻破即报废：** 核心假设不成立则暂停回决策

## Gotchas

| 失败模式                           | 规则                                                                          |
| ---------------------------------- | ----------------------------------------------------------------------------- |
| acceptance_criteria 写成"功能正常" | 可检查、可观测："X 接口返回 200"、"Y 页面可渲染"                              |
| 方案超预期复杂                     | 立即升级到 `/devtask-plan`——不硬塞                                            |
| "判断一下这个报错" → Evaluation    | "判断一下" + bug = Debug，走 Lightweight 修掉；Evaluation 只用于价值/存在判断 |
| Triage 误判缺口                    | grep 已有 affordance 再分类——最常见浪费                                       |
| 写一堆无关 context_pointers        | 只列实际检索到的直接相关路径                                                  |
| 用户说"直接建吧"                   | 仍展示推荐值确认，不省略共享理解                                              |
| AskUserQuestion 没给推荐值         | 第一选项必须是 agent 推荐值                                                   |
| 简单任务写了 `parent_slug`         | simple 的 task 无 parent → 留空，独立可执行                                   |
