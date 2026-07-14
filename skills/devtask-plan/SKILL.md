---
name: devtask-plan
description: "调研需求形成 spec，再拆解为多个可执行的具体 task。当用户抛出一个应被跟踪的需求/功能/想法时使用——先明确做什么、怎么做，再落库为可执行的 task 单元。"
argument-hint: [What do you want to plan?]
---

# devtask-plan

把模糊需求变成一个 **spec（做什么 + 方案）** 和一组 **可执行的具体 task**，然后通过 MCP 工具持久化。

**核心原则：spec → tasks。** 先和用户达成"做什么、怎么做"的共享理解（spec），再拆解为多个可直接执行、可独立验证的 task。每个 task 交給 agent（或未来的你）时不需要重新推导原始意图。

## Outcome Contract

- Outcome: 一份 spec + 一组落库的可执行 task。
- Done when: spec 已落库（返回含 `slug` 的响应）；所有子 task 已落库；用户看到完整的 spec → tasks 结构树。
- Evidence: 当前代码状态、项目 CLAUDE.md、已有任务列表（去重）、用户的明确决策。
- Output: parent spec slug + 每个 task 的 slug/title/acceptance_criteria，以及后续动作提示。

## 流程概览

```
步骤 1: 探索 ──→ 从代码捞事实，压缩未知
步骤 2: 拷问 ──→ Grilling 方案树 + AskUserQuestion 收 metadata → 形成 Spec
步骤 3: Spec 落库 ──→ create_dev_task(parent)
步骤 4: 拆解为 Task ──→ 展示草案 → 逐个拷问 → 批量落库子 task → 补同层依赖 → 更新 parent
步骤 5: 交付 ──→ 展示 spec → tasks 结构树
```

### 步骤 1：探索 — 从代码里捞事实

拿到用户的原始意图后，**先探索代码，把能确认的事实全部捞出来**，使用Explore subagent或自行探索。不要急着问用户——能从代码里找到的答案就别问。

探索路径：

- 用户说 XXX 模块 → `codegraph_explore`（如有） / grep / Read 定位 `XXX` 相关文件和调用链
- 用户说"接 XXX 功能" → 找对应 endpoint / handler / service
- 用户说 bug → 搜索相关 error log / 代码路径 / 最近改动
- 用户提了一个模糊目标 → 跑一遍相关模块，搞清楚现有结构和边界

**目标：把"未知"压缩到最小。** 最后只把真正需要用户做决策的事项留给步骤 2。

探索时，如果涉及框架内置能力或生态标准用法，优先搜索官方方案而非默认自定义实现。有官方方案时默认推荐官方方案，除非能明确说明它不满足当前场景。

**Completion criterion:** 已确认的相关文件路径列表；已识别出用户的真实目标（不是字面措辞）；剩余未决事项已归类为"决策"而非"事实"；已检查重复任务。

### 步骤 2：拷问 — Spec（方案 + metadata）

拷问目标：**形成一个完整的 spec**——不仅包含 metadata（title / type / priority），还包含**具体方案内容**（改什么、怎么改、怎么验证）。

拷问分两个阶段：

#### 2a. 方案拷问（Grilling 设计树）

把步骤 1 探索到的成果摊开给用户，然后**沿方案树逐枝拷问**。

**思维模型：方案树。** 每个方案分叉为多个决策，决策之间存在依赖——上游决策改变下游的问题域。因此拷问必须**按依赖顺序逐个发问**，而不是一次性抛出清单。一次只问一个，等用户回答后下一个问题可能因上一个答案而改变。

**拷问顺序（按依赖链排列）：**

