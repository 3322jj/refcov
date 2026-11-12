"""报告、文字版、状态行（任务 7，设计 3.5，需求 9.8、12.1–12.4），以及日志末尾半行的处理。"""

import json
import shutil
from pathlib import Path

import pytest

from refcov import api, cli, coverage
from refcov.sources import register
from refcov.store import Store, StoreError

REPO = Path(__file__).resolve().parents[1]
SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"


@pytest.fixture
def store(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copyfile(SAMPLE, tmp_path / "docs" / "sample-hooks.md")
    s = Store(tmp_path)
    register(s, "docs/sample-hooks.md", "sample")
    return s


def snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def read_as(store, unit, session):
    r = api.read(store, "sample", unit)
    if session:
        api.attach_session(store, r.call, session)
    return r


# ---- JSON ----


def test_report_fields_follow_design_3_5(store):
    """任务 11 起补齐到这些字段，字段名按设计 3.5；另加 requirement_docs。tokens、blocks、writes、
    tasks_not_found、protected、files 在后面的任务里加。"""
    rep = api.report(store, "sess_a")
    assert set(rep) == {"version", "generated", "session", "session_available", "mode", "enforce", "pass",
                        "sources", "missing", "ghost_units", "not_required_units", "ignored_units",
                        "phantom_requirements", "invalid_refs", "unconverted_requirements", "relaxed", "exempt",
                        "config_mtime", "requirement_docs", "unknown_session_calls", "by_session", "chain"}
    assert rep["relaxed"] == {"sources": [], "kinds": [], "units": [], "cited_but_relaxed": []}
    assert rep["exempt"] == ["DEVLOG.md", "**/DEVLOG.md", "docs/decisions/**"]
    assert rep["config_mtime"] is None and rep["requirement_docs"] == []
    assert rep["enforce"] is True and rep["pass"] is False
    assert rep["version"] == 1 and rep["session"] == "sess_a" and rep["session_available"] is True
    (src,) = rep["sources"]
    assert set(src) == {"id", "units", "read_history", "read_session", "required",
                        "required_read_history", "required_read_session"}
    assert rep["chain"] == {"ok": True, "lines": 1}


def test_counts_history_session_and_unknown(store):
    read_as(store, "Hooks", "sess_a")
    read_as(store, "Hooks", "sess_a")  # 同一单元读两次只算一次
    read_as(store, "退出码", "sess_b")
    read_as(store, "退出码-2", None)  # 没有补记：会话未知
    rep = api.report(store, "sess_a")
    (src,) = rep["sources"]
    assert (src["units"], src["read_history"], src["read_session"]) == (5, 3, 1)
    assert (src["required"], src["required_read_history"], src["required_read_session"]) == (5, 3, 1)
    assert rep["unknown_session_calls"] == 1
    assert [m["unit"] for m in rep["missing"]] == ["sample-hooks", "匹配-工具名"]
    assert rep["missing"][1] == {"source": "sample", "unit": "匹配-工具名", "title": "匹配 [工具名]"}
    rows = {b["session"]: b for b in rep["by_session"]}
    assert [b["session"] for b in rep["by_session"]] == ["sess_a", "sess_b", "unknown"]
    assert (rows["sess_a"]["units_read"], rows["sess_a"]["text_units"], rows["sess_a"]["images"]) == (1, 2, 0)
    assert rows["sess_a"]["first"] and "first" not in rows["unknown"]
    assert rows["unknown"]["units_read"] == 1 and rows["unknown"]["blocks"] == 0


def test_stale_reads_do_not_count(store):
    """校验值过期的 read 记录不算看过（需求 1.4），但仍算会话未知的调用次数。"""
    read_as(store, "Hooks", None)
    p = store.root / "docs" / "sample-hooks.md"
    p.write_text(p.read_text(encoding="utf-8").replace("钩子在事件发生时运行命令。", "改了。"), encoding="utf-8")
    register(store, "docs/sample-hooks.md", "sample")
    rep = api.report(store, None)
    assert rep["sources"][0]["read_history"] == 0 and rep["unknown_session_calls"] == 1


def test_without_session_read_session_is_null(store):
    read_as(store, "Hooks", "sess_a")
    rep = api.report(store, None)
    assert rep["session"] is None and rep["session_available"] is False
    assert rep["sources"][0]["read_session"] is None and rep["sources"][0]["required_read_session"] is None


def test_mode_comes_from_config(store):
    (store.root / "refcov.toml").write_text('mode = "light"\n', encoding="utf-8")
    assert api.report(store, None)["mode"] == "light"
    # 轻量模式：markdown 没有关键类型、也没有需求文档，必看集合为空，达标
    assert api.status_line(store, "s").startswith("RefCov 轻量模式 达标：必看单元 本会话 0/0，历史 0/0")


def test_report_and_status_line_write_nothing(store):
    """报告、文字版、状态行都只读：不拿锁、不建文件、不写日志记录。"""
    read_as(store, "Hooks", "sess_a")
    before = snapshot(store.root)
    api.report_text(api.report(store, "sess_a"))
    api.status_line(store, "sess_a")
    assert snapshot(store.root) == before  # 命令行在下面单独测


def test_empty_repo_report(tmp_path):
    s = Store(tmp_path)
    rep = api.report(s, None)
    assert rep["sources"] == [] and rep["unknown_session_calls"] == 0
    assert rep["by_session"] == [{"session": "unknown", "units_read": 0, "blocks": 0, "text_units": 0, "images": 0}]
    assert "还没有登记参考源" in api.status_line(s, "x")
    assert not (tmp_path / ".refcov").exists()


def test_broken_chain_is_reported(store):
    read_as(store, "Hooks", None)
    lines = store.log_path.read_bytes().split(b"\n")
    lines[0] = lines[0].replace(b'"units":5', b'"units":6')  # 改第 1 行：第 2 行起断开
    store.log_path.write_bytes(b"\n".join(lines))
    rep = api.report(store, None)
    assert rep["chain"] == {"ok": False, "lines": 2, "broken_at": 2}
    assert "第 2 行起断开" in api.report_text(rep)
    assert "第 2 行起断开" in api.status_line(store, None)


# ---- 日志末尾半行 ----


def test_reader_ignores_partial_last_line(store):
    """不拿锁的读取方：末尾没有 \\n 的那段当成正在写的行，不算记录，链不报断开。"""
    read_as(store, "Hooks", None)
    with open(store.log_path, "ab") as f:
        f.write(b'{"seq":3,"type":"read","sour')
    assert [r["seq"] for r in store.records()] == [1, 2]
    assert store.verify_chain().ok and store.log_tail_partial()
    rep = api.report(store, None)
    assert rep["chain"] == {"ok": True, "lines": 2, "partial_tail": True}
    assert "日志末尾有一行还没写完，这次没算" in api.report_text(rep)


def test_writer_refuses_to_append_after_partial_line(store):
    """拿着锁的写入方：末尾半行说明上次写入中断，报错、不写。"""
    with open(store.log_path, "ab") as f:
        f.write(b'{"seq":2,"ty')
    before = store.log_path.read_bytes()
    with pytest.raises(StoreError, match="日志末尾有一行没写完，可能上次写入中断"):
        store.append("x")
    with pytest.raises(StoreError, match="没写完"):
        with store.locked():
            store.next_seq_locked()
    with pytest.raises(api.ReadError, match="没写完"):
        api.read(store, "sample", "Hooks")
    assert store.log_path.read_bytes() == before
    assert not store.lock_path.exists()


def test_complete_log_has_no_partial_tail(store):
    assert not store.log_tail_partial()
    assert not Store(store.root / "nope").log_tail_partial()


# ---- 文字版和状态行 ----


def test_text_is_generated_from_json(store):
    read_as(store, "Hooks", "sess_a")
    read_as(store, "退出码", None)
    text = api.report_text(api.report(store, "sess_a"))
    assert text.splitlines()[0] == "RefCov 严格模式 未达标"
    assert "sample：必看 本会话 1/5，历史 2/5（共 5 个单元，历史看过 2 个）" in text
    assert "还差 3 个（幽灵单元：必看但没看过）：sample/sample-hooks、sample/匹配-工具名、sample/退出码-2" in text
    assert "被忽略单元（看过但没被需求引用）2 个：sample/Hooks、sample/退出码" in text
    assert "出处检查：未配置需求文档（不影响达标）。" in text
    assert "配置文件：没有 refcov.toml，用默认值" in text
    assert "会话未知的读取：1 次" in text
    assert "哈希链：链完整（4 行）" in text  # register、read、session、read
    assert text.endswith(api.HINT)
    assert "本会话 不可用" in api.report_text(api.report(store, None))


def test_status_line_content(store):
    """需求 9.8：模式、本会话 x/y、历史 a/y、还差几个和前 5 个、直接读文件不算看过的提示。一行。"""
    read_as(store, "Hooks", "sess_a")
    line = api.status_line(store, "sess_a")
    assert "\n" not in line
    assert line == ("RefCov 严格模式 未达标：必看单元 本会话 1/5，历史 1/5；还差 4 个："
                    "sample/sample-hooks、sample/退出码、sample/匹配-工具名、sample/退出码-2。" + api.HINT)


def test_status_line_lists_first_five_then_ellipsis(store, tmp_path):
    (tmp_path / "docs" / "many.md").write_text("".join(f"# 节{i}\n正文\n" for i in range(8)), encoding="utf-8")
    register(store, "docs/many.md", "many")
    line = api.status_line(store, "s")
    assert "还差 13 个：" in line and line.count("、") == 5 and "、…。" in line


def test_status_line_when_everything_read(store):
    for u in ("sample-hooks", "Hooks", "退出码", "匹配-工具名", "退出码-2"):
        read_as(store, u, "s")
    assert "没有还差的单元。" in api.status_line(store, "s")


# ---- 命令行 ----


def test_cli_report_text_json_and_session(store, monkeypatch, capsys):
    read_as(store, "Hooks", "sess_a")
    monkeypatch.chdir(store.root)
    before = snapshot(store.root)
    assert cli.main(["report"]) == 0
    assert "本会话 不可用" in capsys.readouterr().out
    assert cli.main(["report", "--session", "sess_a"]) == 0
    assert "本会话 1/5" in capsys.readouterr().out
    assert cli.main(["report", "--json", "--session", "sess_a"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["sources"][0]["read_session"] == 1 and rep["session"] == "sess_a"
    assert snapshot(store.root) == before


def test_cli_report_needs_repo_root(store, monkeypatch, capsys):
    monkeypatch.chdir(store.root / "docs")
    assert cli.main(["report"]) == 1
    assert "请在仓库根目录运行 refcov" in capsys.readouterr().err


def test_cli_report_bad_config(store, monkeypatch, capsys):
    (store.root / "refcov.toml").write_text("mode = [", encoding="utf-8")
    monkeypatch.chdir(store.root)
    assert cli.main(["report"]) == 1
    assert "报告失败" in capsys.readouterr().err


# ---- 真实日志（完成标志 3）----


def test_real_log_first_nine_lines(tmp_path):
    """真实日志的前 9 行（任务 5、6 实测产生，只追加，以后不会变）：会话未知 4 次（c-2、c-3、c-4、c-9），链完整。"""
    (tmp_path / ".refcov").mkdir()
    shutil.copyfile(REPO / ".refcov" / "sources.json", tmp_path / ".refcov" / "sources.json")
    lines = (REPO / ".refcov" / "log.jsonl").read_bytes().split(b"\n")[:9]
    (tmp_path / ".refcov" / "log.jsonl").write_bytes(b"\n".join(lines) + b"\n")
    rep = api.report(Store(tmp_path), None)
    assert rep["unknown_session_calls"] == 4
    assert rep["chain"] == {"ok": True, "lines": 9}
    assert rep["sources"][0]["id"] == "kiro-hooks" and rep["sources"][0]["read_history"] == 6
    sessions = [b["session"] for b in rep["by_session"]]
    assert sessions[-1] == "unknown" and len(sessions) == 3


def test_coverage_first_session_record_wins():
    recs = [{"type": "session", "call": "c-2", "session": "a"}, {"type": "session", "call": "c-2", "session": "b"}]
    assert coverage.call_sessions(recs) == {"c-2": "a"}
