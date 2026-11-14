"""核心层和 MCP 服务不出现 Kiro 专有的名字，也不依赖 Hypothesis（任务 12，需求 13.1、13.4；tech.md）。

Kiro 的工具名、事件名、`.kiro` 路径只能出现在接入层 integrations/kiro/ 里。按文本搜，注释和文档字符串也算。
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CORE_DIRS = ("refcov", "refcov_mcp")

KIRO_NAMES = (
    # 工具名（docs/验证结果.md、hooks/*.json 的匹配条件）
    "fs_write", "str_replace", "fs_append", "execute_pwsh", "control_pwsh_process", "execute_bash", "mcp_refcov_",
    # 事件名
    "PreToolUse", "PostToolUse", "UserPromptSubmit", "PreTaskExec", "PostTaskExec",
    "PostFileSave", "PostFileCreate", "PostFileDelete", "SessionStart",
    # 路径
    ".kiro",
)
# 应用和它们的依赖只出现在各自的应用里（需求 2.6、13.4；tech.md：ffmpeg 只在 apps/shot-coverage，
# geopandas 只在 apps/layer-coverage）。核心层按配置里的路径加载适配器，源码里不写任何具体应用的名字。
APP_NAMES = ("ffmpeg", "ffprobe", "geopandas", "shot-coverage", "shot_coverage", "layer-coverage", "layer_coverage")
_HYPOTHESIS_IMPORT = re.compile(r"^\s*(import|from)\s+hypothesis\b", re.MULTILINE)


def _files():
    out = sorted(p for d in CORE_DIRS for p in (REPO / d).rglob("*.py"))
    assert out, "没找到核心层的源文件"
    return out


@pytest.mark.parametrize("path", _files(), ids=lambda p: p.relative_to(REPO).as_posix())
def test_no_kiro_names_and_no_hypothesis(path):
    text = path.read_text(encoding="utf-8")
    found = [n for n in KIRO_NAMES if n.lower() in text.lower()]
    assert not found, f"{path.relative_to(REPO).as_posix()} 里出现了 Kiro 的名字：{found}"
    assert not _HYPOTHESIS_IMPORT.search(text), f"{path.relative_to(REPO).as_posix()} import 了 hypothesis"
    apps = [n for n in APP_NAMES if n.lower() in text.lower()]
    assert not apps, f"{path.relative_to(REPO).as_posix()} 里出现了应用或应用依赖的名字：{apps}"


def test_the_app_name_check_catches_a_planted_name(tmp_path):
    """性质 13.1：检查本身有效。往一份核心层源码的副本里放 `import ffmpeg` 或应用名，名字检查应当报出来。"""
    for planted in ("import ffmpeg\n", "# see apps/shot-coverage/adapter.py\n", "import geopandas\n"):
        text = (REPO / "refcov" / "sources.py").read_text(encoding="utf-8") + planted
        assert [n for n in APP_NAMES if n.lower() in text.lower()], planted
