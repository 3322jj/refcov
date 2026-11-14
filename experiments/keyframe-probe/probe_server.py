"""真实关键帧试验服务（镜头应用 C1–C3 做完后的实测，验证结果第 10 项）。

用真实的 `refcov.api.read` 和 `refcov_mcp` 服务，只把"适配器"换成一个试验适配器：
拆分沿用文档适配器（一个镜头一节），`read` 按节里的起止时间用 ffmpeg 从视频中点取一帧，
缩小到不超过 960 像素宽的 JPEG，和一行文字一起返回。C4（按名字选适配器）还没做，所以用启动时替换
`api._adapter` 的办法接进去；这不是镜头适配器，只是为了用真实图片测通路。

用法：python probe_server.py --video <视频> --workdir <工作仓库目录> --shots 0:3.84,3.84:6.59,...
工作仓库目录（仓库外）里会建 .git 目录、docs/ep01.shots.md，并用文档适配器登记成参考源 ep01。
每次取帧的字节数记到 <工作目录>/frames.log。视频里有真实公司名字，取出的帧不进公开仓库。
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from refcov import api  # noqa: E402
from refcov.adapters import markdown  # noqa: E402
from refcov.sources import Image, register  # noqa: E402
from refcov.store import Store  # noqa: E402
from refcov_mcp.server import main  # noqa: E402

WIDTH = 960
START_END = re.compile(r"start:\s*([\d.]+)\s*\nend:\s*([\d.]+)")


def shot_id(start: float) -> str:
    tenths = round(start * 10)
    return f"shot-{tenths // 600:02d}-{tenths // 10 % 60:02d}-{tenths % 10}"


def write_list(path: Path, shots: list[tuple[float, float]]) -> None:
    lines = ["# EP01 probe shot list", ""]
    for s, e in shots:
        lines += [f"## {shot_id(s)}", f"start: {s:.1f}", f"end: {e:.1f}", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def make_adapter(video: Path, log: Path, total: int):
    def extract(t: float) -> bytes:
        # -nostdin 和 stdin=DEVNULL：服务的标准输入是 MCP 协议管道，ffmpeg 不能去读它。
        # 第一次实测没加，同一个视频的第 5 个镜头两次超时 120 秒（单独跑同样的命令只要 0.7 秒）。
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
               "-vf", f"scale='min({WIDTH},iw)':-2", "-q:v", "4", "-f", "image2pipe", "-c:v", "mjpeg", "-"]
        res = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        if res.returncode != 0 or not res.stdout:
            raise RuntimeError(f"ffmpeg 取帧失败：{res.stderr.decode('utf-8', 'replace')[:300]}")
        return res.stdout

    class Adapter:
        name = markdown.name
        kinds = markdown.kinds
        split = staticmethod(markdown.split)
        facts = staticmethod(markdown.facts)

        def read(self, data, name, unit_id):
            unit = next(u for u in markdown.split(data, name) if u.id == unit_id)
            m = START_END.search(unit.text)
            if not m:
                return [unit.text]
            s, e = float(m[1]), float(m[2])
            t0 = time.monotonic()
            jpeg = extract((s + e) / 2)
            with log.open("a", encoding="utf-8") as f:
                f.write(f"{unit_id}\tmid={(s + e) / 2:.2f}\tbytes={len(jpeg)}\tffmpeg_s={time.monotonic() - t0:.2f}\n")
            return [f"{unit_id}: {s:.1f}-{e:.1f} s ({e - s:.1f} s), one of {total} shots. Keyframe taken at the middle.",
                    Image(jpeg, "image/jpeg")]

    return Adapter()


def parse_shots(text: str) -> list[tuple[float, float]]:
    return [tuple(float(x) for x in pair.split(":")) for pair in text.split(",")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--shots", required=True)
    a = ap.parse_args()
    work, shots = Path(a.workdir), parse_shots(a.shots)
    (work / ".git").mkdir(parents=True, exist_ok=True)
    write_list(work / "docs" / "ep01.shots.md", shots)
    register(Store(work), "docs/ep01.shots.md", "ep01")
    adapter = make_adapter(Path(a.video), work / "frames.log", len(shots))
    api._adapter = lambda store, name: adapter
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main(["--root", str(work)]))
