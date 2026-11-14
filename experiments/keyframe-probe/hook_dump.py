"""试验用钩子：把收到的钩子输入的"形状"记到 hook-dump.jsonl，图片数据只记长度，不记内容。

只为看 PostToolUse 的 tool_response 在带图片时长什么样（镜头应用 C3）。一律退出码 0，不写 stdout。
输出文件在环境变量 KEYFRAME_DUMP 指定的路径，没设置就写到本脚本旁边。
"""
import json
import os
import sys
import time
from pathlib import Path

raw = sys.stdin.buffer.read()
payload = raw.decode("utf-8", errors="replace")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def shape(x, depth=0):
    """递归描述结构：字符串记长度和末行（最多 120 字符），base64 一类长字符串只记长度。"""
    if isinstance(x, str):
        last = x.rsplit("\n", 1)[-1]
        return {"str": len(x), "last_line": last[:120] if len(last) < 200 else "<long line>"}
    if isinstance(x, dict):
        return {k: shape(v, depth + 1) for k, v in x.items()}
    if isinstance(x, list):
        return [shape(v, depth + 1) for v in x]
    return x


try:
    data = json.loads(payload)
    entry = {"time": time.strftime("%H:%M:%S"), "event": data.get("hook_event_name"), "tool_name": data.get("tool_name"),
             "keys": sorted(data), "tool_input": data.get("tool_input"),
             "tool_response_type": type(data.get("tool_response")).__name__,
             "tool_response_shape": shape(data.get("tool_response")), "stdin_bytes": len(raw)}
except Exception as e:  # 试验脚本：记下来，不影响工具
    entry = {"time": time.strftime("%H:%M:%S"), "error": repr(e), "stdin_bytes": len(raw)}
out = Path(os.environ.get("KEYFRAME_DUMP") or Path(__file__).with_name("hook-dump.jsonl"))
with out.open("a", encoding="utf-8") as f:
    f.write(json.dumps(entry, ensure_ascii=True) + "\n")
