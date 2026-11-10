"""试验用 MCP 服务（只用标准库，stdio）。

只为第 4 步实测：Kiro 调用 MCP 工具时，PostToolUse 钩子是否每次触发、
输入里有没有准确的会话 ID 和参数。不是正式的 RefCov MCP 服务。

每条收到的消息都记到 logs/server.jsonl（进程号、方法、参数）。
"""
import json
import os
import sys
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent / "logs" / "server.jsonl"
PID = os.getpid()
CALLS = 0


def log(entry):
    entry = {"time": time.strftime("%H:%M:%S"), "pid": PID, **entry}
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except Exception:
        pass


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


TOOL = {
    "name": "read_unit",
    "description": "试验工具：按参考源 ID 和单元 ID 返回一段假内容。note 填你想留在日志里的标记。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "unit": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["source", "unit"],
    },
}


def handle(msg):
    global CALLS
    method = msg.get("method")
    mid = msg.get("id")
    log({"recv": method, "id": mid, "params": msg.get("params")})
    if mid is None:  # 通知，不回
        return
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "refcov-probe", "version": "0.0.1"},
        }})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [TOOL]}})
    elif method == "tools/call":
        CALLS += 1
        args = (msg.get("params") or {}).get("arguments") or {}
        text = (f"试验单元 {args.get('source')}/{args.get('unit')}："
                f"服务进程 {PID} 的第 {CALLS} 次调用。")
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "content": [{"type": "text", "text": text}], "isError": False}})
    elif method == "ping":
        send({"jsonrpc": "2.0", "id": mid, "result": {}})
    else:
        send({"jsonrpc": "2.0", "id": mid,
              "error": {"code": -32601, "message": f"method not found: {method}"}})


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    log({"event": "start", "argv": sys.argv})
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except Exception as e:  # 试验服务：记下来，不退出
            log({"error": repr(e), "line": line[:500]})


if __name__ == "__main__":
    main()
