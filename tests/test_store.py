"""store.py：状态目录、配置、路径匹配、只追加日志和哈希链（任务 1）。"""

import json
import os
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path

import pytest

from refcov import store
from refcov.store import GENESIS, LockTimeout, Store

REPO = Path(__file__).resolve().parents[1]


def test_state_dir_created_on_first_write_only(tmp_path):
    s = Store(tmp_path)
    s.load_config()
    s.read_sources()
    s.records()
    assert s.verify_chain().ok
    assert not (tmp_path / ".refcov").exists()
    s.append("register", source="x")
    assert (tmp_path / ".refcov" / "log.jsonl").exists()


def test_config_defaults_when_missing(tmp_path):
    cfg = Store(tmp_path).load_config()
    assert cfg["mode"] == "strict" and cfg["enforce"] is True
    assert cfg["exempt"] == ["DEVLOG.md", "**/DEVLOG.md", "docs/decisions/**"]
    assert cfg["confirm"] == ["docs/decisions/**"]
    assert cfg["requirements"] == [] and cfg["scope"] == []
    assert Store(tmp_path).config_mtime() is None


def test_config_file_overrides_defaults(tmp_path):
    (tmp_path / "refcov.toml").write_text(
        'mode = "light"\n[relax]\nunits = ["a/b"]\n[[scope]]\npaths = ["src/**"]\nsources = ["a"]\n',
        encoding="utf-8",
    )
    cfg = Store(tmp_path).load_config()
    assert cfg["mode"] == "light" and cfg["enforce"] is True
    assert cfg["relax"] == {"sources": [], "kinds": [], "units": ["a/b"]}
    assert cfg["scope"] == [{"paths": ["src/**"], "sources": ["a"]}]
    assert Store(tmp_path).config_mtime() is not None


def test_example_config_parses(tmp_path):
    src = REPO / "integrations" / "kiro" / "refcov.example.toml"
    (tmp_path / "refcov.toml").write_bytes(src.read_bytes())
    cfg = Store(tmp_path).load_config()
    assert cfg["requirements"] == [".kiro/specs/*/requirements.md"]
    assert cfg["scope"][0]["sources"] == ["kiro-hooks"]


def test_bad_mode_rejected(tmp_path):
    (tmp_path / "refcov.toml").write_text('mode = "loose"\n', encoding="utf-8")
    with pytest.raises(store.ConfigError):
        Store(tmp_path).load_config()


def test_path_matching_relative_to_root_and_case_insensitive(tmp_path):
    s = Store(tmp_path)
    exempt = store.DEFAULT_CONFIG["exempt"]
    assert s.rel(tmp_path / "Docs" / "Decisions" / "x.md") == "Docs/Decisions/x.md"
    assert s.rel("docs\\DEVLOG.md") == "docs/DEVLOG.md"
    assert s.matches("DEVLOG.md", exempt)
    assert s.matches("docs/devlog.md", exempt)
    assert s.matches(tmp_path / "docs" / "decisions" / "sub" / "a.md", exempt)
    assert not s.matches("docs/DEVLOG.md.bak", exempt)
    assert not s.matches("src/main.py", exempt)


def test_sources_roundtrip(tmp_path):
    s = Store(tmp_path)
    assert s.read_sources() == {"version": 1, "sources": []}
    manifest = {"version": 1, "sources": [{"id": "kiro-hooks", "units": [{"id": "退出码", "title": "退出码"}]}]}
    s.write_sources(manifest)
    assert s.read_sources() == manifest
    assert b"\r\n" not in s.sources_path.read_bytes()


def test_append_fields_and_chain(tmp_path):
    s = Store(tmp_path)
    r1 = s.append("read", call="c-1", unit="退出码 [x]")
    r2 = s.append("session", session="sess_1", call="c-1")
    assert (r1["seq"], r2["seq"]) == (1, 2)
    assert r1["prev"] == GENESIS and r1["session"] is None
    raw = s.log_path.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    first_line = raw.split(b"\n")[0]
    assert r2["prev"] == store.sha256_bytes(first_line)
    assert list(r1)[:4] == ["seq", "time", "type", "session"] and list(r1)[-1] == "prev"
    assert datetime.fromisoformat(r1["time"]).tzinfo is not None
    assert s.records()[0]["unit"] == "退出码 [x]"
    assert s.verify_chain() == store.ChainResult(ok=True, lines=2)


def test_append_rejects_reserved_fields(tmp_path):
    with pytest.raises(ValueError):
        Store(tmp_path).append("read", seq=5)


def test_edited_line_reports_break(tmp_path):
    s = Store(tmp_path)
    for i in range(5):
        s.append("read", call=f"c-{i + 1}")
    lines = s.log_path.read_bytes().split(b"\n")
    lines[2] = lines[2].replace(b"c-3", b"c-9")  # 改第 3 行
    s.log_path.write_bytes(b"\n".join(lines))
    result = s.verify_chain()
    assert (result.ok, result.lines, result.broken_at) == (False, 5, 4)
    assert result.describe() == "第 4 行起断开"


def test_crlf_breaks_chain(tmp_path):
    s = Store(tmp_path)
    for _ in range(3):
        s.append("read")
    s.log_path.write_bytes(s.log_path.read_bytes().replace(b"\n", b"\r\n"))
    assert s.verify_chain().broken_at == 2


def test_lock_timeout_leaves_log_unchanged(tmp_path, monkeypatch):
    s = Store(tmp_path)
    s.append("read")
    s.lock_path.write_text("other")  # 别的进程拿着锁（新鲜的）
    monkeypatch.setattr(store, "LOCK_TIMEOUT", 0.2)
    before = s.log_path.read_bytes()
    with pytest.raises(LockTimeout):
        s._acquire_lock(timeout=0.2)
    with pytest.raises(LockTimeout):
        s.append("read")
    assert s.log_path.read_bytes() == before


def test_stale_lock_is_removed(tmp_path):
    s = Store(tmp_path)
    s.ensure_state_dir()
    s.lock_path.write_text("old")
    old = time.time() - 30
    os.utime(s.lock_path, (old, old))
    s.append("read")
    assert not s.lock_path.exists()
    assert s.verify_chain().ok


WORKER = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, sys.argv[1])
    from refcov.store import Store
    s = Store(sys.argv[2])
    for i in range(100):
        s.append("read", writer=sys.argv[3], i=i)
    """
)


def test_two_processes_append_concurrently(tmp_path):
    procs = [
        subprocess.Popen([sys.executable, "-c", WORKER, str(REPO), str(tmp_path), name])
        for name in ("a", "b")
    ]
    for p in procs:
        assert p.wait(timeout=60) == 0
    s = Store(tmp_path)
    recs = s.records()
    assert len(recs) == 200
    assert [r["seq"] for r in recs] == list(range(1, 201))
    assert sum(r["writer"] == "a" for r in recs) == 100
    assert s.verify_chain() == store.ChainResult(ok=True, lines=200)
    assert not s.lock_path.exists()
    json.dumps(recs)  # 每行都是合法 JSON
