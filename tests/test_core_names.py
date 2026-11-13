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
