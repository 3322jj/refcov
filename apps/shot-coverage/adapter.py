"""镜头适配器（镜头应用设计第 2、3 节）：把"镜头清单"拆成 `shot` 单元，读一个镜头时返回文字加一张关键帧。

**一个自带依赖的文件**：核心层按配置 `[adapters]` 里写的路径加载它，加载时不改 `sys.path`，所以这里只能 import
标准库和 `refcov`（`refcov/adapters/loader.py` 的约定）。`cli.py` 和测试也经这个文件用同样的函数。

**导入时不做任何耗时的事**（设计 3.1.1）：写文件关卡的每次检查都会经 `api._decls` 加载它。所以模块顶层只放
import、常量、类和函数定义；调 ffmpeg、查 PATH、算哈希、读视频和清单都只在函数体里，且只在 `read`、`detect`
被调用时才发生。`tests/test_shot_adapter_import.py` 守着这一条。

时间在内部一律用整数"十分之一秒"（`t`），清单里写成一位小数；首尾相接因此是整数相等，不靠浮点比较。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from refcov.sources import KindDecl, Unit

name = "shot"
kinds = {"shot": KindDecl(strict=True, key=False)}  # 需求 1.6：严格必看，没有关键类型

REQUIRED_KEYS = ("video", "sha256", "size", "mtime_ns", "duration", "threshold", "min_shot", "shots")
OPTIONAL_KEYS = ("detect_scale",)
MAX_SHOTS_HINT = 300  # 需求 1.7：镜头数多于这个数时 detect 提示
_TENTH = re.compile(r"\d+\.\d")
_SHA = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Header:
    """镜头清单的文件头（设计 2）。`duration_t` 是时长，单位十分之一秒。"""

    video: str  # 相对仓库根目录、用 `/`；仓库外的视频写绝对路径
    sha256: str
    size: int
    mtime_ns: int
    duration_t: int
    threshold: float
    min_shot: float
    scale: int | None = None  # 检测前缩小到的行高；没缩小就是 None（清单里不写这一项）


# ---- 单元 ID 和时间 ----

def shot_id(t: int) -> str:
    """起点 `t`（十分之一秒）生成的镜头 ID：`shot-<分>-<秒>-<十分之一秒>`（需求 1.3）。"""
    return f"shot-{t // 600:02d}-{t // 10 % 60:02d}-{t % 10}"


def fmt_t(t: int) -> str:
    """十分之一秒写成一位小数的秒，例如 38 → "3.8"。"""
    return f"{t // 10}.{t % 10}"


def _parse_t(text: str, what: str) -> int:
    if not _TENTH.fullmatch(text):
        raise ValueError(f"{what} 要写成一位小数的秒，例如 3.8，现在是 {text!r}")
    whole, tenth = text.split(".")
    return int(whole) * 10 + int(tenth)


# ---- 边界处理（纯函数，设计 4 第 4 步）----

def build_shots(cuts, duration: float, min_shot: float) -> list[tuple[int, int]]:
    """把切点（秒）变成首尾相接的镜头 `[(起点, 终点)]`，单位十分之一秒。

    切点和时长先四舍五入到 0.1 秒；去重，去掉 0 和终点上（以及之外）的点；从前往后，凡是会让镜头比 `min_shot`
    还短的切点都去掉（并入前一个）；最后一个镜头如果还是太短，就并入倒数第二个。保证：首尾相接、覆盖
    `[0, 时长]`、每个镜头不短于 `min_shot`（整段视频本身比 `min_shot` 短时是唯一的一个镜头）、
    除 0 以外的起点都来自输入的切点。
    """
    total = round(duration * 10)
    if total <= 0:
        raise ValueError(f"视频时长要大于 0：{duration}")
    shortest = max(1, math.ceil(round(min_shot * 10, 6)))
    kept = [0]
    for p in sorted({round(c * 10) for c in cuts}):
        if 0 < p < total and p - kept[-1] >= shortest:
            kept.append(p)
    if len(kept) > 1 and total - kept[-1] < shortest:
        kept.pop()
    return list(zip(kept, kept[1:] + [total]))


# ---- 镜头清单：写和读（设计 2）----

def format_list(h: Header, shots: list[tuple[int, int]]) -> str:
    """写镜头清单。UTF-8、换行 `\\n`。"""
    if "\n" in h.video or "\r" in h.video:
        raise ValueError("视频路径里不能有换行")
    lines = [f"# {h.video.rsplit('/', 1)[-1]} shots", "",
             f"video: {h.video}", f"sha256: {h.sha256}", f"size: {h.size}", f"mtime_ns: {h.mtime_ns}",
             f"duration: {fmt_t(h.duration_t)}", f"threshold: {float(h.threshold)!r}",
             f"min_shot: {float(h.min_shot)!r}"]
    if h.scale is not None:
        lines.append(f"detect_scale: {h.scale}")
    lines += [f"shots: {len(shots)}", ""]
    for s, e in shots:
        lines += [f"## {shot_id(s)}", f"start: {fmt_t(s)}", f"end: {fmt_t(e)}", ""]
    return "\n".join(lines)


def _int(values: dict, key: str, minimum: int = 0) -> int:
    try:
        n = int(values[key])
    except ValueError:
        raise ValueError(f"文件头 {key} 要是整数，现在是 {values[key]!r}") from None
    if n < minimum:
        raise ValueError(f"文件头 {key} 不能小于 {minimum}：{n}")
    return n


def _float(values: dict, key: str) -> float:
    try:
        x = float(values[key])
    except ValueError:
        raise ValueError(f"文件头 {key} 要是数，现在是 {values[key]!r}") from None
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f"文件头 {key} 要大于 0：{values[key]!r}")
    return x


def _parse_header(lines: list[str]) -> tuple[Header, int]:
    values: dict[str, str] = {}
    for line in lines:
        if not line.strip() or line.startswith("# "):
            continue
        key, sep, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if not sep or key not in REQUIRED_KEYS + OPTIONAL_KEYS:
            raise ValueError(f"文件头里有看不懂的一行：{line!r}")
        if key in values:
            raise ValueError(f"文件头里 {key} 写了两次")
        values[key] = val
    missing = [k for k in REQUIRED_KEYS if k not in values]
    if missing:
        raise ValueError(f"文件头缺少：{'、'.join(missing)}")
    if not values["video"]:
        raise ValueError("文件头 video 不能为空")
    if not _SHA.fullmatch(values["sha256"]):
        raise ValueError("文件头 sha256 要是 64 位小写十六进制")
    threshold = _float(values, "threshold")
    if threshold > 1:
        raise ValueError(f"文件头 threshold 要在 0 到 1 之间：{threshold}")
    header = Header(values["video"], values["sha256"], _int(values, "size"), _int(values, "mtime_ns"),
                    _parse_t(values["duration"], "文件头 duration"), threshold, _float(values, "min_shot"),
                    _int(values, "detect_scale", 1) if "detect_scale" in values else None)
    if header.duration_t <= 0:
        raise ValueError("文件头 duration 要大于 0")
    return header, _int(values, "shots", 1)


def parse_list(text: str) -> tuple[Header, list[tuple[int, int]]]:
    """严格读镜头清单，返回 (文件头, [(起点, 终点)])。不合格抛 `ValueError`（设计 2）。

    检查：文件头键齐全且格式对；`shots` 等于小节数；第一个镜头从 0.0 开始；每个镜头的起点等于上一个的终点；
    最后一个镜头的终点等于 `duration`；每个小节的 ID 等于由起点生成的 ID；终点大于起点。
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    first = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
    header, count = _parse_header(lines[:first])
    sections: list[tuple[str, dict[str, str]]] = []
    for line in lines[first:]:
        if line.startswith("## "):
            sections.append((line[3:].strip(), {}))
        elif line.strip():
            key, sep, val = line.partition(":")
            body = sections[-1][1]
            if not sep or key.strip() not in ("start", "end") or key.strip() in body:
                raise ValueError(f"镜头小节 {sections[-1][0]} 里有看不懂的一行：{line!r}")
            body[key.strip()] = val.strip()
    shots, prev_end = [], 0
    for sid, body in sections:
        if set(body) != {"start", "end"}:
            raise ValueError(f"镜头小节 {sid} 要有 start 和 end 两行")
        s, e = _parse_t(body["start"], f"{sid} 的 start"), _parse_t(body["end"], f"{sid} 的 end")
        if sid != shot_id(s):
            raise ValueError(f"镜头小节标题 {sid} 和起点 {body['start']} 对不上（应是 {shot_id(s)}）")
        if s != prev_end:
            raise ValueError(f"镜头 {sid} 的起点 {body['start']} 不等于上一个镜头的终点 {fmt_t(prev_end)}"
                             "（有空隙或重叠）")
        if e <= s:
            raise ValueError(f"镜头 {sid} 的终点要大于起点")
        shots.append((s, e))
        prev_end = e
    if len(shots) != count:
        raise ValueError(f"文件头 shots 是 {count}，实际有 {len(shots)} 个镜头小节")
    if prev_end != header.duration_t:
        raise ValueError(f"最后一个镜头的终点 {fmt_t(prev_end)} 不等于文件头 duration {fmt_t(header.duration_t)}")
    return header, shots


