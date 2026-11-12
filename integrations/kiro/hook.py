"""Kiro 接入层的钩子脚本（设计 8）。一个脚本，按第一个参数分派事件。

用法：python integrations/kiro/hook.py <事件>
- post-mcp：RefCov MCP 工具的 PostToolUse，按返回文字最后一行的调用编号补记会话（需求 4.5，任务 6）。
- prompt：UserPromptSubmit，把一行简短报告写到 stdout（需求 9.8，任务 7）。用户消息全文不读、不记。
- pre-write、pre-shell：PreToolUse 的保护检查（需求 14，任务 14）。不 import 核心层；命中就退出码 2、
  原因写 stderr；这一步出任何异常也退出码 2。拦下后才 import 核心层追加 protect 记录，失败就算了。
  逃生办法：用户把 .kiro/hooks/refcov-pre-write.json 和 refcov-pre-shell.json 移出 .kiro/hooks/，立即停用。

规矩（tech.md、需求 11.1、11.3），post-mcp 和 prompt 适用：
- stdin 按字节读，UTF-8 解码；stdout、stderr 改成 UTF-8。
- 仓库根目录按这个文件的位置算（integrations/kiro/hook.py 往上两级），放到 sys.path 最前面，不依赖当前目录。
- 这个分支任何异常都放行：退出码 0，原因写进 .refcov/errors.log（json.dumps(..., ensure_ascii=True)），不写 stdout。
  不写 tool_response 原文（里面是参考材料正文）。
"""

import json
import os
import posixpath
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ERRORS_LOG = ROOT / ".refcov" / "errors.log"
MCP_TOOL = re.compile(r"^mcp_refcov_")  # 和 hooks/refcov-post-mcp.json 的 matcher 一致（需求 9.5）

# ---- 保护检查（任务 14，需求 14.1–14.5，设计 8 第 2 步）：不 import 核心层 ----

USER_ONLY = ("add", "confirm")  # 和 refcov/cli.py 的 USER_ONLY 一致（tests/test_protect.py 检查）
WRITE_TOOLS = frozenset({"fs_write", "str_replace", "fs_append"})  # 和 hooks/refcov-pre-write.json 一致
SHELL_TOOLS = frozenset({"execute_pwsh", "control_pwsh_process", "execute_bash"})  # 和 hooks/refcov-pre-shell.json 一致
_I = re.IGNORECASE
# 都是对整段命令文本的匹配，不分大小写。换写法（拼接字符串、用 py 启动等）能绕过（需求 11.4 的局限）。
SHELL_RULES = (
    (re.compile(r"\.refcov", _I), "命令里出现了状态目录 .refcov"),
    (re.compile(r"refcov\.toml", _I), "命令里出现了配置文件 refcov.toml"),
    # 用户 2026-11-12 定：挪走、删掉、看钩子目录都由用户做（偏离需求原文，需求 11.4 没有这一条）
    (re.compile(r"\.kiro[\\/]+hooks", _I), "命令里出现了钩子目录 .kiro/hooks"),
    # 用 Python 运行钩子脚本。python 后面紧跟 -m、-c 时不算（`python -m refcov check …/hook.py` 是只读检查），
    # 文件名必须正好是 hook.py（`tests/test_hook.py` 不算）
    (re.compile(r"(^|[\s;&|(])python3?(\.exe)?(\s+-(?!m\b|c\b)\S+)*\s+[\"']?(\S*[/\\])?hook\.py\b", _I),
     "命令在运行钩子脚本"),
    (re.compile(r"-m\s+refcov_mcp\b", _I), "命令在运行 RefCov 的 MCP 服务"),
    (re.compile(r"(^|[\s;&|(])(refcov(\.exe)?|python3?(\.exe)?\s+-m\s+refcov)\s+(" + "|".join(USER_ONLY) + r")\b", _I),
     "命令是只能由用户在终端跑的 refcov 子命令"),
)
_PROTECT_TAIL = ("AI 不能改状态目录、配置和钩子，也不能替用户登记或确认（需求 14）。看记录用 RefCov 的 MCP 工具 report。"
                 "不要换写法绕过；需要做这件事就停下来告诉用户。")


