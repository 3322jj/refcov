"""`refcov doctor` 的性质测试和固定例子（设计第 5 节，需求 5）。

进程内运行 integrations/commands.py 的 doctor。探测解释器的函数换成"找得到"，原因同 test_init_kiro.py：
性质测试要跑很多次。探测本身在 test_init_kiro.py 里用子进程测过。
"""

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

from hypothesis import given, settings, strategies as st

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from integrations import commands  # noqa: E402
from integrations.kiro import init as kiro_init  # noqa: E402

HOOK_EVENTS = ["pre-write", "pre-shell", "pretask", "post-mcp", "prompt"]


def _doctor(repo: Path):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = commands.doctor(repo)
    return code, out.getvalue()


def _snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _init(repo: Path) -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assert kiro_init.run(repo, False) == 0


def _mcp_path(repo: Path) -> Path:
    return repo / ".kiro" / "settings" / "mcp.json"


def _edit_mcp(repo: Path, **changes) -> None:
    data = json.loads(_mcp_path(repo).read_text(encoding="utf-8"))
    data["mcpServers"]["refcov"].update(changes)
    _mcp_path(repo).write_text(json.dumps(data), encoding="utf-8")


def _build(tmp: str, git: bool, mcp_state: str, hook_events: list, toml_state: str, with_state: bool) -> Path:
    repo = Path(tmp)
    if git:
        (repo / ".git").mkdir()
    if mcp_state == "valid":
        _mcp_path(repo).parent.mkdir(parents=True, exist_ok=True)
        entry = {"command": sys.executable, "args": ["-P", "-m", "refcov_mcp", "--root", str(repo)], "disabled": False}
        _mcp_path(repo).write_text(json.dumps({"mcpServers": {"refcov": entry}}), encoding="utf-8")
    elif mcp_state == "bad":
        _mcp_path(repo).parent.mkdir(parents=True, exist_ok=True)
        _mcp_path(repo).write_bytes(b"{not json")
    for ev in hook_events:
        path = repo / ".kiro" / "hooks" / f"refcov-{ev}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        cmd = f'"{sys.executable}" -P -m integrations.kiro.hook --root "{repo}" {ev}'
        path.write_text(json.dumps({"hooks": [{"action": {"type": "command", "command": cmd}}]}), encoding="utf-8")
    if toml_state == "valid":
        (repo / "refcov.toml").write_bytes(b'mode = "strict"\n[sources]\nfiles = []\n')
    elif toml_state == "bad":
        (repo / "refcov.toml").write_bytes(b'mode = "unterminated\n')
    if with_state:
        (repo / ".refcov").mkdir()
        (repo / ".refcov" / "log.jsonl").write_bytes(b'{"seq":1,"type":"read"}\n')
    return repo


@settings(max_examples=40, deadline=None)
@given(st.booleans(), st.sampled_from(["none", "valid", "bad"]), st.lists(st.sampled_from(HOOK_EVENTS), unique=True,
                                                                          max_size=5),
       st.sampled_from(["none", "valid", "bad"]), st.booleans())
def test_doctor_never_writes_anything(git, mcp_state, hook_events, toml_state, with_state):
    """性质 D1：doctor 只读。对随机的仓库状态（缺文件、坏 JSON、有或没有状态目录），运行前后每个文件的存在与否
    和字节都相同；它不建 .refcov/，也不写日志。"""
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        repo = _build(tmp, git, mcp_state, hook_events, toml_state, with_state)
        before = _snapshot(repo)
        _doctor(repo)  # 不论结果如何都不能抛异常
        assert _snapshot(repo) == before


def test_clean_init_has_no_problems(tmp_path):
    """干净的 init 以后 doctor 退出码为 0；"没有登记资料"只是提示（需求 5.7）。"""
    repo = _build(str(tmp_path), True, "none", [], "none", False)
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        _init(repo)
        code, text = _doctor(repo)
    assert code == 0, text
    assert "还没有登记过资料" in text and "  问题：" not in text


def test_not_in_a_repo_is_exit_2_and_writes_nothing(tmp_path):
    code, text = _doctor(tmp_path)
    assert code == 2 and "不能检查" in text
    assert list(tmp_path.iterdir()) == []


def test_missing_hook_file_is_reported_with_a_fix(tmp_path):
    repo = _build(str(tmp_path), True, "none", [], "none", False)
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        _init(repo)
        (repo / ".kiro" / "hooks" / "refcov-pretask.json").unlink()
        code, text = _doctor(repo)
    assert code == 1
    assert "缺钩子文件 .kiro/hooks/refcov-pretask.json" in text
    assert "修法：运行 refcov init" in text


def test_root_pointing_elsewhere_is_reported(tmp_path):
    repo = _build(str(tmp_path), True, "none", [], "none", False)
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        _init(repo)
        _edit_mcp(repo, args=["-P", "-m", "refcov_mcp", "--root", str(tmp_path / "other")])
        code, text = _doctor(repo)
    assert code == 1
    assert "--root 没有指向当前仓库" in text
    assert "修法：运行 refcov init --force" in text


def test_interpreter_that_does_not_exist_is_reported(tmp_path):
    repo = _build(str(tmp_path), True, "none", [], "none", False)
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        _init(repo)
        _edit_mcp(repo, command=str(tmp_path / "no" / "python.exe"))
        code, text = _doctor(repo)
    assert code == 1
    assert "command 不是存在的绝对路径" in text


def test_relative_hook_command_is_reported(tmp_path):
    repo = _build(str(tmp_path), True, "none", [], "none", False)
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        _init(repo)
        path = repo / ".kiro" / "hooks" / "refcov-pretask.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["hooks"][0]["action"]["command"] = "python integrations/kiro/hook.py pretask"
        path.write_text(json.dumps(data), encoding="utf-8")
        code, text = _doctor(repo)
    assert code == 1
    assert "解释器不是存在的绝对路径" in text and "没有 --root" in text


def test_syntax_error_in_config_is_reported_with_the_fix(tmp_path):
    repo = _build(str(tmp_path), True, "none", [], "bad", False)
    code, text = _doctor(repo)
    assert code == 1
    assert "不能解析" in text
    assert "改掉上面说的语法错" in text


def test_pending_sync_is_reported(tmp_path):
    repo = _build(str(tmp_path), True, "none", [], "none", False)
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        _init(repo)
    (repo / "refcov.toml").write_text('mode = "strict"\n[sources]\nfiles = ["notes/*.md"]\n', encoding="utf-8")
    (repo / "notes").mkdir()
    (repo / "notes" / "a.md").write_text("# A\n", encoding="utf-8")
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        code, text = _doctor(repo)
    assert code == 1
    assert "还没登记" in text and "运行 refcov sync" in text


def test_disabled_mcp_entry_is_reported(tmp_path):
    repo = _build(str(tmp_path), True, "none", [], "none", False)
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        _init(repo)
        _edit_mcp(repo, disabled=True)
        code, text = _doctor(repo)
    assert code == 1
    assert "disabled 为真" in text
    assert "init 不改这一项" in text


def test_path_comparison_ignores_case_on_windows(tmp_path):
    """需求 5.10：Windows 上路径不分大小写，换了大小写的同一个仓库根不算问题。"""
    if os.name != "nt":
        return
    repo = _build(str(tmp_path), True, "none", [], "none", False)
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True):
        _init(repo)
        _edit_mcp(repo, args=["-P", "-m", "refcov_mcp", "--root", str(repo).swapcase()])
        code, text = _doctor(repo)
    assert "--root 没有指向当前仓库" not in text
