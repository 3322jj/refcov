"""api.call_from_text、api.attach_session（任务 6，需求 4.5）。"""

import shutil
from pathlib import Path

import pytest

from refcov import api
from refcov.sources import register
from refcov.store import LockTimeout, Store

SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"


@pytest.fixture
def store(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copyfile(SAMPLE, tmp_path / "docs" / "sample-hooks.md")
    s = Store(tmp_path)
    register(s, "docs/sample-hooks.md", "sample")
    return s


@pytest.mark.parametrize(
    "text, call",
    [
        ("正文\n\n提示\nrefcov-call: c-12", "c-12"),
        ("正文\nrefcov-call: c-12\n", "c-12"),  # 只去掉末尾换行
        ("正文\r\nrefcov-call: c-7\r\n", "c-7"),
        ("refcov-call: c-1", "c-1"),
        ("正文\nrefcov-call: c-12 ", None),  # 末尾空格不去
        ("正文\n refcov-call: c-12", None),
        ("正文\nrefcov-call: c-12\n\n", "c-12"),
        ("正文\nrefcov-call: t-3", None),  # 凭证编号这一步不认
        ("正文\nrefcov-call: c-", None),
        ("正文\nrefcov-call: c-1x", None),
        ("refcov-call: c-5\n别的内容", None),  # 不在最后一行
        ("还没有登记任何参考源。\n\n" + api.HINT, None),  # list_units
        ("", None),
    ],
)
def test_call_from_text_only_accepts_exact_last_line(text, call):
    """只认最后一行：完全是 `refcov-call: c-<数字>`，只去掉末尾换行。"""
    assert api.call_from_text(text) == call


def test_call_from_real_read_text(store):
    r = api.read(store, "sample", "Hooks")
    assert api.call_from_text(r.text()) == r.call


def test_attach_appends_session_record(store):
    r = api.read(store, "sample", "Hooks")
    assert api.attach_session(store, r.call, "sess_a", "sample", "Hooks") is True
    rec = store.records()[-1]
    assert (rec["type"], rec["session"], rec["call"]) == ("session", "sess_a", r.call)
    assert store.verify_chain().ok


def test_attach_same_session_twice_writes_once(store):
    r = api.read(store, "sample", "Hooks")
    api.attach_session(store, r.call, "sess_a")
    n = len(store.records())
    assert api.attach_session(store, r.call, "sess_a") is False
    assert len(store.records()) == n


def test_attach_other_session_is_refused(store):
    r = api.read(store, "sample", "Hooks")
    api.attach_session(store, r.call, "sess_a")
    n = len(store.records())
    with pytest.raises(api.AttachError, match="已经补记成会话"):
        api.attach_session(store, r.call, "sess_b")
    assert len(store.records()) == n


def test_attach_needs_an_existing_read_record(store):
    n = len(store.records())
    with pytest.raises(api.AttachError, match="没有这个调用编号的 read 记录"):
        api.attach_session(store, "c-99", "sess_a")
    with pytest.raises(api.AttachError, match="没有这个调用编号的 read 记录"):
        api.attach_session(store, "c-1", "sess_a")  # c-1 不存在：第 1 行是 register，没有 call
    assert len(store.records()) == n


def test_attach_checks_tool_arguments(store):
    """需求 4.5：按工具参数和返回内容对上是哪一次调用。参数和 read 记录不一致就不写。"""
    r = api.read(store, "sample", "Hooks")
    n = len(store.records())
    with pytest.raises(api.AttachError, match="unit"):
        api.attach_session(store, r.call, "sess_a", "sample", "退出码")
    with pytest.raises(api.AttachError, match="source"):
        api.attach_session(store, r.call, "sess_a", "other", "Hooks")
    assert len(store.records()) == n


def test_attach_empty_session_is_refused(store):
    r = api.read(store, "sample", "Hooks")
    with pytest.raises(api.AttachError):
        api.attach_session(store, r.call, "")


def test_attach_lock_timeout_writes_nothing(store):
    r = api.read(store, "sample", "Hooks")
    store.lock_path.write_text("other", encoding="ascii")
    before = store.log_path.read_bytes()
    with pytest.raises(LockTimeout):
        api.attach_session(store, r.call, "sess_a")
    assert store.log_path.read_bytes() == before