def _rel(path: str) -> str:
    """相对仓库根目录、`/` 分隔、小写的路径（Windows 上路径不分大小写）。"""
    p = path.replace("\\", "/")
    if os.path.isabs(p) or re.match(r"^[A-Za-z]:", p):
        try:
            p = os.path.relpath(p, str(ROOT))
        except ValueError:  # 不在同一个盘
            return posixpath.normpath(p).lower()
    return posixpath.normpath(p.replace("\\", "/")).lower()


def protect_reason(data: dict) -> str | None:
    """需要拦时返回原因，放行返回 None。认不出输入时抛异常，由调用方按拦截处理（需求 14.5）。

    写文件工具只看 `tool_input.path`；shell 工具只看 `tool_input.command`（`null` 当空字符串，
    control_pwsh_process 的 stop 就是这样，docs/验证结果.md 第 7 项）。其他工具不管。
    """
    tool = data.get("tool_name")
    if tool in WRITE_TOOLS:
        path = data["tool_input"]["path"]
        if not isinstance(path, str):
            raise TypeError("tool_input.path 不是字符串")
        rel = _rel(path)
        if rel == ".refcov" or rel.startswith(".refcov/"):
            return f"RefCov 保护：不能写状态目录 .refcov/ 下的文件（{path}）。{_PROTECT_TAIL}"
        if rel == "refcov.toml":
            return f"RefCov 保护：不能写配置文件 refcov.toml，配置只能由用户改。{_PROTECT_TAIL}"
        return None
    if tool in SHELL_TOOLS:
        tool_input = data["tool_input"]
        if not isinstance(tool_input, dict):
            raise TypeError("tool_input 不是对象")
        command = tool_input.get("command")
        if command is None:
            command = ""
        if not isinstance(command, str):
            raise TypeError("tool_input.command 不是字符串")
        for rx, why in SHELL_RULES:
            if rx.search(command):
                return f"RefCov 保护：{why}。{_PROTECT_TAIL}"
        return None
    return None


def _record_protect(data: dict, reason: str) -> None:
    """拦下后追加一条 protect 记录（需求 14.3）。核心层加载失败、拿不到锁时只写过 stderr，不再做别的。"""
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from refcov.store import Store

        tool = data.get("tool_name") if isinstance(data.get("tool_name"), str) else None
        ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
        if tool in WRITE_TOOLS:
            kind, target = "write", ti.get("path")
        elif tool in SHELL_TOOLS:
            kind, target = "shell", ti.get("command")
        else:
            kind, target = "unknown", None
        session = data.get("session_id") if isinstance(data.get("session_id"), str) else None
        Store(ROOT).append("protect", session, kind=kind, tool=tool,
                           target=target[:300] if isinstance(target, str) else None, reason=reason[:300])
    except Exception:
        pass


def protect_main(event: str) -> int:
    """pre-write、pre-shell：先做保护检查。拦就退出码 2、原因写 stderr；这一步任何异常也退出码 2（需求 14.5）。"""
    data: dict = {}
    try:
        raw = sys.stdin.buffer.read()
        payload = raw.decode("utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise TypeError("钩子输入不是 JSON 对象")
        data = parsed
        reason = protect_reason(data)
    except Exception as e:
        reason = (f"RefCov 保护：钩子脚本认不出这次输入（{type(e).__name__}），按需求 14.5 一律拦下。"
                  "反复出现时请用户把 .kiro/hooks/refcov-pre-write.json 和 refcov-pre-shell.json 移出 .kiro/hooks/，"
                  "保护立即停用。")
        log_error(event, "保护检查认不出输入", e)
    if reason is None:
        return gate_write(data, event) if event == "pre-write" else 0
    try:
        sys.stderr.write(reason + "\n")
        sys.stderr.flush()
    except Exception:
        pass
    _record_protect(data, reason)
    return 2


def gate_write(data: dict, event: str) -> int:
    """写文件关卡（任务 15，需求 9.1、11.2、17.1）：保护检查放行之后才做。只按 tool_input.path 判断。

    和保护检查相反，这一步出任何错都放行（需求 11.1）：退出码 0，原因写 errors.log，stdout、stderr 不写。
    不达标时由核心层追加 block 记录，这里把原因写 stderr、退出码 2。enforce = false 时核心层直接放行。
    """
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from refcov import api
        from refcov.store import Store

        session = data.get("session_id") if isinstance(data.get("session_id"), str) and data.get("session_id") else None
        res = api.check_write(Store(ROOT), data["tool_input"]["path"], session)
    except Exception as e:
        log_error(event, "写文件关卡出错，放行", e, tool_name=data.get("tool_name"))
        return 0
    if res["allow"]:
        return 0
    try:
        sys.stderr.write(res["reason"] + "\n")
        sys.stderr.flush()
    except Exception:
        pass
    return 2


def log_error(event: str, reason: str, exc: BaseException | None = None, **extra) -> None:
    """往 errors.log 追加一行 JSON（全部转义成 ASCII）。写不进去也不抛。"""
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, "reason": reason, **extra}
    if exc is not None:
        entry["error"] = type(exc).__name__
        entry["traceback"] = "".join(traceback.format_exception(exc))[-2000:]
    try:
        ERRORS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ERRORS_LOG, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except Exception:
        pass


