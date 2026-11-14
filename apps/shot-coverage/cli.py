"""镜头覆盖率应用的命令行（镜头应用设计第 4、5 节）：`detect`、`count`、`page`。

在仓库根目录运行（和 `refcov` 一样：当前目录下要有 `.git`）：

    python apps/shot-coverage/cli.py detect <视频> [--out <清单>] [--threshold 0.25] [--min-shot 0.5]
                                              [--scale N] [--video-path <写进清单的视频路径>]

只用标准库和 `refcov`；ffmpeg 和 ffprobe 只在 `adapter.py` 里被调用。
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录的 adapter.py、page.py

import adapter  # noqa: E402
from refcov.store import sha256_file  # noqa: E402


def _repo_root() -> Path | None:
    """当前目录下有 `.git` 时返回当前目录，否则返回 None（和 `refcov` 一样，不往上找）。"""
    cwd = Path.cwd()
    return cwd if (cwd / ".git").exists() else None


def _inside(path: Path, root: Path) -> bool:
    return Path(os.path.normcase(path)).is_relative_to(os.path.normcase(root))


def _fail(msg: str) -> int:
    print(msg, file=sys.stderr)
    return 1


def detect(args) -> int:
    root = _repo_root()
    if root is None:
        return _fail(f"检测失败：请在仓库根目录运行（{Path.cwd()} 下没有 .git）")
    video = Path(os.path.abspath(args.video))
    if not video.is_file():
        return _fail(f"检测失败：找不到视频文件 {args.video}")
    root = root.resolve()
    video = video.resolve()
    try:
        adapter.find_tool("ffmpeg")
        adapter.find_tool("ffprobe")
        duration = adapter.probe_duration(video)
        if round(duration * 10) <= 0:
            return _fail("检测失败：视频时长读出来是 0")
        st = video.stat()
        sha = sha256_file(video)
        scale = args.scale or None
        cuts = adapter.detect_cuts(video, args.threshold, scale)
        shots = adapter.build_shots(cuts, duration, args.min_shot)
    except (adapter.ShotError, ValueError, OSError) as e:
        return _fail(f"检测失败：{e}")
    if args.video_path:
        shown = args.video_path
    else:
        shown = video.relative_to(root).as_posix() if _inside(video, root) else video.as_posix()
    if args.out:
        out = Path(os.path.abspath(args.out))
    else:  # 视频在仓库里：放在视频旁边；不在：放在仓库根目录（清单必须在仓库里，登记才收）
        out = (video.parent if _inside(video, root) else root) / f"{video.stem}.shots.md"
    if not _inside(Path(os.path.abspath(out)), root):
        return _fail(f"检测失败：清单要放在仓库里（{out} 不在 {root} 下），否则登记会被拒绝")
    header = adapter.Header(shown, sha, st.st_size, st.st_mtime_ns, round(duration * 10), args.threshold,
                            args.min_shot, scale)
    try:
        text = adapter.format_list(header, shots)
        adapter.parse_list(text)  # 写之前自己再读一遍，保证写出去的清单登记时一定收得下
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".tmp")
        tmp.write_bytes(text.encode("utf-8"))
        os.replace(tmp, out)  # 先写临时文件再改名，不留半份
    except (ValueError, OSError) as e:
        return _fail(f"检测失败：{e}")
    rel = out.relative_to(root).as_posix() if _inside(out, root) else out.as_posix()
    print(f"检测完成：{len(shots)} 个镜头，时长 {duration:.1f} 秒，阈值 {args.threshold}，"
          f"最短镜头 {args.min_shot} 秒" + (f"，检测前缩小到 {scale} 行高" if scale else ""))
    print(f"清单：{rel}")
    if len(shots) < 2 or len(shots) > adapter.MAX_SHOTS_HINT:
        print(f"提示：镜头数 {len(shots)} 不太正常（少于 2 或多于 {adapter.MAX_SHOTS_HINT}），检查阈值 {args.threshold}")
    print("下一步：在配置文件的 [adapters] 里声明适配器（只能用户改），然后在终端运行：")
    print(f"  refcov add {rel} --id <参考源ID> --adapter {adapter.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shot-coverage", description="Shot coverage for a reference video.")
    sub = parser.add_subparsers(dest="command")
    d = sub.add_parser("detect", help="用 ffmpeg 场景检测把视频切成镜头，生成镜头清单（只跑一次）")
    d.add_argument("video", help="视频文件")
    d.add_argument("--out", help="清单路径（要在仓库里）；默认放在视频旁边，视频在仓库外时放在仓库根目录")
    d.add_argument("--threshold", type=float, default=adapter.DEFAULT_THRESHOLD, help="场景检测阈值，默认 0.25")
    d.add_argument("--min-shot", type=float, default=adapter.DEFAULT_MIN_SHOT, help="最短镜头时长（秒），默认 0.5")
    d.add_argument("--scale", type=int, default=adapter.DEFAULT_SCALE or 0,
                   help="检测前把画面缩到这个行高再检测；0 是不缩小（默认）。EP01 上缩小没有变快，也没改变结果")
    d.add_argument("--video-path", help="写进清单的视频路径（不改变视频本身）；给对比试验的模板用")
    return parser


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "detect":
        return detect(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
