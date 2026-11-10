---
inclusion: always
---

# 技术约定

## 语言和依赖

- Python 3.11 及以上，Windows 和 Linux 都要能跑。
- **核心层只用标准库**：单元模型、读取记录、覆盖率、出处检查、凭证、文档适配器都不引第三方包。
- MCP 服务放单独模块，用官方 SDK（`mcp` 包）。运行时只有这个模块依赖第三方包。
- ffmpeg 只在 `apps/shot-coverage` 里用，geopandas 只在 `apps/layer-coverage` 里用。核心层和接入层不得 import 它们，也不得假设它们已安装。
- 开发依赖：Hypothesis（属性测试）、pytest。
- 核心层不出现 Kiro 专有的工具名、事件名或路径。Kiro 相关的东西只放在接入层。

## 钩子脚本

- **拦截只用退出码 2，原因写 stderr。** 退出码 1 不拦，agent 也收不到原因（实测）。
- PreToolUse 退出码 0 时的 stdout 到不了 agent。只有 UserPromptSubmit（和 SessionStart）的 stdout 会进上下文。
- 匹配条件写精确工具名：`fs_write`、`str_replace`、`fs_append`、shell 工具名。不用 `write` 这类类别名。
- 关卡只按 `tool_input.path`（或命令文本）判断，不在整段输入里搜关键词。
- 脚本自身出错时放行（退出码 0），错误写进状态目录的日志，不写到 stdout。例外：保护状态目录和配置的检查出错时拦截。

## Windows 编码

钩子脚本开头固定这样处理：

```python
import sys

raw = sys.stdin.buffer.read()                 # 按字节读
payload = raw.decode("utf-8", errors="replace")
sys.stdout.reconfigure(encoding="utf-8")      # 输出强制 UTF-8
sys.stderr.reconfigure(encoding="utf-8")
```

写日志前先转义特殊字符（例如用 `json.dumps(..., ensure_ascii=True)`），环境变量里的坏字符曾让脚本崩掉。

依据：`docs/验证结果.md` 第 1–3 项，`docs/DEVLOG.md` 2026-11-10。
