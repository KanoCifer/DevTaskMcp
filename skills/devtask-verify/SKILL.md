---
name: devtask-verify
description: '对照实际代码和运行时行为验证 dev-task 的验收条件。当用户说"verify task-N"、"check task-42"、"does task-7 pass?"、"验收 task-N"、"task 验收通过了吗"、"这个 spec 完了吗"，或询问某任务的验收条件是否满足时使用。对 parent task（kind=spec）会自动递归验证所有子任务。与 /devtask-doit（执行任务）和 /devtask-plan（创建任务）配套。对于没有 task slug 的通用代码变更验证，请用内置的 /verify。'
argument-hint: [task slug to verify, e.g. task-N]
---

# devtask-verify

**关键词：verify。** 给定一个 task slug，从任务板上拉取规格，然后逐条检查验收条件是否在实际代码和运行时行为中成立。产出每条条件的通过/失败报告并附证据（命令输出、diff、运行时输出）。不修改代码——这是一次只读检查。

**Parent task 递归验证。** 如果被验证的是 parent spec（`kind=spec`），会自动递归验证所有子任务，并将 parent 的验收条件（"所有子任务 verify 通过"）作为聚合结论。

## Preflight

执行前先做连通性检查：调一次 `list_dev_tasks` 看是否连通。如果返回错误或异常，告知用户 MCP server 不可用，中止验证。

## 步骤

### 步骤 1：拉取任务 + 检测层级

调用 `get_dev_task_by_slug` 拉取任务详情 —— 若为子任务一并拿到嵌套的 parent spec 数据（含 acceptance_criteria / context_pointers），后续递归验证子任务时无需再单独查 parent。**slug 格式预检**：slug 形如 `task-N`，格式不对直接告知用户。如果 slug 解析不到，通过 `get_frontier_tasks` 列一下 frontier 并建议一个任务。

拿到任务后判断层级（检查 kind / parent_slug / 嵌套 parent 字段）：

- **`kind == "spec"`** → **Parent spec**：需要递归验证所有子任务
- **`kind == "subtask"` + `parent_slug` 非空** → 归属在某 spec 下的子任务，标准逐条验证
- **`kind == "subtask"` + `parent_slug` 为空** → 独立原子任务，标准逐条验证

如果是 parent spec，通过 `list_children` 一次性获取全部子任务（走后端 parent_slug 索引查询，返回完整 task 对象无需再次按 slug 拉取）。

**Completion criterion:** 手上有任务的完整 spec（含 kind / parent_slug）+ 层级判定结果；parent 已获取完整子任务列表。

### 步骤 2：解析验收条件

把 `acceptance_criteria` 拆成单条。该字段是自由文本——常见格式有编号列表、清单项（`- ...` / `* ...`）、或一行一条。如果字段为空或缺失，停下来告知用户没有可验证的内容。

对每条条件，分类其验证方式：

- **子任务完成类（parent 特有）** — `- [ ] task-N1: ... verify 通过`：这是人读摘要，**不解析 AC 文本获取 slug**。Parent 的子任务发现唯一权威来源是步骤 1 已通过 `list_children` 拿到的完整列表。本条 ⇔ 子任务自己的 acceptance_criteria 递归验证后**全部 ✅**。
- **代码检查** — "函数 X 返回 Y"、"文件 Z 包含..." → 读文件、grep 匹配。
- **运行时 / 行为** — "server 返回 200"、"CLI 输出..." → 执行命令并捕获输出。
- **Diff / git** — "新增了对...的测试"、"删除了废弃的..." → 检查 `git diff` 或 `git log`。

**Completion criterion:** 条件列表，每条都标注了验证方式；parent 的子任务列表已在步骤 1 通过 `list_children` 获取，无需从 AC 文本解析。

### 步骤 3：读上下文

按 `context_pointers` 读相关源码。不靠记忆——读实际文件。如果某条条件引用了 `context_pointers` 没覆盖的代码，也读一下。

**Completion criterion:** 所有条件涉及的代码都已读过。

### 步骤 4：逐条验证

对每条条件执行对应检查：

