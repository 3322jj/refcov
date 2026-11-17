"""`refcov init` 的性质测试和固定例子（设计 7.1，需求 2、3）。

进程内运行 integrations/kiro/init.py。写钩子前的探测在测试里换成"找得到"（性质测试要跑很多次，
子进程太慢）；探测本身另有子进程测试，而且用一个不存在的模块名，结果与 D:\\pyth 的安装状态无关。
"""

import contextlib
import io
import json
import string
import sys
import tempfile
from pathlib import Path
from unittest import mock

from hypothesis import given, settings, strategies as st

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:  # 进程内导入仓库里的接入层（设计 7.3）
    sys.path.insert(0, str(REPO))

from integrations.kiro import init as kiro_init  # noqa: E402


def _quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


def _snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _git_repo(root: Path) -> Path:
    (root / ".git").mkdir(exist_ok=True)
    return root


def _write_mcp(repo: Path, data) -> None:
    path = repo / ".kiro" / "settings" / "mcp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(data).encode("utf-8"))


JSON_VALUE = st.one_of(st.text(max_size=8), st.booleans(), st.integers(-5, 5), st.lists(st.text(max_size=5), max_size=3))
SERVER_NAME = st.text(alphabet="abcxyz-_ ", min_size=1, max_size=6)  # 不含 refcov 的字母，所以不会撞上 refcov 项
SERVERS = st.dictionaries(SERVER_NAME, st.dictionaries(st.text(alphabet="abcdef", min_size=1, max_size=5),
                                                       JSON_VALUE, max_size=3), max_size=4)
PATHCHARS = string.ascii_letters + string.digits + " 中文[]()-_.:\\/"


@settings(max_examples=40, deadline=None)
@given(SERVERS, st.booleans())
def test_init_twice_leaves_every_file_byte_identical(servers, with_refcov):
    """性质 I1：已有的合法 MCP 配置（服务器随机，可以有或没有 refcov 项），init 连续运行两次；第二次之后写过的文件逐字节不变。"""
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        repo = _git_repo(Path(tmp))
        data = {"mcpServers": dict(servers)}
        if with_refcov:
            data["mcpServers"]["refcov"] = {"command": "old", "args": [], "disabled": False}
        _write_mcp(repo, data)
        assert _quiet(kiro_init.run, repo, False) == 0
        first = _snapshot(repo)
        assert _quiet(kiro_init.run, repo, False) == 0
        assert _snapshot(repo) == first


@settings(max_examples=40, deadline=None)
@given(st.binary(max_size=120), st.booleans())
def test_config_file_is_never_changed(content, force):
    """性质 I2：配置文件的内容在任何参数下都不变，--force 也不变（需求 3.4）。"""
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        repo = _git_repo(Path(tmp))
        (repo / "refcov.toml").write_bytes(content)
        _quiet(kiro_init.run, repo, force)
        assert (repo / "refcov.toml").read_bytes() == content


@settings(max_examples=40, deadline=None)
@given(SERVERS, st.booleans())
def test_force_keeps_every_other_server(servers, with_refcov):
    """性质 I3：合法 MCP 配置里的其他服务器，init --force 之后仍然在，内容不变（需求 3.1）。"""
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        repo = _git_repo(Path(tmp))
        data = {"mcpServers": dict(servers)}
        if with_refcov:
            data["mcpServers"]["refcov"] = {"command": "old", "args": []}
        _write_mcp(repo, data)
        assert _quiet(kiro_init.run, repo, True) == 0
        after = json.loads((repo / ".kiro" / "settings" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        for name, value in servers.items():
            assert after[name] == value


@settings(max_examples=40, deadline=None)
@given(st.dictionaries(st.text(alphabet="abcdef", min_size=1, max_size=6), JSON_VALUE, max_size=4))
def test_force_changes_only_command_and_args_of_the_refcov_entry(extra):
    """性质 I4：--force 只换 refcov 项的 command 和 args；其他键（autoApprove、env、disabled 等）原样保留（需求 3.6）。"""
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        repo = _git_repo(Path(tmp))
        entry = {"command": "old", "args": ["x"], **{k: v for k, v in extra.items() if k not in ("command", "args")}}
        _write_mcp(repo, {"mcpServers": {"refcov": entry}})
        _quiet(kiro_init.run, repo, True)
        now = json.loads((repo / ".kiro" / "settings" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["refcov"]
        assert now["command"] == sys.executable
        assert now["args"][:3] == ["-P", "-m", "refcov_mcp"]
        for k, v in entry.items():
            if k not in ("command", "args"):
                assert now[k] == v


@settings(max_examples=40, deadline=None)
@given(st.text(alphabet=PATHCHARS, min_size=1, max_size=12), st.text(alphabet=PATHCHARS, min_size=1, max_size=20),
       st.text(alphabet=string.ascii_lowercase + "-", min_size=1, max_size=10))
def test_hook_command_has_the_event_last_and_the_prefix_replaced(py, root, event):
    """性质 I5：模板命令的前缀换成 `"<解释器>" -P -m integrations.kiro.hook --root "<仓库根>"`；事件名留在最后。"""
    cmd = kiro_init.hook_command("python integrations/kiro/hook.py " + event, py, root)
    assert cmd == f'"{py}" -P -m integrations.kiro.hook --root "{root}" {event}'
    assert cmd.endswith(" " + event)


def test_commands_without_the_template_prefix_are_left_alone():
    assert kiro_init.hook_command("echo hi", "p", "r") == "echo hi"


def test_without_git_nothing_is_written(tmp_path):
    """需求 2.5：仓库根没有 .git 时什么都不写，返回 1。"""
    assert _quiet(kiro_init.run, tmp_path, False) == 1
    assert list(tmp_path.iterdir()) == []


def test_refcov_state_directory_is_never_touched(tmp_path):
    """需求 2.4：init 不创建、修改或删除 .refcov/ 下的任何文件。"""
    repo = _git_repo(tmp_path)
    state = repo / ".refcov"
    state.mkdir()
    (state / "log.jsonl").write_bytes(b'{"seq":1}\n')
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        assert _quiet(kiro_init.run, repo, True) == 0
    assert _snapshot(state) == {"log.jsonl": b'{"seq":1}\n'}


def test_missing_hook_module_writes_nothing(tmp_path):
    """需求 2.3：解释器找不到钩子模块时，一个文件都不写，返回 1。用一个不存在的模块名，结果与环境无关。"""
    repo = _git_repo(tmp_path)
    with mock.patch.object(kiro_init, "HOOK_MODULE", "integrations.kiro.no_such_module"):
        assert _quiet(kiro_init.run, repo, False) == 1
    assert not (repo / ".kiro").exists() and not (repo / "refcov.toml").exists()


def test_probe_is_false_for_a_module_that_does_not_exist(tmp_path):
    assert kiro_init.module_importable(sys.executable, tmp_path, "integrations.kiro.no_such_module") is False


def test_probe_finds_the_module_when_the_repo_is_on_pythonpath(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(REPO))
    assert kiro_init.module_importable(sys.executable, tmp_path, "integrations.kiro.hook") is True


def test_config_template_has_no_video_example_and_points_at_detect():
    """需求 7.1、7.4：模板里没有 *.mp4 的示例，注释里写着 detect。"""
    assert "*.mp4" not in kiro_init.CONFIG_TEMPLATE
    assert "detect" in kiro_init.CONFIG_TEMPLATE
    assert "videos/*.shots.md" in kiro_init.CONFIG_TEMPLATE
