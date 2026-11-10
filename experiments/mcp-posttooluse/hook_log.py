"""试验用钩子脚本：把钩子收到的输入原样记到 logs/hooks.jsonl，一律退出码 0。

用法：python experiments/mcp-posttooluse/hook_log.py <钩子名>
"""
import json
import os
import sys
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent / "logs" / "hooks.jsonl"


def main():
    raw = sys.stdin.buffer.read()
    payload = raw.decode("utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        data = json.loads(payload)
    except Exception:
        data = {"unparsed": payload[:2000]}
    resp = data.get("tool_response")
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "hook": sys.argv[1] if len(sys.argv) > 1 else "?",
        "pid": os.getpid(),
        "env_session": os.environ.get("KIRO_SESSION_ID"),
        "session_id": data.get("session_id"),
        "event": data.get("hook_event_name"),
        "tool_name": data.get("tool_name"),
        "tool_input": data.get("tool_input"),
        "file_path": data.get("file_path"),
        "has_tool_response": resp is not None,
        "tool_response": str(resp)[:300] if resp is not None else None,
        "keys": sorted(data.keys()) if isinstance(data, dict) else None,
    }
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
