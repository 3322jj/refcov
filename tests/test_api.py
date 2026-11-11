"""api.read、api.list_units（任务 5，需求 4.1、4.6、4.8，设计 3.2、6）。"""

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


def state(store):
    return {p.relative_to(store.state_dir).as_posix(): p.read_bytes()
            for p in store.state_dir.rglob("*") if p.is_file()}


def test_read_returns_body_and_appends_record(store):
    """需求 4.1、4.6：返回正文，追加一条 read 记录：调用编号、单元校验值、文字单元数、图片数；会话先为 null。"""
    r = api.read(store, "sample", "退出码")
    assert r.texts == ["\n只有退出码 2 能拦，原因写 stderr。\n\n```bash\n# 注释：这一行不是标题\nexit 2\n```\n\n"]
    assert r.title == "退出码" and r.images == []
    rec = store.records()[-1]
    entry = store.read_sources()["sources"][0]
    unit = next(u for u in entry["units"] if u["id"] == "退出码")
    assert rec == {**rec, "type": "read", "session": None, "call": f"c-{rec['seq']}", "source": "sample",
                   "unit": "退出码", "unit_sha256": unit["sha256"], "text_units": 1, "images": 0}
    assert r.call == rec["call"] == "c-2"  # 第 1 行是 register
    assert store.verify_chain().ok


def test_text_order_and_call_is_the_very_last_line(store):
    """设计 5：正文 → 提示 → `refcov-call: c-<seq>`；调用编号那一行是整段的最后一行，后面没有换行。"""
    text = api.read(store, "sample", "Hooks").text()
    assert text.endswith("\n" + api.HINT + "\nrefcov-call: c-2")
    assert text.splitlines()[-1] == "refcov-call: c-2"
    assert not text.endswith("\n")
    assert text.startswith("\n钩子在事件发生时运行命令。\n")


def test_body_without_trailing_newline_still_ends_with_call():
    r = api.ReadResult("s", "u", "t", ["没有换行结尾"], [], "c-9", {})
    assert r.text() == f"没有换行结尾\n\n{api.HINT}\nrefcov-call: c-9"
    empty = api.ReadResult("s", "u", "t", [""], [], "c-9", {})
    assert empty.text() == f"\n{api.HINT}\nrefcov-call: c-9"


def test_body_line_that_looks_like_a_call_line_is_not_last(store, tmp_path):
    (tmp_path / "docs" / "trick.md").write_text("# 骗\nrefcov-call: c-999\n", encoding="utf-8")
    register(store, "docs/trick.md", "trick")
    text = api.read(store, "trick", "骗").text()
    assert text.splitlines()[-1] == f"refcov-call: {store.records()[-1]['call']}"


def test_repeated_reads_get_new_calls(store):
    a = api.read(store, "sample", "Hooks")
    b = api.read(store, "sample", "Hooks")
    assert (a.call, b.call) == ("c-2", "c-3")
    assert [r["type"] for r in store.records()] == ["register", "read", "read"]


def test_preamble_unit_uses_file_name_from_origin(store):
    """借文件名的开头那段：读取时按清单里的 origin 算出同一个文件名，拆出的单元和登记时一致。"""
    r = api.read(store, "sample", "sample-hooks")
    assert r.title == "sample-hooks" and r.texts[0].startswith("> ## Documentation Index")


def _assert_error_and_no_record(store, source, unit, match):
    before = state(store)
    with pytest.raises(api.ReadError, match=match):
        api.read(store, source, unit)
    assert state(store) == before


def test_unknown_unit_lists_three_nearest(store):
    """需求 4.1、设计 5：单元不存在时报错，附最接近的 3 个 ID；不写 read 记录。"""
    with pytest.raises(api.ReadError) as e:
        api.read(store, "sample", "退出")
    msg = str(e.value)
    assert "最接近的 3 个" in msg and "退出码" in msg and "退出码-2" in msg
    assert msg.split("：")[-1].count("、") == 2
    _assert_error_and_no_record(store, "sample", "退出", "没有单元")


def test_unknown_source(store):
    _assert_error_and_no_record(store, "sampel", "Hooks", "没有参考源.*sample")


