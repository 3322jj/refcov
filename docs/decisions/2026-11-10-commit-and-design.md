# 2026-11-10 提交、历史和进入设计

用户在第 4 步实测之后的回复。用户过目后定稿。

## 改写历史

旧提交里的邮箱由用户自己处理，agent 不管。之后定为：不改写历史，不强制推送，在 DEVLOG 记一句。

## 提交哪些文件

提交 README.md、language.md、外部审阅、`experiments/` 和改过的文件。`.kiro/settings/mcp.json` 不提交，也不写进 `.gitignore`（比赛规则禁止忽略 `.kiro` 及其子文件夹），写进 `.git/info/exclude`，另提交 `docs/mcp.example.json`（路径用占位符）。

## 试验钩子

把 `.kiro/hooks/` 下的 4 个试验钩子挪进 `experiments/mcp-posttooluse/hooks-disabled/`，不要删。

## 存 decisions

把用户的回复整理成 `docs/decisions/` 下的文件，先给用户看，看过再提交。这一项不挡后面的事。

## 需求冻结，开始设计

需求冻结，开始骨架设计，写 `.kiro/specs/refcov-skeleton/design.md`：

- 模块不超过 8 个，每个写清做什么、对应哪几条需求。
- 读取记录、参考源清单、凭证、配置文件、报告 JSON，各给一个例子。
- MCP 工具不超过 6 个，列出名字、输入、输出。
- 钩子列出事件、匹配条件、调用核心层哪个入口。
- 定下 citation.md 的待定问题和超长章节的字数。
- 属性测试怎么生成数据，对应需求 16。
- 先做审阅 D1 说的最细通路：登记 Markdown → 拆单元 → 经 MCP 读 → 记录 → 报告。关卡放在后面。

写完让 spec-auditor 审一遍，报告附在最后，停下给用户看。需求有问题只记进 DEVLOG"以后再做"，不改需求。
