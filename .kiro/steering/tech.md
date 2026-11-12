---
inclusion: always
---

# 技术约定

EN summary: Python 3.11+ on Windows; CI runs the tests on Linux and Windows. The core uses only the standard library; only the MCP server module depends on the official `mcp` SDK, and ffmpeg/geopandas stay inside their apps. Hook scripts block only with exit code 2 and a reason on stderr, match exact tool names, and judge only by `tool_input.path` or the command text. On internal errors they allow, except the state/config protection checks, which block. Hook scripts read stdin as bytes, decode UTF-8, force UTF-8 output, and escape text before logging. Dependent agent operations (edit then test, commit then push, push retries) are sent one at a time, each after the previous result is back.

## agent 操作顺序

- **有先后的操作必须分开发出，一次只发一个。** 先等上一个的结果，再发下一个。包括：改文件 → 跑测试；`git commit` → `git push`；`push` 失败后的重试。
- 同一批发出的工具调用不保证按顺序执行，测试可能跑在改动之前，push 可能跑在 commit 之前。

依据：`docs/DEVLOG.md` 2026-11-12（任务 8 里同批发出出了 4 次）。

## 语言和依赖

- Python 3.11 及以上，在 Windows 上运行；持续集成在 Linux 和 Windows 上跑测试（需求 13.5；Windows 作业 2026-11-12 任务 8 加）。
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
- 脚本自身出错时放行（退出码 0），错误写进状态目录的日志，不写到 stdout。例外：保护状态目录和配置的检查里，脚本内部异常一律按拦截处理（退出码 2）。解释器启动失败（Python 没装、语法错误）时退出码不是 2，拦不住，这一条写在局限里（需求 11.4、14.5）。

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
