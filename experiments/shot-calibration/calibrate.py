"""检测前缩小的校准（镜头应用设计 4 第 3 步，任务 3）：比较"缩小到 N 行高"和"不缩小"两种做法，
看抓到的切点和仓库外的标准答案对得上多少，以及用时。

用法：python calibrate.py --video <视频> --key <标准答案 json> [--scales 360,540,0] [--threshold 0.25]

标准答案文件（仓库外，D:\\agent\\kiro\\refcov-trial-grader\\video_key.json）只读 `hard_cuts[*].t`（硬切）和
`scene_changes`（原先用全分辨率跑的场景检测）；这个脚本不读、不打印画面文字。视频是 EP01 的隔离副本，
里面有真实公司名字，脚本只输出时间点和数字。
"""

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ADAPTER = Path(__file__).resolve().parents[2] / "apps" / "shot-coverage" / "adapter.py"
TOLERANCE = 0.5  # 秒：切点和标准答案的硬切相差不超过这个数算对上（和判分口径一致）


def load_adapter():
    spec = importlib.util.spec_from_file_location("shot_adapter_calibration", ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def near(t, points, tol=TOLERANCE):
    return any(abs(t - p) <= tol for p in points)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--scales", default="360,0", help="逗号分隔的行高；0 是不缩小")
    ap.add_argument("--threshold", type=float, default=0.25)
    a = ap.parse_args()
    shot = load_adapter()
    key = json.loads(Path(a.key).read_text(encoding="utf-8"))
    hard = [c["t"] for c in key["hard_cuts"]]
    reference = list(key.get("scene_changes", []))
    reference = [x["t"] if isinstance(x, dict) else x for x in reference]
    video = Path(a.video)
    print(f"标准答案：硬切 {len(hard)} 处，原先的场景检测 {len(reference)} 个点；阈值 {a.threshold}，容差 {TOLERANCE} 秒")
    for scale in [int(s) for s in a.scales.split(",")]:
        t0 = time.monotonic()
        cuts = shot.detect_cuts(video, a.threshold, scale or None)
        secs = time.monotonic() - t0
        found = [h for h in hard if near(h, cuts)]
        missed = [h for h in hard if not near(h, cuts)]
        extra = [c for c in cuts if not near(c, hard)]
        shots = shot.build_shots(cuts, shot.probe_duration(video), shot.DEFAULT_MIN_SHOT)
        print(f"\n缩小到 {scale or '不缩小'}：用时 {secs:.1f} 秒，抓到 {len(cuts)} 个切点，"
              f"生成 {len(shots)} 个镜头（最短 {shot.DEFAULT_MIN_SHOT} 秒）")
        print(f"  硬切找到 {len(found)}/{len(hard)}；漏掉 {[round(m, 2) for m in missed]}")
        print(f"  多出的点（不在标准答案的硬切附近）{len(extra)} 个：{[round(x, 2) for x in extra]}")
        if reference:
            same = [r for r in reference if near(r, cuts)]
            print(f"  和原先全分辨率场景检测的 {len(reference)} 个点比：对上 {len(same)} 个")


if __name__ == "__main__":
    main()
