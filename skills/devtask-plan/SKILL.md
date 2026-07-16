---
name: devtask-plan
description: '调研需求形成 spec，再拆解为多个可执行的具体 task（输出 = spec + 子任务树）。当用户抛出一个预计改动 >5 文件、或需要跨层/多步骤的需求/功能/想法时使用——先明确做什么、怎么做，再落库为 spec + 子任务树。典型触发："做个 X 功能"、"规划一下这个需求"、"我有个想法想拆成几个 task"。不适合：简单的小修/小加/单文件改动（用 devtask-simple）；价值/判断类（用 devtask-simple 的 Evaluation 模式）。'
argument-hint:
  [Requirement / feature / idea to be specified and broken into tasks]
---

# devtask-plan

把模糊需求变成 **spec（做什么 + 方案）** 和一组 **可执行的具体 task**，通过 MCP 工具持久化。

**核心原则：spec → tasks。** 先达成"做什么、怎么做"的共享理解（spec），再拆解为多个可直接执行、可独立验证的 task。

## 流程

```
步骤 1: 探索 ──→ 从代码捞事实，压缩未知
步骤 2: 方案 ──→ Grilling 方案树 + AskUserQuestion 收 metadata → 形成 Spec
步骤 3: Spec 落库 ──→ devtask_create_task
步骤 4: 拆解为 Task ──→ 展示草案 → 逐个拷问 → 批量落库子 task → 补依赖 → 更新 parent
步骤 5: 交付 ──→ 展示结构树
```

### 步骤 1：探索

先探索代码再问用户——能从代码找的答案就别问：

- 模块名 → `codegraph_explore` / grep / Read 定位
- "接 XXX 功能" → 找对应 endpoint / handler / service
- bug → 搜索 error path / 最近改动
- 模糊目标 → 跑相关模块搞清结构

**同时做：** 用 `devtask_list_tasks` 查重复（有重复先展示让用户判断）；涉及框架能力时优先检查官方方案。

**退出条件：能回答以下三个问题时即进入步骤 2——① 改哪些文件 ② 大致怎么改 ③ 影响范围多大。**

**降级/升级 gate：** 步骤 1 结束时如果发现需求改动 ≤5 文件且单层次——建议降级到 `/devtask-simple`，本技能终止；如果发现需求超过 5 个文件或跨多个服务，保持在 plan 继续。

### 步骤 2：方案

#### 2a. 方案 Grilling

把步骤 1 成果摊开，**沿方案树逐枝拷问**——一次一问，附推荐答案 + 理由，等回答后再出下一个。

拷问按依赖链推进：方案选型 → 关键决策点 → 实现步骤 → 验收条件 → 脆弱假设 → 约束红线。

原则：一次一问不抛问卷；每个问题附推荐答案 + 理由；能从代码回答的不问；具体到"另一个工程师能据此实现"；Hard-to-reverse 决策（引入新语言/改公共 API）必须明确确认。

**示例（用户说"加 SSO 登录"）：**

- Q1: 用 NextAuth vs 自研 OAuth？（推荐 NextAuth，生态成熟、维护成本低）
- Q2: session 存 Redis vs JWT？（推荐 JWT，无状态、部署简单）
- Q3: 用户表加哪些字段？（推荐 provider / provider_id / avatar_url）
- Q4: 现有登录页改造还是新建路由？（推荐改造，保持 URL 稳定）

#### 2b. Metadata 收集

方案确定后用 `AskUserQuestion`（Claude Code 内置交互组件，非 MCP 工具）一次收集所有字段（`questions` 数组传 3-4 题）：

```json
{
  "questions": [
    {
      "question": "Spec 标题？",
      "header": "Title",
      "multiSelect": false,
      "options": [{ "label": "<推荐 title>" }, { "label": "其他" }]
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
      "question": "Spec 的前置依赖任务？（parent 自身的 blocked_by — 依赖其他 spec 时填写）",
      "header": "Deps",
      "multiSelect": true,
      "options": [
        { "label": "无依赖" },
        { "label": "task-XX: <标题>" },
        { "label": "其他" }
      ]
    }
  ]
}
```

规则：每个 Q 第一个选项是 agent 推荐值；选"其他"返回后追加追问；`scope` 通过方案讨论确定不单独提问（2b 末尾检查：若 2a 中未明确 scope 则追加一问）；`for_agent` 默认 true。

核心字段：`title`、`type`、`priority`、`scope`、`blocked_by` 来自 AskUserQuestion；`acceptance_criteria`、`constraints`、`context_pointers` 来自方案讨论。

**不要提前落库。** 用户确认方案 + metadata 前不调用 `devtask_create_task`。

### 步骤 3：Spec 落库

用 `devtask_create_task` 把 spec 落库为 parent task。始终按 for_agent: true 落库——避免用户反悔选「不拆」时产生不可执行的 dead task。