| 阶段          | 拷问内容                                                                        | 产出                       |
| ------------- | ------------------------------------------------------------------------------- | -------------------------- |
| 1. 方案选型   | 推荐什么方案、为什么选这个而不是别的、核心改动在哪（具体到文件路径）            | 方案思路锁定               |
| 2. 关键决策点 | 方案中有分歧的地方（用 X 还是 Y 库、改现有接口还是新增、先迁移还是 dual-write） | 设计决策 + 理由            |
| 3. 实现步骤   | 分几步、每步改什么、步骤间依赖。超 3 个独立阶段则标记为子任务拆分候选项         | 执行计划 / 子任务边界      |
| 4. 验收条件   | 整体完成时怎么验证？推荐 2-4 条可检查条件                                       | `acceptance_criteria` 草稿 |
| 5. 脆弱假设   | 方案依赖什么前提？前提不成立怎么办？                                            | `constraints` 草稿         |
| 6. 约束红线   | 禁动文件、禁用技术、不可回退的 benchmark                                        | `constraints` 确认         |

**拷问原则：**

- **一次一问，等待回答后再出下一个。** 不要抛问卷——依赖链上一题的答案决定下一题问什么。
- **每个问题附带 agent 的推荐答案 + 理由。** 事实是你的，决策是用户的。
- **能从代码里回答的问题不问用户。** 步骤 1 已经探索过的直接用。
- **具体到"另一个工程师能据此实现"。** "加个缓存"→"在 X 层加 Redis，key=`prefix:{id}`，TTL 60s"。
- **Hard-to-reverse 决策（如引入新语言/运行时、改公共 API）必须明确确认+记录。** 可逆的偏好选择直接推荐即可。

#### 2b. Metadata 收集（一次性 AskUserQuestion）

方案讨论完成后，用 `AskUserQuestion` **一步收集所有 metadata 字段**。不要逐条问——把所有选择题打包成一次调用（`questions` 数组传 3-4 个问题）。

真实调用示例（每个 `options` 的第一个选项是 agent 的推荐值）：

```json
{
  "questions": [
    {
      "question": "Spec 标题是什么？（一句话说明这个需求要做什么）",
      "header": "Title",
      "multiSelect": false,
      "options": [
        {
          "label": "<推荐的 title>",
          "description": "如：'Add user login via OAuth'"
        },
        { "label": "其他", "description": "自定义标题" }
      ]
    },
    {
      "question": "任务类型？",
      "header": "Type",
      "multiSelect": false,
      "options": [
        { "label": "功能需求", "description": "新增功能" },
        { "label": "优化", "description": "性能/体验改进" },
        { "label": "问题", "description": "修 bug" },
        { "label": "技术债", "description": "重构/清理" }
      ]
    },
    {
      "question": "优先级？",
      "header": "Priority",
      "multiSelect": false,
      "options": [
        { "label": "P2 中", "description": "默认优先级" },
        { "label": "P1 高", "description": "比较紧急" },
        { "label": "P3 低", "description": "可以排后面" },
        { "label": "P0 紧急", "description": "线上故障级别" }
      ]
    },
    {
      "question": "是否有前置依赖任务？",
      "header": "Deps",
      "multiSelect": true,
      "options": [
        { "label": "无依赖", "description": "当前无阻塞任务" },
        {
          "label": "task-XX: <已有任务标题>",
          "description": "依赖已存在的任务"
        },
        { "label": "其他", "description": "自定义 slug" }
      ]
    }
  ]
}
```

**规则：**

- 每个 `options` 数组的**第一个选项**必须是 agent 基于 2a 讨论产出的推荐值（用户可以直接回车确认）
- `multiSelect: true` 仅用于依赖等可能存在多选的字段
- 选了"其他"时，`AskUserQuestion` 返回后追加简短追问获取具体值
- `scope` 和 `for_agent` 通过 2a 方案讨论确定，默认 `<层>-<技术>` + `for_agent: true`，不单独提问

**Parent Spec 字段模板：**

| 字段                  | 是否必填 | 来源                                          |
| --------------------- | -------- | --------------------------------------------- |
| `title`               | ✅       | AskUserQuestion Title                         |
| `type`                | ✅       | AskUserQuestion Type                          |
| `priority`            | ✅       | AskUserQuestion Priority                      |
| `acceptance_criteria` | ✅       | 2a 讨论产出（整体验收条件），用户确认         |
| `constraints`         | 可选     | 2a 讨论产出（脆弱假设 / 红线）                |
| `context_pointers`    | 可选     | 步骤 1 检索到的代码路径 + 2a 补充的文档 / ADR |
| `scope`               | ✅       | 2a 讨论产出（`<层>-<技术>` 格式）             |
| `for_agent`           | ✅       | 完善后设 `true`；                             |
| `blocked_by`          | 可选     | AskUserQuestion Deps                          |
| `parent_slug`         | 否       | 是否是任务的Spec                              |
| `kind`                | ✅       | 任务类型（`spec` 或 `subtask`）               |

