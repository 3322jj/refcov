"""`integrations/kiro/setup.py`：和 `refcov init` 做同样的事（设计 2.1、4.5）。

setup 在临时仓库里用子进程运行。子进程的 PYTHONPATH 指向仓库根，所以探测能找到 integrations 包，
结果不依赖 D:\\pyth 里的可编辑安装是不是最新（设计 7.3）。--force 只换 MCP 的 refcov 项的 command 和 args（需求 3.6）。
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RC = Path(__file__).resolve().parents[1]  # RefCov 的目录
SETUP = RC / "integrations" / "kiro" / "setup.py"
HOOK = RC / "integrations" / "kiro" / "hook.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HOOK_MOD = _load("refcov_hook_under_test", HOOK)


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RC)
    return env


def _run(repo: Path, *args):
    return subprocess.run([sys.executable, str(SETUP), *args], cwd=repo, capture_output=True, env=_env(),
                          timeout=180)


def _mcp(repo: Path) -> dict:
    return json.loads((repo / ".kiro" / "settings" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]


def _snapshot(repo: Path) -> dict:
    return {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob("*") if p.is_file()}


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_take_root_is_taken_only_before_the_event():
    """`--root <路径>` 取出来，剩下的第一个参数是事件名；没有它或没有值时参数原样保留。"""
    take = HOOK_MOD._take_root
    assert take(["--root", "D:/r", "pre-write"]) == (["pre-write"], "D:/r")
    assert take(["pre-write"]) == (["pre-write"], None)
    assert take(["--root"]) == (["--root"], None)


def test_setup_writes_the_mcp_entry_and_five_hooks_with_absolute_paths(repo):
    res = _run(repo)
    assert res.returncode == 0, res.stderr.decode("utf-8", "replace")
    entry = _mcp(repo)["refcov"]
    assert entry["command"] == sys.executable
    assert entry["args"][:3] == ["-P", "-m", "refcov_mcp"]
    hooks = sorted((repo / ".kiro" / "hooks").glob("refcov-*.json"))
    assert len(hooks) == 5
    for f in hooks:
        (h,) = json.loads(f.read_text(encoding="utf-8"))["hooks"]
        cmd = h["action"]["command"]
        assert cmd.startswith(f'"{sys.executable}" -P -m integrations.kiro.hook --root "'), cmd
        assert cmd.endswith(" " + f.stem[len("refcov-"):]), cmd
    assert "可以改用 refcov init" in res.stdout.decode("utf-8", "replace")


def test_second_run_is_byte_identical(repo):
    assert _run(repo).returncode == 0
    before = _snapshot(repo)
    assert _run(repo).returncode == 0
    assert _snapshot(repo) == before


def test_force_replaces_only_command_and_args_of_the_mcp_entry(repo):
    """需求 3.6：--force 只换 command 和 args；autoApprove、env、disabled 等其他键保留。"""
    assert _run(repo).returncode == 0
    mcp_path = repo / ".kiro" / "settings" / "mcp.json"
    data = json.loads(mcp_path.read_text(encoding="utf-8"))
    data["mcpServers"]["refcov"].update({"command": "old", "args": ["x"], "autoApprove": ["read_unit"],
                                         "env": {"A": "1"}, "disabled": True})
    mcp_path.write_text(json.dumps(data), encoding="utf-8")
    assert _run(repo, "--force").returncode == 0
    entry = _mcp(repo)["refcov"]
    assert entry["command"] == sys.executable
    assert entry["args"][:3] == ["-P", "-m", "refcov_mcp"]
    assert entry["autoApprove"] == ["read_unit"]
    assert entry["env"] == {"A": "1"}
    assert entry["disabled"] is True


def test_force_overwrites_hook_files_but_never_the_config(repo):
    assert _run(repo).returncode == 0
    hook = sorted((repo / ".kiro" / "hooks").glob("refcov-*.json"))[0]
    hook.write_text("EDITED", encoding="utf-8")
    cfg = repo / "refcov.toml"
    cfg.write_text('mode = "light"\n', encoding="utf-8")
    assert _run(repo, "--force").returncode == 0
    assert json.loads(hook.read_text(encoding="utf-8"))["hooks"]
    assert cfg.read_text(encoding="utf-8") == 'mode = "light"\n'


def test_without_force_existing_hook_files_are_kept(repo):
    assert _run(repo).returncode == 0
    hook = sorted((repo / ".kiro" / "hooks").glob("refcov-*.json"))[0]
    hook.write_text("EDITED", encoding="utf-8")
    res = _run(repo)
    assert res.returncode == 0
    assert "跳过" in res.stdout.decode("utf-8", "replace")
    assert hook.read_text(encoding="utf-8") == "EDITED"


def test_other_mcp_servers_are_kept(repo):
    mcp_path = repo / ".kiro" / "settings" / "mcp.json"
    mcp_path.parent.mkdir(parents=True)
    mcp_path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    assert _run(repo).returncode == 0
    servers = _mcp(repo)
    assert servers["other"] == {"command": "x"} and "refcov" in servers


def test_without_git_nothing_is_written(tmp_path):
    res = subprocess.run([sys.executable, str(SETUP)], cwd=tmp_path, capture_output=True, env=_env(), timeout=180)
    assert res.returncode == 1
    assert not (tmp_path / ".kiro").exists() and not (tmp_path / "refcov.toml").exists()
