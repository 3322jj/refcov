"""任务 13 试验钩子：记下 PreToolUse 收到的输入，命令文本里有标记词时用退出码 2 拦住。

由 .kiro/hooks/trial-shell-match.json 调用（匹配 ^control_pwsh_process$），用完由用户删掉钩子文件。
记录写进同目录的 hook-input.jsonl，非 ASCII 字符转义。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

raw = sys.stdin.buffer.read()
payload = raw.decode("utf-8", errors="replace")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

try:
    data = json.loads(payload)
except ValueError:
    data = {"unparsed": payload}

tool_input = data.get("tool_input") if isinstance(data, dict) else None
command = tool_input.get("command") if isinstance(tool_input, dict) else None
block = isinstance(command, str) and "REFCOV_TRIAL_BLOCK" in command

out = Path(__file__).with_name("hook-input.jsonl")
with open(out, "a", encoding="utf-8", newline="\n") as f:
    f.write(json.dumps({"time": datetime.now().astimezone().isoformat(timespec="seconds"),
                        "blocked": block, "payload": data}, ensure_ascii=True) + "\n")

if block:
    print("试验钩子：命令里有 REFCOV_TRIAL_BLOCK，按退出码 2 拦下（任务 13）", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
