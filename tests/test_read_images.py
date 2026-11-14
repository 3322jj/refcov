"""api.read 调用适配器的 `read`，返回文字和图片并记下张数（镜头应用需求第二部分 C1，骨架需求 2.1、4.1、4.6）。

适配器是测试里现造的假适配器（拆分沿用文档适配器，`read` 另给内容），不用 ffmpeg。
"""

import shutil
from pathlib import Path

import pytest

from refcov import api
from refcov.adapters import markdown
from refcov.sources import Image, register
from refcov.store import Store

SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"
PNG = Image(b"\x89PNG-fake-1", "image/png")
JPG = Image(b"\xff\xd8fake-2", "image/jpeg")


class FakeAdapter:
    """拆分沿用文档适配器；`read` 返回 `parts`，或者抛 `error`。"""

    name = markdown.name
    kinds = markdown.kinds
    split = staticmethod(markdown.split)
    facts = staticmethod(markdown.facts)

    def __init__(self, parts=None, error=None):
        self.parts, self.error, self.calls = parts, error, 0

    def read(self, data, name, unit_id):
        self.calls += 1
        if self.error:
            raise self.error
        return self.parts


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


def use(monkeypatch, adapter):
    monkeypatch.setattr(api, "_adapter", lambda store, name: adapter)
    return adapter


def test_images_are_returned_and_counted(store, monkeypatch):
    """需求 4.1、4.6：适配器返回一段文字加两张图，ReadResult 带两张图，读取记录写 text_units=1、images=2。"""
    use(monkeypatch, FakeAdapter(["镜头 3/10：31.2–34.8 秒", PNG, JPG]))
    r = api.read(store, "sample", "Hooks")
    assert r.texts == ["镜头 3/10：31.2–34.8 秒"] and r.images == [PNG, JPG]
    rec = store.records()[-1]
    assert rec["type"] == "read" and rec["text_units"] == 1 and rec["images"] == 2
    assert r.call == rec["call"] and store.verify_chain().ok


def test_report_counts_images(store, monkeypatch):
    """需求 17.3：报告按会话累加送出的图片张数（读取记录里的 images）。"""
    use(monkeypatch, FakeAdapter(["文字", PNG, JPG]))
    api.read(store, "sample", "Hooks")
    api.read(store, "sample", "退出码")
    by_session = api.report(store, None)["by_session"]
    assert sum(b["images"] for b in by_session) == 4
    assert sum(b["text_units"] for b in by_session) == 2


def test_text_does_not_carry_images_and_ends_with_call(store, monkeypatch):
    """设计 5：图片不进文字；`refcov-call:` 仍是文字的最后一行。"""
    use(monkeypatch, FakeAdapter(["正文", PNG]))
    r = api.read(store, "sample", "Hooks")
    text = r.text()
    assert "PNG" not in text and text.startswith("正文\n")
    assert text.splitlines()[-1] == f"refcov-call: {r.call}" and not text.endswith("\n")


def test_image_only_unit(store, monkeypatch):
    """适配器只返回图片时：文字段数为 0，图片张数照记，调用编号行仍在。"""
    use(monkeypatch, FakeAdapter([JPG]))
    r = api.read(store, "sample", "Hooks")
    assert r.texts == [] and r.images == [JPG]
    rec = store.records()[-1]
    assert rec["text_units"] == 0 and rec["images"] == 1
    assert r.text().splitlines()[-1] == f"refcov-call: {r.call}"


@pytest.mark.parametrize("error", [RuntimeError("视频变了"), KeyError("shot-1"), OSError("ffmpeg 不在")])
def test_adapter_failure_returns_nothing_and_writes_nothing(store, monkeypatch, error):
    """适配器的 `read` 抛任何异常：抛 ReadError、不返回内容、日志不多一行（少算不多算）。"""
    adapter = use(monkeypatch, FakeAdapter(error=error))
    before = state(store)
    with pytest.raises(api.ReadError, match="不返回内容") as e:
        api.read(store, "sample", "Hooks")
    assert adapter.calls == 1 and e.value.__cause__ is error
    assert state(store) == before and store.verify_chain().ok


@pytest.mark.parametrize("parts", [[b"bytes"], ["文字", 3], [None]])
def test_unknown_part_type_is_refused(store, monkeypatch, parts):
    """适配器返回既不是文字也不是图片的内容：拒绝，不写记录。"""
    use(monkeypatch, FakeAdapter(parts))
    before = state(store)
    with pytest.raises(api.ReadError, match="既不是文字也不是图片"):
        api.read(store, "sample", "Hooks")
    assert state(store) == before


def test_markdown_adapter_read_is_unchanged(store):
    """文档适配器：没有图片，images 记 0，正文和以前逐字相同（现有测试另有逐字断言）。"""
    r = api.read(store, "sample", "退出码")
    assert r.images == [] and len(r.texts) == 1 and r.texts[0].startswith("\n只有退出码 2 能拦")
    assert store.records()[-1]["images"] == 0
