"""测试用：用 ffmpeg 的合成源现场生成测试视频，不把任何视频提交进仓库（镜头应用需求 7.2）。"""

import shutil
import subprocess

import pytest

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="没有 ffmpeg 或 ffprobe（PATH 上找不到）")

COLORS = {"red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255)}


def run(args, **kw):
    if "input" not in kw:
        kw["stdin"] = subprocess.DEVNULL
    return subprocess.run(args, capture_output=True, timeout=120, **kw)


def make_video(path, colors=("red", "lime", "blue"), seconds=2, size="320x240"):  # ffmpeg 的 green 是 (0,128,0)，lime 才是纯绿
    """把几段纯色接成一个视频，每段 `seconds` 秒，切点在 seconds、2*seconds……（都是硬切）。"""
    n = len(colors)
    args = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
    for c in colors:
        args += ["-f", "lavfi", "-i", f"color=c={c}:s={size}:d={seconds}:r=25"]
    graph = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    for codec in ("libx264", "mpeg4"):
        res = run([*args, "-filter_complex", graph, "-map", "[v]", "-c:v", codec, "-pix_fmt", "yuv420p",
                   "-g", "25", str(path)])
        if res.returncode == 0:
            return path
    raise RuntimeError(f"合成视频失败：{res.stderr.decode('utf-8', 'replace')[:300]}")


def jpeg_width(data: bytes) -> int:
    """读 JPEG 的宽度（找 SOF 段）。不是 JPEG 时抛 ValueError。"""
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("不是 JPEG")
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7:i + 9], "big")
        i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    raise ValueError("没找到 SOF 段")


def center_pixel(jpeg: bytes):
    """用 ffmpeg 解码 JPEG，返回正中间一个像素的 (R, G, B)（纯色画面，取中间 2x2 的第一个像素）。"""
    res = run(["ffmpeg", "-nostdin", "-v", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-i", "pipe:0",
               "-frames:v", "1", "-vf", "crop=2:2:(iw-2)/2:(ih-2)/2", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "pipe:1"], input=jpeg)
    assert res.returncode == 0 and len(res.stdout) == 12, res.stderr
    return tuple(res.stdout[:3])
