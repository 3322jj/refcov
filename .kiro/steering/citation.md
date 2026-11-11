---
inclusion: fileMatch
fileMatchPattern: ".kiro/specs/**"
---

# 需求出处写法（草案）

EN summary: Draft citation format for requirements. Requirements cite units as `[ref:<source-id>/<unit-id>]`, usually on a `出处：` (source) line; a requirement block with no valid reference anywhere is a phantom requirement, and a reference to a missing source or unit is an invalid reference; in strict mode either one fails the check. Unit IDs come from headings: CJK kept, runs of whitespace, square brackets and `@` become one hyphen, `-2`, `-3` for duplicate headings (compared case-insensitively, skipping every heading's own ID; a unit named after the file gets its ID last), `@2`, `@3` for parts of an over-long section. User instructions given in chat are saved under `docs/decisions/` and cited like any other unit.

> 状态：**草案**。格式按设计文档 `.kiro/specs/refcov-skeleton/design.md` 第 4 节定下，实现时如有改动同步改这里。对应需求 6.1。

## 写法

每条需求在验收标准之后、下一条需求之前，单独写一行出处：

```markdown
出处：[ref:kiro-hooks/exit-codes] [ref:rules/repository]
```

- 一个引用写成 `[ref:<参考源ID>/<单元ID>]`，多个引用用空格隔开。
- 参考源 ID 是登记参考源时起的短名（小写字母、数字、短横线）。
- 单条验收标准有专门出处时，可以在该条末尾直接写引用，例如 `… SHALL 用退出码 2 拦截。[ref:kiro-hooks/exit-codes]`。
- 出处标到需求级就够：一条需求块里任何位置有一个有效引用，就不是幻影需求。
- 需求块里一个有效引用都没有的需求，算幻影需求。
- 引用的参考源或单元不存在，算无效引用。
- 严格模式下，有幻影需求或无效引用就不达标；轻量模式下只在报告里列出（需求 6.6）。写规格文件本身不因此被拦，否则补不了出处（需求 6.7）。

## 单元 ID 怎么来

由单元标题生成（需求 2.5，设计第 4 节）：

1. 把连续的空白、`[`、`]`、`@` 换成一个 `-`，去掉首尾的 `-`。其余字符原样保留，含中日韩文字和大小写。结果为空时用 `section`。
2. 同一参考源里标题重名，第二个起加 `-2`、`-3`……，还重名就继续往后数。空号要避开所有标题自己的 ID，所以本身不重名的标题 ID 不会因为别处多了重名章节而变。查重不区分大小写，ID 保留原来的大小写（设计第 4 节第 2 条）。第一个标题之前那段用文件名当标题，它最后分 ID，和真标题撞了就由它加后缀，例如 `hooks.md` 里 `# Hooks` 是 `Hooks`、开头那段是 `hooks-2`（设计第 4 节第 5 条）。
3. 超过 4000 个字符的章节拆成几段：第一段沿用原 ID；后面的标题是"原标题 (2)"，ID 是原 ID 加 `@2`、`@3`……。标题生成的 ID 里没有 `@`，所以拆分出的 ID 不会和重名的 ID 撞。

例子：`退出码`、`退出码-2`（第二个叫"退出码"的章节）、`退出码@2`（第一个"退出码"章节超长拆出的第二段）。单元 ID 不含空白和方括号，单元标题不限。

## 用户在聊天里给的要求

- 每次回复存成 `docs/decisions/` 下的一个 Markdown 文件，一条意见一个小标题，登记成参考源，按普通单元引用，不另设出处类型（需求 6.1）。
- 这些文件进公开仓库，**存之前先给用户过目**。用户确认后在终端跑 `refcov confirm <文件>`；没确认或确认后改过的，报告里标红"待用户确认"。
- `docs/decisions/**` 默认豁免关卡（需求 8.3）。

## 检查程序怎么认

- "一条需求"= 以 `### 需求 N：` 开头，到下一个 `### ` 或文件结尾为止。
- 引用用正则 `\[ref:([a-z0-9-]+)/([^\]\s]+)\]` 提取。单元 ID 部分 `[^\]\s]+` 能匹配 `@`，拆分出的 `退出码@2` 照样认。
- tasks.md 里任务的子项也用同样写法引用单元；`_需求：1.1_` 照旧写需求编号。

## 过渡期

骨架做好之前，需求文档的出处是文字描述（"交接说明·核心功能 1""第二稿审阅第 6 条"等）。骨架做好后：

- 交接说明、比赛规则页、Kiro 文档登记为参考源，按章节拆单元。Kiro 文档登记 `.md` 地址（例如 `https://kiro.dev/docs/hooks.md`）。
- 用户的审阅回复存成 `docs/decisions/` 下的文件后登记（见上一节）。
- 文字出处逐条改成 `[ref:…]`，改完前检查程序把文字出处报为"未转换"，不算幻影需求。

## 待定问题

1. ~~单元 ID 用短名还是序号？~~ 已定：用标题生成的短名（外部审阅 A8，用户 2026-11-10 同意）。
2. ~~一条需求只标到需求级，还是每条验收标准都要标？~~ 已定：需求级（设计第 4 节第 7 条）。
3. ~~用户口头回复算不算单元？~~ 已定：存成 `docs/decisions/` 下的文件，按普通单元引用。