**Completion criterion:** 方案讨论到达"另一个工程师能据此实现"的精度；`AskUserQuestion` 所有必填字段有用户确认；用户表示"这就是我想要的"；已确认无重复任务。

**不要提前落库。** 在用户确认方案 + metadata 已达成的共享理解之前，不调用 `create_dev_task`。

### 步骤 3：Spec 落库 — 写入 parent task

用户确认后，用 `create_dev_task` 把 spec 落库为一个 parent task。**始终先按 `for_agent: true` 落库**——即使预期要拆分，也保持可执行状态直到步骤 4d 实际完成拆分后才降级。这避免了步骤 4a 用户反悔选「不拆」时产生不可执行的 dead task。

向用户展示 spec 快照，然后**进入步骤 4 决定如何拆解为可执行 task**。

**Completion criterion:** 返回体含 `slug`（如 `task-5`）；用户看到 spec 快照；task 为 `for_agent: true`。

### 步骤 4：拆解为可执行 Task

Spec 落库后，把它拆解为**多个可直接执行的具体 task**。这是 `devtask-plan` 的核心产出——不是一份文档，而是可以逐个 `doit` 的工作单元。

#### 4a. 展示拆解草案

基于步骤 2a 的实现步骤和 context_pointers，提出子任务拆分方案。每个子任务必须满足：

- **独立可执行**：有独立的、可检查的 acceptance_criteria（不是"完成 spec 的一部分"）
- **单一 scope**：不能跨层、不能跨 5 个文件或 1 个服务——超过则进一步拆
- **`for_agent: true`**（如果 spec 够完整）
- **从 parent 继承 priority**——子任务默认和 parent 同优先级

用 `AskUserQuestion` 确认拆分方案：

```
question: "按以下方案拆分为 N 个子任务？"
header: "Split"
options:
  - label: "确认拆分"              description: "按草案拆为 N 个子任务"
  - label: "调整拆分"              description: "需要增删改子任务"
  - label: "不拆，作为一个 task"    description: "spec 足够小，直接执行"
multiSelect: false
```

如果用户选"不拆，作为一个 task" → 跳过 4b-4d，parent 本身已是可执行 task，直接跳到步骤 5。

#### 4b. 逐个产出子 Task spec

对每个子任务运行步骤 2 的**轻量版拷问**——只问该子任务特有的决策点：

- `title`（一句话动词开头）
- `acceptance_criteria`（2-4 条独立可检查条件）
- `constraints`（特有红线）
- `context_pointers`（具体到文件路径）

**从 parent 继承的字段不再问**：`type`、`priority`、`scope`。

一次 `AskUserQuestion` 收一个子任务的 metadata（每个子任务 1 次调用，2-3 题）。所有子任务依次处理。

#### 4c. 批量落库子 Task

**用 `batch_create_tasks` 一次调用落库全部子任务**——不要逐个 `create_dev_task`。一次 batch = 一次 MCP round-trip = 省 N 倍 token + N 倍延迟，失败条目单独重试即可。

每个子任务设置：

- `kind: "subtask"` — 标记为可执行子任务
- `parent_slug: "<parent_slug>"` — 指向所属 spec（结构归属）
- `for_agent: true`（默认）

**单次上限 20 条。** 超出 20 个子的 spec 需要分批——拆成多次 `batch_create_tasks` 调用，每批 ≤20 条，按批返回的 slug 推进。

**`batch_create_tasks` 的跨任务约束（必读）：** 同批内 **禁止跨任务 `blocked_by`**——因为同一批次的 slug 尚未分配，互相引用会失败。处理顺序：

