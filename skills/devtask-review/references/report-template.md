```
## Review: <slug> — <title>

板上状态: <status> → <最终状态（若变动）>
验收条件: 共 N 条，P 通过，F 失败，U 不明确

| # | 条件 | 结论 | 证据 |
|---|------|------|------|
| 1 | ... | ✅/❌/❓ | file:line |

### 清理审查（四视角）
| 视角 | file:line | 修法 | 结论 |
|------|-----------|------|------|
| Reuse | ... | applied: ... | fixed |
| Simplification | ... | 会改行为 | skipped: <reason> |
| Efficiency | ... | applied: ... | fixed |
| Altitude | — | — | clean |

### 正确性 + 安全
- [severity] file:line — 建议（不自动修）

### 子任务概览（parent）
| slug | title | AC | 清理 | 正确性 |
|------|-------|----|------|--------|
| task-N1 | ... | ✅ | clean | — |
```

全 AC 通过 + 清理全 clean → 末尾一句话总结"可以被证成完成"；否则明确 remaining work。