def unit_text(h: Header, s: int, e: int) -> str:
    """单元的 `text`：**不是给 AI 看的内容，而是校验值的输入**（设计 3.1，需求 3.1）。

    视频的 SHA-256、起止时间、检测参数任一个变了，核心层算出的单元校验值就变，旧读取记录自然失效。
    """
    text = (f"video-sha256={h.sha256}\nstart={fmt_t(s)}\nend={fmt_t(e)}\n"
            f"threshold={float(h.threshold)!r}\nmin_shot={float(h.min_shot)!r}\n")
    return text + (f"detect_scale={h.scale}\n" if h.scale is not None else "")


# ---- 适配器接口（骨架需求 2.1）----

def split(data: bytes, file_name: str) -> list[Unit]:
    """把镜头清单拆成 `shot` 单元；清单不合格时抛 `ValueError`（登记因此被拒绝，什么都不写）。"""
    header, shots = parse_list(data.decode("utf-8-sig"))
    return [Unit(shot_id(s), shot_id(s), "shot", unit_text(header, s, e)) for s, e in shots]


def facts(data: bytes, file_name: str, unit_id: str) -> dict:
    """这个镜头可核对的事实：序号、总数、起止、时长、视频的 SHA-256。单元不存在时抛 `KeyError`。"""
    header, shots = parse_list(data.decode("utf-8-sig"))
    for i, (s, e) in enumerate(shots, start=1):
        if shot_id(s) == unit_id:
            return {"index": i, "of": len(shots), "start": s / 10, "end": e / 10, "duration": (e - s) / 10,
                    "video_sha256": header.sha256}
    raise KeyError(unit_id)


def read(data: bytes, file_name: str, unit_id: str):
    raise NotImplementedError("read 在任务 2 里实现")