### 步骤 4：拆解为 Task

#### 4a. 展示草案

> 降级检查已前置到步骤 1 出口（见 §1），此处无需重复。若本步骤到达，说明需求复杂度达标。

提出子任务拆分方案，每个子任务必须满足：

- 独立可执行（有独立的 acceptance_criteria，不是"完成 spec 的一部分"）
- 单一 scope（不跨层、不跨 5 个文件或 1 个服务——超过则进一步拆）
- `for_agent: true`，从 parent 继承 priority

用 `AskUserQuestion` 确认拆分方案：确认拆分 / 调整拆分 / 不拆（作为单个 task）。选"不拆"时评估是否降级到 `/devtask-simple`。

#### 4b. 逐个产出子 Task

对每个子任务收集四个字段：`title`、`acceptance_criteria`、`constraints`、`context_pointers`——**type / priority / scope 从 parent 继承不重问**。

推荐流程：agent 先基于 parent spec 一次性推导全部子任务的四个字段草案 → AskUserQuestion 打包确认（不是每子任务单独一轮） → 用户确认后直接进 §4c。只有真正有歧义的决策点才单独追问，不在 grilling 阶段混问卷。

#### 4c. 批量落库

一次性批量落库全部子任务（`kind="subtask"`、`parent_slug` 指向 spec、`for_agent=true`）。单次上限 20 条，超出分批。

**同批内禁止跨任务 `blocked_by`**（slug 尚未分配，互相引用会失败）。先全部创建，`blocked_by` 留空，拿到 slug 后走 4d 补。依赖指向本 batch 外已有的任务时不受限。

#### 4d. 补同层顺序依赖

有顺序依赖的子任务走 `devtask_update_task` 补上 blocked_by。无顺序依赖则跳过。

#### 4e. 更新 Parent

1. 把 parent 的 acceptance_criteria 改为指向子任务完成状态：

```markdown
- [ ] task-N1: <子任务1 title> verify 通过
- [ ] task-N2: <子任务2 title> verify 通过
```

2. 把 parent 的 **for_agent 改为 false**（parent 是工头，不兼打工头；agent 只领子任务）。

### 步骤 5：交付

展示结构树：

```
Spec: task-N (kind: spec)
├── task-N1: <title> [parent_slug: task-N, for_agent: true]
├── task-N2: <title> [parent_slug: task-N, for_agent: true]
└── task-N3: <title> [parent_slug: task-N, for_agent: true]

启动：/devtask:devtask-doit task-N1
```

若用户确认「可以推进」，把 spec + 全部子任务一次性状态翻转到 **待排期**（进入 frontier）。如需只推进部分子任务，手动逐个推进即可。

## Hard Rules

- **禁止重复落库：** 已有类似 task 先展示让用户判断
- **Spec 始终拆解为可执行 task：** 不允许只产出计划文档不落库
- **No placeholders：** 所有字段在用户确认时具体。含占位符则 `for_agent=false` 标注未决项
- **唯一真相源：** 走 `devtask_update_task` 修改，不重新 create
- **子 Task 独立可执行：** acceptance_criteria 不隐含"等其他 task 完成"——用 `blocked_by` 声明顺序
- **子 Task 不循环依赖：** `blocked_by` 只指向同层前置；子→父归属写 `parent_slug`
- **Parent 不兼打工头：** 拆解后 parent 的 `for_agent` 设 false
- **攻破即报废：** 核心假设不成立则暂停，把 task 状态改为 **已搁置**，detail 字段记录哪条假设被攻破及攻破依据

## Gotchas

| 失败模式                            | 规则                                                         |
| ----------------------------------- | ------------------------------------------------------------ |
| acceptance_criteria 写成"功能正常"  | 可检查、可观测："X 接口返回 200"、"Y 页面可渲染"             |
| 子任务 scope 跨层（如"前端+后端"）  | 进一步拆到单层单技术                                         |
| child→parent 关系写错位置           | 归属用 `parent_slug`，`blocked_by` 只放同层前置              |
| 一次抛出多个 metadata 问题          | 2a grilling 一次一问；2b 才用 AskUserQuestion 打包——不要混淆 |
| 方案讨论停在"大概改一下"            | 必须深入到文件路径 + 改动内容粒度                            |
| 同批 batch 内写跨任务 `blocked_by`  | 必然失败——先批量创建再走 4d 用 `devtask_update_task` 补      |
| 需求实际很简单却走完 plan           | 步骤 4a 降级检查——≤5 文件单层次走 `/devtask-simple`          |
| 用户抛来 3+ 个不相关需求            | 相关需求合并走一次流程；不相关需求各自独立                   |
| 拆解后忘记设 parent.for_agent=false | 必须走 §4e — agent 只领子任务，parent 是工头                 |
| AskUserQuestion 没给推荐值          | 第一选项必须是 agent 推荐值                                  |
