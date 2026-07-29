---
name: devtask-gcf
description: "Generate concise commit messages in Conventional Commits format. Use when committing changes, creating a commit, writing a commit message, or when the user says 'commit this' or 'create a commit'."
argument-hint: [c(commit)|p(push)]
allowed-tools: Bash(git *), AskUserQuestion
---

**从对话上下文或暂存区中了解本次变更的内容和意图**

## 行为模式

- $ARGUMENTS == `c`：message → commit
- $ARGUMENTS == `p`：message → commit → push
- 默认：展示 preview 后用 `AskUserQuestion` 工具询问：提交 / 提交并推送 / 取消

## 前置检查

- `git status` 确认有变更；无变更则告知用户并终止
- `git diff --staged` 为空但 `git diff` 非空 → 询问是否 stage 全部改动
- 无 staged 文件且无 unstaged 文件 → 终止

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

## Rules

- **无变更不提交** — 工作区干净时终止，不创建空 commit
- **stage 确认** — 有未 staged 改动时先询问，不自动 `git add`
- **不修改代码** — 本 skill 只负责 commit/push，不改动任何文件