def test_missing_cache_asks_user_to_register_again(store):
    """新克隆的仓库没有缓存：报错并提示用户重新登记，不返回内容，不写记录。"""
    for p in store.cache_dir.iterdir():
        p.unlink()
    _assert_error_and_no_record(store, "sample", "Hooks", "缓存里没有.*refcov add docs/sample-hooks.md --id sample")


def test_cache_content_not_matching_manifest(store):
    (cache,) = store.cache_dir.iterdir()
    cache.write_bytes(cache.read_bytes() + b"\n## \xe6\x94\xb9\n")
    _assert_error_and_no_record(store, "sample", "Hooks", "校验值对不上")


def test_cache_not_utf8(store):
    (cache,) = store.cache_dir.iterdir()
    cache.write_bytes(b"\xff\xfe\x00")
    _assert_error_and_no_record(store, "sample", "Hooks", "校验值对不上")


def test_manifest_unit_checksum_not_matching_split(store):
    """缓存没坏，但清单里单元的校验值和重新拆分的对不上（例如适配器改过）：报错，不返回内容。"""
    manifest = store.read_sources()
    next(u for u in manifest["sources"][0]["units"] if u["id"] == "Hooks")["sha256"] = "0" * 64
    store.write_sources(manifest)
    _assert_error_and_no_record(store, "sample", "Hooks", "和清单对不上")


def test_crlf_cache_still_matches(store):
    """缓存里是 CRLF 的原始字节（Windows 上 core.autocrlf），校验值按换行统一后算，照样能读。"""
    (cache,) = store.cache_dir.iterdir()
    cache.write_bytes(cache.read_bytes().replace(b"\n", b"\r\n"))
    assert api.read(store, "sample", "Hooks").texts == ["\n钩子在事件发生时运行命令。\n\n"]


def test_lock_timeout_returns_nothing_and_writes_nothing(store):
    """2 秒拿不到日志锁：报错，不返回内容，不写记录（设计 3.2）。"""
    store.lock_path.write_text("other", encoding="ascii")
    before = state(store)
    with pytest.raises(api.ReadError, match="拿不到日志锁") as e:
        api.read(store, "sample", "Hooks")
    assert isinstance(e.value.__cause__, LockTimeout)
    assert state(store) == before


def test_list_units_and_valid_reads(store):
    """list_units：ID、标题、类型、历史上是否看过；只认校验值和清单一致的 read 记录（需求 1.4）。"""
    api.read(store, "sample", "Hooks")
    units = api.list_units(store)
    assert [(u["id"], u["title"], u["kind"], u["read"]) for u in units] == [
        ("sample-hooks", "sample-hooks", "section", False),
        ("Hooks", "Hooks", "section", True),
        ("退出码", "退出码", "section", False),
        ("匹配-工具名", "匹配 [工具名]", "section", False),
        ("退出码-2", "退出码", "section", False),
    ]
    assert api.list_units(store, "sample") == units
    with pytest.raises(api.ReadError, match="没有参考源"):
        api.list_units(store, "nope")
    # 改了 Hooks 章节、重新登记：旧的 read 记录不再有效
    p = store.root / "docs" / "sample-hooks.md"
    p.write_text(p.read_text(encoding="utf-8").replace("钩子在事件发生时运行命令。", "改过了。"), encoding="utf-8")
    register(store, "docs/sample-hooks.md", "sample")
    assert not next(u for u in api.list_units(store) if u["id"] == "Hooks")["read"]


def test_read_is_the_only_writer_of_read_records():
    """需求 4.8：核心层只有 api.read 追加 type 为 "read" 的记录。"""
    root = Path(__file__).resolve().parents[1]
    import re

    writes_read = re.compile(r"append(_locked)?\(\s*\"read\"")
    hits = [p.relative_to(root).as_posix()
            for p in list((root / "refcov").rglob("*.py")) + list((root / "refcov_mcp").rglob("*.py"))
            if writes_read.search(p.read_text(encoding="utf-8"))]
    assert hits == ["refcov/api.py"]