1. **先批量创建全部子任务**，`blocked_by` 留空（无论有没有同层顺序依赖）。
2. **拿到全部 slug 后，走步骤 4d**，用 `update_dev_task(slug, blocked_by=[sibling_slug])` 把同层前置依赖补上。
3. 依赖指向**本 batch 之外**的已有任务（非本次创建的）时，`blocked_by` 可以直接写在 batch 里——不受限制。

返回体::

```json
{
  "succeeded": [{"index": 0, "slug": "task-43", "title": "..."}],
  "failed":    [{"index": 2, "title": "...", "error": "..."}],
  "summary":   "9/10 created"
}
```

- `succeeded`/`failed` 里的 `index` 对应输入数组下标，用于定位失败条目。
- 有失败时**只重试 failed 里的条目**（用 `index` 取对应输入，单独再跑一次 batch），不要整批重跑。
- 超过 20 条被截断时返回 ToolError（`单次最多 20 条…`），按提示分批。

**与旧版的关键区别：** 原来写 `blocked_by: [parent_slug]` 不再正确——parent 关系由 `parent_slug` 承载，`blocked_by` 只承载同层前置依赖。这使得 `list_children(parent_slug)` 走后端 parent_slug 索引查询，不再全表扫描 + 过滤。

#### 4d. 补同层顺序依赖（仅在有顺序依赖时执行）

步骤 4c 创建时 `blocked_by` 留空了。此时所有子任务 slug 已分配，对于存在同层前置依赖的子任务（如"子任务 2 必须等子任务 1 完成"），逐个调用 `update_dev_task(slug, blocked_by=[sibling_slug])` 补上。

- 返回的 `succeeded` 列表里的slug 就是引用目标——直接用，不要猜 slug 编号。
- 无顺序依赖的 spec（所有子任务可并行）→ 跳过本步骤。

**Completion criterion:** 所有顺序依赖已用 `update_dev_task` 显式声明；无遗漏。

#### 4e. 更新 Parent 指向子 Task

用 `update_dev_task` 把 parent 的 acceptance_criteria 改为指向子任务完成状态：

```markdown
## 验收条件

- [ ] task-N1: <子任务1 title> verify 通过
- [ ] task-N2: <子任务2 title> verify 通过
- [ ] task-N3: <子任务3 title> verify 通过
```

**Completion criterion:** 所有子任务已落库；parent acceptance_criteria 已更新；parent `kind` 确认为 spec；用户看到完整结构树。

### 步骤 5：交付

全部落库完成后：

1. 向用户展示最终结构树（参见下方 `Output` 章节）；
2. 若用户确认「可以推进」，调用 `transition_plan(parent_slug, status="待排期")`，
   把 spec 和所有子任务一次性从「待评估」翻到「待排期」，让它们出现在
   frontier 里可被领取。返回 `{ succeeded, failed }` —— 有失败时逐条告知；
   用 `batch_create_tasks` 创建的子任务默认状态是「待评估」，所以动作为「待评估 → 待排期」
   是安全的，不会发生「进行中 → 待排期」这种逆流转。
3. 一行启动提示：`devtask:devtask-doit <首个子任务 slug>`。

**Completion criterion:** 用户看到完整 spec → tasks 树；spec + 子任务已成功推进到待排期；知道从哪个 task 开始 `doit`。

## Hard Rules

- **禁止重复落库：** 步骤 1 已用 `list_dev_tasks` 检查过的，后续步骤不再绕过。发现重复先展示已有任务，让用户判断是补充还是新建。
- **Spec 始终拆解为可执行 task。** `devtask-plan` 的产出永远是 spec + task 集合。不允许只产出一份"计划文档"而不落库可执行的 task。如果方案足够小（≤5 文件、1 个阶段），可以只有 1 个原子 task，但仍需走步骤 4 的确认。
- **No placeholders in approved specs.** 所有字段在用户确认时必须是具体的。禁止 TBD、TODO、"后面再补"、"参照 task-N 的做法"。含占位符时把 `for_agent` 改 `false` 并标注未决项。
- **唯一真相源：** 落库后的 spec 是唯一真相。后续修改走 `update_dev_task`，不重新 create。
- **每个子 Task 独立可执行。** acceptance_criteria 不能隐含"等其他 task 完成"——需要顺序用 `blocked_by` 声明（仅同层前置）。
- **子 Task 不能循环依赖。** `blocked_by` 只能指向同层前置 task，不允许环路；子→父归属由 `parent_slug` 承载，不动 `blocked_by`。
- **Parent 不兼打工头。** Parent 被分解为子任务后 `for_agent` 必须为 `false`，对 parent 调用 doit 时拒绝并引导到子任务。
- **攻破即报废：** 步骤 2 发现核心假设不成立时，不带着已知注定失败的条件落库——暂停，告知用户，回到决策。