def _block_text(block) -> str | None:
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        if isinstance(block.get("content"), list):
            return response_text(block["content"])
        if isinstance(block.get("text"), str) and block.get("type", "text") == "text":
            return block["text"]
    return None


def response_text(resp) -> str | None:
    """从 tool_response 取出全部文字。字符串原样返回；对象取 `text` 或 `content` 里的文字块；
    列表按顺序把各块的文字用换行连起来。认不出文字时返回 None。"""
    if isinstance(resp, list):
        parts = [t for t in (_block_text(b) for b in resp) if t is not None]
        return "\n".join(parts) if parts else None
    return _block_text(resp)


def post_mcp(data: dict) -> None:
    from refcov import api
    from refcov.store import Store

    if data.get("hook_event_name") != "PostToolUse":
        return
    tool = data.get("tool_name")
    if not isinstance(tool, str) or not MCP_TOOL.match(tool):
        return
    text = response_text(data.get("tool_response"))
    if text is None:
        log_error("post-mcp", "tool_response 里认不出文字", tool_name=tool,
                  response_type=type(data.get("tool_response")).__name__)
        return
    call = api.call_from_text(text)
    if call is None:
        return  # list_units、出错的 read_unit 没有调用编号，属于正常情况
    session = data.get("session_id")
    if not isinstance(session, str) or not session:
        log_error("post-mcp", "钩子输入里没有 session_id", tool_name=tool, call=call)
        return
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    source = ti.get("source") if isinstance(ti.get("source"), str) else None
    unit = ti.get("unit") if isinstance(ti.get("unit"), str) else None
    try:
        api.attach_session(Store(ROOT), call, session, source, unit)
    except api.AttachError as e:
        log_error("post-mcp", str(e), tool_name=tool, call=call)


def prompt(data: dict) -> str | None:
    """UserPromptSubmit：返回一行简短报告（需求 9.8），由 main 在成功后写 stdout，进 AI 的上下文。

    data["prompt"] 是用户消息全文，不读、不记。出错时由 main 记 errors.log，stdout 什么都不写。
    """
    from refcov import api
    from refcov.store import Store

    if data.get("hook_event_name") != "UserPromptSubmit":
        return None
    session = data.get("session_id") if isinstance(data.get("session_id"), str) and data.get("session_id") else None
    return api.status_line(Store(ROOT), session)


HANDLERS = {"post-mcp": post_mcp, "prompt": prompt}


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    if event in ("pre-write", "pre-shell"):
        return protect_main(event)  # 出错一律拦，和下面"出错放行"相反（需求 14.5）
    try:
        raw = sys.stdin.buffer.read()
        payload = raw.decode("utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        handler = HANDLERS.get(event)
        if handler is None:
            log_error(event, "不认识的事件参数")
            return 0
        data = json.loads(payload)
        if not isinstance(data, dict):
            log_error(event, "钩子输入不是 JSON 对象")
            return 0
        out = handler(data)
    except Exception as e:  # 出错放行（需求 11.1），stdout 什么都不写
        log_error(event, "钩子脚本出错", e)
        return 0
    if out:  # 只有分支整个跑完才写 stdout，出错的半截文字进不了上下文
        try:
            sys.stdout.write(out + "\n")
            sys.stdout.flush()
        except Exception as e:
            log_error(event, "写 stdout 失败", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
