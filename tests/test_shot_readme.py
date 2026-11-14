"""README 和实现不脱节（镜头应用任务 7，需求 1.8–1.10、6.2）：README 里写的命令名和参数在代码里都存在，局限都写了。"""

import re
from pathlib import Path

import pytest

import shot_loader

REPO = Path(__file__).resolve().parents[1]
README = (REPO / "apps" / "shot-coverage" / "README.md").read_text(encoding="utf-8")
cli = shot_loader.load_cli()


def commands_and_flags():
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if a.choices and hasattr(a.choices, "items"))
    flags = {c: {o for a in p._actions for o in a.option_strings if o.startswith("--")} for c, p in sub.choices.items()}
    return set(sub.choices), flags


def test_readme_commands_exist():
    """README 里出现的 `cli.py <子命令>` 都是真的子命令，三个子命令都写了。"""
    commands, _ = commands_and_flags()
    used = set(re.findall(r"cli\.py (\w+)", README))
    assert used <= commands and commands == {"detect", "count", "page"} <= used


def test_readme_options_exist():
    """README 里 `cli.py` 命令行和说明里写的 `--选项` 都是真的（`refcov add` 的 `--id`、`--adapter` 另查）。"""
    _, flags = commands_and_flags()
    known = set().union(*flags.values()) | {"--id", "--adapter", "--help"}
    written = set(re.findall(r"`(--[a-z-]+)`", README)) | set(re.findall(r"\s(--[a-z-]+)", README))
    assert written <= known, sorted(written - known)
    assert {"--out", "--threshold", "--min-shot", "--scale", "--video-path", "--json"} <= written
    for flag in ("--id", "--adapter"):  # 核心层的登记命令
        assert f'"{flag}"' in (REPO / "refcov" / "cli.py").read_text(encoding="utf-8")


def test_readme_default_values_match_the_code():
    adapter = shot_loader.load()
    assert f"default {adapter.DEFAULT_THRESHOLD}" in README
    assert f"default {adapter.DEFAULT_MIN_SHOT} seconds" in README


@pytest.mark.parametrize("phrase", [
    "Hard cuts only",                                        # 需求 1.8：只切硬切
    "One keyframe per shot",                                  # 需求 1.8：一镜头一张关键帧
    "not the same as having seen every frame",               # 需求 1.8
    "ordinary code",                                          # 需求 1.9：适配器文件是普通代码
    "`kinds`",                                                # 需求 1.9：改 kinds 能缩小必看集合
    "deliberate tampering",                                   # 需求 1.9：不防蓄意伪造
    "size and modification time",                             # 需求 3.4 的局限
    "runs inside RefCov's own process",                       # 设计 6
    "Not a power",                                            # 需求 6.2
    "No speed or cost claim",                                 # 没测出来不说
])
def test_readme_states_the_limitations(phrase):
    assert phrase in README


def test_readme_claims_nothing_the_trial_has_not_shown():
    """"更快、更省"要等视频对比试验的结果；README 不得出现这类断言（没测出来不说）。"""
    lowered = README.lower()
    for claim in ("saves credits", "guarantees", "cannot be bypassed", "prevents the ai from"):
        assert claim not in lowered, claim
    for sentence in re.split(r"(?<=[.!?])\s+", README):
        if re.search(r"\b(faster|cheaper)\b( or (faster|cheaper))? than\b", sentence.lower()):
            assert "not been measured" in sentence, sentence  # 只能是"还没测"这种说明
