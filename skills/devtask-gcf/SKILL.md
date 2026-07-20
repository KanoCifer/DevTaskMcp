---
name: devtask-gcf
description: Generate concise with Conventional Commits format
argument-hint: [c(commit)|p(push)]
allowed-tools: Bash(git *), AskUserQuestion
disable-model-invocation: true
---

**从对话上下文或暂存区中了解本次变更的内容和意图**

## 行为模式

- `c`：message → commit
- `p`：message → commit → push
- 默认：展示 preview 后用 `AskUserQuestion` 工具询问：提交 / 提交并推送 / 取消

## Commit Message

**标题**：`<type>(<scope>): <imperative summary>`

- Type：`feat` / `fix` / `refactor` / `perf` / `chore` ...
- Scope：单模块用目录名

**正文**：仅必要时：breaking change、非显而易见的 why、`Closes #42`

**禁止**：AI 署名、emoji

## 输出格式

严格按此输出，禁止额外信息：

```
提交预览 (Committing to <branch>)

提交信息:
<type>(<scope>): <summary>

  <body line>

变更文件:
• <relative-path>    (+N/-N)
```
