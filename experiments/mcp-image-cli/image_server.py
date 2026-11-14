"""试验用 MCP 服务（只用标准库，stdio）：检验图片经 MCP 工具返回后，Kiro CLI 里的模型能不能真的看到。

照 kirohe 里 IDE 验证用的 image_server.py 重写，改成英文颜色名，并加了 count 参数
（返回 1 或 2 张图，对应以后镜头单元的"首尾各一张"）。不是正式的 RefCov MCP 服务。

工具 get_test_image 返回一段文字和 count 张 3x3 色块 PNG，每格颜色随机。
正确答案只写进 --answer-log 指定的文件（放在被测工作区之外），不出现在工具返回的文字里。
用法：python image_server.py --answer-log <答案日志路径>
"""
import argparse
import base64
import datetime
import json
import random
import struct
import sys
import zlib
from pathlib import Path

PALETTE = {
    "red": (220, 30, 30),
    "green": (30, 170, 50),
    "blue": (30, 60, 220),
    "yellow": (240, 220, 20),
    "black": (0, 0, 0),
    "white": (255, 255, 255),
}


def make_png(grid, cell=100):
    """grid: 3x3 的颜色名列表，生成 PNG 字节。"""
    n = len(grid)
    size = n * cell
    rows = []
    for y in range(size):
        row = bytearray([0])  # 每行开头的 filter 字节
        for x in range(size):
            row.extend(PALETTE[grid[y // cell][x // cell]])
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


TOOLS = [{
    "name": "get_test_image",
    "description": ("Returns a test picture (PNG): a 3x3 grid of coloured squares. "
                    "count (1 or 2, default 1) is the number of pictures returned."),
    "inputSchema": {
        "type": "object",
        "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 2}},
    },
}]


def send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answer-log", required=True)
    answer_log = Path(ap.parse_args().answer_log)
    answer_log.parent.mkdir(parents=True, exist_ok=True)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

    def log(entry):
        entry = {"time": datetime.datetime.now().isoformat(timespec="seconds"), **entry}
        with answer_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def handle(req):
        method = req.get("method")
        if method == "initialize":
            version = (req.get("params") or {}).get("protocolVersion", "2025-06-18")
            return {"protocolVersion": version, "capabilities": {"tools": {}},
                    "serverInfo": {"name": "image-probe", "version": "0.0.1"}}
        if method == "tools/list":
            return {"tools": TOOLS}
        if method == "tools/call":
            args = (req.get("params") or {}).get("arguments") or {}
            count = args.get("count", 1)
            count = count if count in (1, 2) else 1
            grids = [[[random.choice(list(PALETTE)) for _ in range(3)] for _ in range(3)]
                     for _ in range(count)]
            log({"event": "call", "args": args, "grids": grids})
            content = [{"type": "text", "text": f"{count} test picture(s) follow. The answer is not in this text."}]
            for grid in grids:
                content.append({"type": "image", "mimeType": "image/png",
                                "data": base64.b64encode(make_png(grid)).decode()})
            return {"content": content}
        if method == "ping":
            return {}
        raise ValueError(f"unknown method {method}")

    log({"event": "start"})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        if "id" not in req:  # 通知，不回
            continue
        try:
            send({"jsonrpc": "2.0", "id": req["id"], "result": handle(req)})
        except Exception as e:
            send({"jsonrpc": "2.0", "id": req["id"], "error": {"code": -32601, "message": str(e)}})


if __name__ == "__main__":
    main()
