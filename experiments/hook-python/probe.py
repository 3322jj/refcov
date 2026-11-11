"""试验：钩子进程里跑的是哪个 python、当前目录是哪里（任务 6 第 8 点）。只写本目录的 logs/probe.jsonl，一律退出码 0。

从 stdin 只取 hook_event_name、tool_name 两项，不存 tool_response，不写 .refcov/。用完由用户把钩子文件挪出 .kiro/hooks/。
"""
import json
import os
import sys
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent / "logs" / "probe.jsonl"


def main():
    raw = sys.stdin.buffer.read()
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
        data = data if isinstance(data, dict) else {}
    except Exception:
        data = {}
    entry = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        # 工具名对不上时正式钩子静默跳过，和"没触发"分不出来，所以记下这两项（不记 tool_response）
        "hook_event_name": data.get("hook_event_name"),
        "tool_name": data.get("tool_name"),
        "executable": sys.executable,
        "version": sys.version,
        "cwd": os.getcwd(),
        "path_head": os.environ.get("PATH", "").split(os.pathsep)[:5],
        "pid": os.getpid(),
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