## Output

最终输出：完整的 spec → tasks 结构树。

```
Spec: task-N (kind: spec, for_agent: true)
├── task-N1: <title> [kind: subtask, parent_slug: task-N, for_agent: true]
├── task-N2: <title> [kind: subtask, parent_slug: task-N, for_agent: true]
└── task-N3: <title> [kind: subtask, parent_slug: task-N, for_agent: true]

启动：/devtask:devtask:doit task-N1
```

如果 spec 本身是原子 task（未拆分）：

```
Task: task-N (kind: spec, for_agent: true)
title: <title>
acceptance_criteria:
- <条件 1>
- <条件 2>

启动：/devtask:devtask:doit task-N
```

## Gotchas

| 失败模式                            | 规则                                                                                 |
| ----------------------------------- | ------------------------------------------------------------------------------------ |
| 用户说"加个登录按钮"但没说平台      | 步骤 1 先 grep 项目确认是 iOS / Android / Web，再推荐的 scope 带平台信息             |
| acceptance_criteria 写成"功能正常"  | 条件必须可检查、可观测。改写为"X 接口返回 200"、"Y 页面在 Z 浏览器可渲染"            |
| 用户说"做think里那个方案"           | 步骤 1 先找到对应 think 产出（文件路径 / 链接），提取规格而非重新发问                |
| context_pointers 写了一堆无关路径   | 只列步骤 1 实际检索到的、与任务直接相关的路径                                        |
| 用户跳过确认直接说"直接建吧"        | 仍然展示推荐值让用户逐项确认或一次性批准，不省略共享理解这一步                       |
| 用户抛来 3+ 个不相关需求            | 每个需求独立走一次完整流程，不合并为一个模糊 task                                    |
| 动笔前没查 CLAUDE.md 的硬性规则     | Durable Context Preflight 不是可选的——违反规则的 task 在执行阶段必然被打回           |
| 子任务 scope 跨层（如"前端+后端"）  | 拆分粒度不合格——要求进一步拆到单层单技术                                             |
| 子任务 parent 关系写错位置          | child→parent 归属写 `parent_slug`，`blocked_by` 只放同层前置 task——两者语义不同      |
| 一次抛出 5 个 metadata 问题让用户填 | 2a 是 grilling 方案（一次一问），2b 才用 AskUserQuestion 打包 metadata——不要混淆阶段 |
| 方案讨论停在"大概改一下 X 模块"     | 2a 必须深入到文件路径 + 改动内容粒度，不接受模糊描述                                 |
| 问用户能从代码里回答的问题          | 步骤 1 已经探索过的直接用——2a 只问用户必须做决策的未知项                             |
| AskUserQuestion 选项里没给推荐值    | 每个 Q 的第一个选项必须是 agent 基于 2a 讨论产出的推荐值                             |
| 子任务粒度太大（>5 文件）还不拆     | 步骤 4a 拆分粒度自检——超过 5 文件或 1 个服务的子任务必须进一步拆                     |
| 同批 batch 内写跨任务 blocked_by    | `batch_create_tasks` 同批内禁止跨任务 `blocked_by`（slug 尚未分配，必然失败）——先批量创建再走步骤 4d 用 `update_dev_task` 补依赖 |
| 子任务之间隐含顺序但没加 blocked_by | 串行依赖必须用 `blocked_by` 显式声明                                                 |
