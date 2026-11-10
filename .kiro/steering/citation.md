---
inclusion: fileMatch
fileMatchPattern: ".kiro/specs/**"
---

# 需求出处写法（草案）

EN summary: Draft citation format for requirements. Each requirement ends with a `出处：` (source) line of `[ref:<source-id>/<unit-id>]` references; a single criterion may carry its own inline reference. Unit IDs are generated from headings (CJK kept, whitespace and square brackets replaced by hyphens, `-2`, `-3` on collisions). A requirement with no valid reference is a phantom requirement; a reference to a missing source or unit is an invalid reference; in strict mode either one fails the check. User instructions given in chat are saved under `docs/decisions/` and cited like any other unit.

> 状态：**草案**。设计阶段定稿，定稿前格式可能改。对应需求 6.1。

## 写法

每条需求在验收标准之后、下一条需求之前，单独写一行出处：

```markdown
出处：[ref:kiro-hooks/exit-codes] [ref:rules/repository]
```

- 一个引用写成 `[ref:<参考源ID>/<单元ID>]`，多个引用用空格隔开。
- 参考源 ID 是登记参考源时起的短名（小写字母、数字、短横线）。
- 单元 ID 由单元标题生成（需求 2.5）：保留原文字，含中日韩文字；空白和方括号换成短横线；重名时依次加 `-2`、`-3`。超长章节拆出的后几段，标题是"原标题 (2)"，ID 是原 ID 加 `-2`（需求 3.5）。单元 ID 不含空白和方括号，单元标题不限。
- 单条验收标准有专门出处时，可以在该条末尾直接写引用，例如 `… SHALL 用退出码 2 拦截。[ref:kiro-hooks/exit-codes]`。
- 没有 `出处：` 行、或 `出处：` 行里一个有效引用都没有的需求，算幻影需求。
- 引用的参考源或单元不存在，算无效引用。
- 严格模式下，有幻影需求或无效引用就不达标；轻量模式下只在报告里列出（需求 6.6）。写规格文件本身不因此被拦，否则补不了出处（需求 6.7）。

## 用户在聊天里给的要求

- 每次回复存成 `docs/decisions/` 下的一个 Markdown 文件，一条意见一个小标题，登记成参考源，按普通单元引用，不另设出处类型（需求 6.1）。
- 这些文件进公开仓库，**存之前先给用户过目**。
- `docs/decisions/**` 默认豁免关卡（需求 8.3）。

## 检查程序怎么认

- "一条需求"= 以 `### 需求 N：` 开头，到下一个 `### ` 或文件结尾为止。
- 引用用正则 `\[ref:([a-z0-9-]+)/([^\]\s]+)\]` 提取。
- tasks.md 里任务的子项也用同样写法引用单元；`_需求：1.1_` 照旧写需求编号。

## 过渡期

骨架做好之前，需求文档的出处是文字描述（"交接说明·核心功能 1""第二稿审阅第 6 条"等）。骨架做好后：

- 交接说明、比赛规则页、Kiro 文档登记为参考源，按章节拆单元。Kiro 文档登记 `.md` 地址（例如 `https://kiro.dev/docs/hooks.md`）。
- 用户的审阅回复存成 `docs/decisions/` 下的文件后登记（见上一节）。
- 文字出处逐条改成 `[ref:…]`，改完前检查程序把文字出处报为"未转换"，不算幻影需求。

## 待定问题

1. ~~单元 ID 用短名还是序号？~~ 已定：用标题生成的短名（外部审阅 A8，用户 2026-11-10 同意）。
2. 一条需求只标到需求级就够，还是每条验收标准都要标？
3. ~~用户口头回复算不算单元？~~ 已定：存成 `docs/decisions/` 下的文件，按普通单元引用。
