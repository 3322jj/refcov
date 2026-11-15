"""`integrations/kiro/setup.py` 和钩子的 `--root`（简化上手设计 2）。setup 在临时仓库里用子进程运行。"""

import importlib.util
import json
import os
import string
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

RC = Path(__file__).resolve().parents[1]  # RefCov 的目录
SETUP = RC / "integrations" / "kiro" / "setup.py"
HOOK = RC / "integrations" / "kiro" / "hook.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SETUP_MOD = _load("refcov_setup_under_test", SETUP)
HOOK_MOD = _load("refcov_hook_under_test", HOOK)

# 路径里要有中文、空格和方括号（测试约定：生成数据包含这些字符）
PATHTEXT = st.text(alphabet=string.ascii_letters + string.digits + " 中文[]()-_.", min_size=1, max_size=20)
EVENT = st.text(alphabet=string.ascii_lowercase + "-", min_size=1, max_size=12)


@given(PATHTEXT, PATHTEXT, EVENT)
def test_hook_command_keeps_the_event_last(py, root, event):
    """性质 U2：改写后的钩子命令以事件名结尾；前缀换成带引号的解释器和脚本路径，`--root` 紧跟其后。"""
    template = "python integrations/kiro/hook.py " + event
    cmd = SETUP_MOD.hook_command(template, py, "H:/x/hook.py", root)
    assert cmd == f'"{py}" "H:/x/hook.py" --root "{root}" {event}'
    assert cmd.endswith(" " + event)


def test_other_commands_are_left_alone():
    """性质 U2 的反面：不以 `python integrations/kiro/hook.py` 开头的命令原样保留。"""
    assert SETUP_MOD.hook_command("echo hi", "p", "h", "r") == "echo hi"


def test_root_option_is_taken_only_before_the_event():
    """性质 U3：`--root <路径>` 取出来，剩下的第一个参数是事件名；没有它或没有值时参数原样保留。"""
    take = HOOK_MOD._take_root
    assert take(["--root", "D:/r", "pre-write"]) == (["pre-write"], "D:/r")
    assert take(["pre-write"]) == (["pre-write"], None)
    assert take(["--root"]) == (["--root"], None)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


def _run(repo: Path, *args):
    return subprocess.run([sys.executable, str(SETUP), *args], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=120)


def _commands(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                yield value
            else:
                yield from _commands(value)
    elif isinstance(node, list):
        for value in node:
            yield from _commands(value)


def _hook_files(repo: Path):
    return sorted((repo / ".kiro" / "hooks").glob("refcov-*.json"))


def test_setup_writes_mcp_hooks_and_config(repo):
    """性质 U1：MCP 配置的解释器和仓库根都是绝对路径；5 个钩子的命令指向 RefCov 的 hook.py 和这个仓库，
    事件名和文件名对得上；refcov.toml 是合法的模板，[sources] 的 files 为空。"""
    res = _run(repo)
    assert res.returncode == 0, res.stderr
    mcp = json.loads((repo / ".kiro/settings/mcp.json").read_text(encoding="utf-8"))["mcpServers"]["refcov"]
    assert mcp["command"] == sys.executable
    assert os.path.samefile(mcp["args"][-1], repo)
    files = _hook_files(repo)
    assert len(files) == 5
    for f in files:
        event = f.stem[len("refcov-"):]
        (cmd,) = list(_commands(json.loads(f.read_text(encoding="utf-8"))))
        assert cmd.startswith(f'"{sys.executable}" "{SETUP_MOD.HOOK}" --root "'), cmd
        assert cmd.endswith(" " + event), cmd
    cfg = tomllib.loads((repo / "refcov.toml").read_text(encoding="utf-8"))
    assert cfg["sources"] == {"files": []}


def test_second_run_does_not_overwrite_without_force(repo):
    """性质 U4：同名文件和 refcov.toml 已存在时，不加 --force 就不覆盖。"""
    assert _run(repo).returncode == 0
    hook = _hook_files(repo)[0]
    hook.write_text("EDITED", encoding="utf-8")
    cfg = repo / "refcov.toml"
    cfg.write_text('mode = "light"\n[sources]\nfiles = ["docs/*.md"]\n', encoding="utf-8")
    res = _run(repo)
    assert res.returncode == 0
    assert "跳过" in res.stdout
    assert hook.read_text(encoding="utf-8") == "EDITED"
    assert "light" in cfg.read_text(encoding="utf-8")


def test_force_overwrites_hooks_and_the_refcov_entry_but_never_the_config(repo):
    """性质 U5：--force 覆盖 5 个钩子文件和 mcpServers.refcov，但 refcov.toml 永远不动。"""
    assert _run(repo).returncode == 0
    hook = _hook_files(repo)[0]
    hook.write_text("EDITED", encoding="utf-8")
    mcp_path = repo / ".kiro/settings/mcp.json"
    mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
    mcp["mcpServers"]["refcov"]["command"] = "old"
    mcp_path.write_text(json.dumps(mcp), encoding="utf-8")
    cfg = repo / "refcov.toml"
    cfg.write_text('mode = "light"\n', encoding="utf-8")
    assert _run(repo, "--force").returncode == 0
    assert json.loads(hook.read_text(encoding="utf-8"))  # 又是合法的钩子 JSON
    assert json.loads(mcp_path.read_text(encoding="utf-8"))["mcpServers"]["refcov"]["command"] == sys.executable
    assert cfg.read_text(encoding="utf-8") == 'mode = "light"\n'


def test_other_mcp_servers_are_kept(repo):
    """性质 U6：已有的 MCP 配置里别的服务器不动，只加 refcov 一项。"""
    mcp_path = repo / ".kiro/settings/mcp.json"
    mcp_path.parent.mkdir(parents=True)
    mcp_path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    assert _run(repo).returncode == 0
    servers = json.loads(mcp_path.read_text(encoding="utf-8"))["mcpServers"]
    assert servers["other"] == {"command": "x"} and "refcov" in servers


def test_without_git_nothing_is_written(tmp_path):
    """性质 U7：仓库根没有 `.git` 时报错退出，什么都不写。"""
    res = _run(tmp_path)
    assert res.returncode == 1
    assert not (tmp_path / ".kiro").exists() and not (tmp_path / "refcov.toml").exists()
