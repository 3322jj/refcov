"""Kiro 接入层的钩子脚本（设计 8）。一个脚本，按第一个参数分派事件。

用法：python integrations/kiro/hook.py <事件>
- post-mcp：RefCov MCP 工具的 PostToolUse，按返回文字最后一行的调用编号补记会话（需求 4.5，任务 6）。
- prompt：UserPromptSubmit，把一行简短报告写到 stdout（需求 9.8，任务 7）。用户消息全文不读、不记。

规矩（tech.md、需求 11.1、11.3）：
- stdin 按字节读，UTF-8 解码；stdout、stderr 改成 UTF-8。
- 仓库根目录按这个文件的位置算（integrations/kiro/hook.py 往上两级），放到 sys.path 最前面，不依赖当前目录。
- 这个分支任何异常都放行：退出码 0，原因写进 .refcov/errors.log（json.dumps(..., ensure_ascii=True)），不写 stdout。
  不写 tool_response 原文（里面是参考材料正文）。
"""

import json
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ERRORS_LOG = ROOT / ".refcov" / "errors.log"
MCP_TOOL = re.compile(r"^mcp_refcov_")  # 和 hooks/refcov-post-mcp.json 的 matcher 一致（需求 9.5）


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