- **子任务完成类（parent 特有）：** 步骤 1 已通过 `list_children` 拿到所有子任务的完整 spec（含 acceptance_criteria、context_pointers、parent_slug），**权威来源唯一，不从 AC 文本解析 slug**。直接逐条验证每条子任务的验收条件（无需再次按 slug 拉取）。子任务全部 ✅ → 本条 ✅；任一 ❌ → 本条 ❌；有 ❉ → 本条标记 ❉（"有条件通过"）。证据引用子报告的结论。
- **代码检查：** 读文件，确认模式存在（或不存在）。捕获相关行号作为证据。
- **运行时：** 按 task 的 context_pointers / constraints 启动对应服务（不绑项目特定命令），发请求，断言期望响应。捕获 stdout/stderr/退出码。
- **Diff / git：** `git diff <since>..HEAD` 或 `git log --oneline <since>..HEAD`。先用 `detail` 字段里记录的执行时间戳锚定范围，没有再用 `updated_at`。

记录通过/失败及具体证据（file:line、命令输出、diff 片段）。如果某条条件有歧义，标记为 **❉** 而不是猜——让用户澄清。

**Completion criterion:** 每条条件都有 ✅/❌/❉ 结论并附证据；parent 的所有子任务已完成独立验证。

### 步骤 5：报告

**子任务 / 原子 task**——标准报告：

```
## 验证：<slug> — <title>

板上状态：<status>
条件：共 <N> 条，<P> 通过，<F> 失败，<U> 不明确

| # | 条件 | 结论 | 证据 |
|---|------|------|------|
| 1 | <文本> | ✅/❌/❉ | <file:line 或输出片段> |
...

### 总结
- **通过：** 所有条件都是 ✅。
- **失败：** 有条件是 ❌ — 列出还需要做什么。
```

**Parent task**——层级报告：

```
## 验证：<slug> — <title>（Spec）

板上状态：<status>
子任务：<N> 个，<M> 已通过验证，<K> 待修复

### 子任务概览
| slug | title | 条件数 | 通过 | 失败 | 结论 |
|------|-------|--------|------|------|------|
| task-N1 | ... | 3 | 3 | 0 | ✅ |
| task-N2 | ... | 2 | 1 | 1 | ❌ |
| task-N3 | ... | 4 | 4 | 0 | ✅ |

### 子任务详情
（每个子任务的标准验证表，按上方格式逐条展开）

### 总结
- **Spec 通过：** 所有子任务 ✅。
- **Spec 有条件通过：** 所有子任务验证完成，但有 ❉ 不明确项 — 请用户澄清后重验。
- **Spec 有条件失败：** task-N2 的 `<具体条件>` 未通过 — 建议用 devtask-doit 技能修复。
- **Spec 整体状态：** <M>/<N> 子任务完成。
```

**不要修改任务状态。** 如果全部通过且任务还不是 `已完成`，建议用 devtask-doit 技能收尾。如果有失败的，按失败条件建议下一步。

**Completion criterion:** 用户看到带证据的逐条结论表。

## 失败处理

- **任务找不到：** 告知用户，提供 frontier 列表。
- **无 acceptance_criteria：** 告知用户该任务没有可验证的内容；建议编辑任务补上验收条件。
- **运行时检查无法执行**（如没有 API key、server 起不来）：\*\* 把该条标记为 ❉ 并记录原因；不要伪造通过。
- **条件是主观的**（"看起来不错"、"感觉快"）：标记为 ❉，请用户把它改写成可度量的表述。
- **Parent 的子任务找不到：** 如果 `list_children` 返回空，告知用户子任务可能未正确关联，建议检查子任务的 `parent_slug` 字段是否指向该 parent。
- **子任务状态不是 `已完成`：** 仍然执行验证（可用于执行中途检查进度），但在报告显著位置注明该子任务板上状态，提醒用户未完成时结论仅反映当前代码快照。
- **AC 引用文件/路径不存在：** 标记 ❌ 并记录"目标不存在"——区别于主观 ❉。

## 何时用、何时不用（补充）

- **使用场景：** 验证父 spec 是否端到端完成（所有子任务 AC 过 → spec 过）。
- **使用场景：** 执行中途在把状态翻到 `已完成` 之前自测。
- **使用场景：** 接收别人的 task 前先独立确认条件成立。
- **不使用：** 任务状态是 `进行中` 且你想知道"做完了没"——进行中代码快照不完整，结论不可靠；建议等 doit 完成后再验。
- **不使用：** 任务没有 `acceptance_criteria`——没有可验证的内容，直接告知用户。
- **不使用：** 没有绑定 task slug 的 generic 代码变更——用内置的 `/verify`。

