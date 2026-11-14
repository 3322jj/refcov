"""镜头条页面（镜头应用任务 6，需求 5.1–5.5、1.8）。数据只来自核心层；不用 ffmpeg。"""

import dataclasses
import hashlib
import importlib
import json
import re

import pytest

import shot_loader
from refcov import api
from refcov.sources import register
from refcov.store import Store

cli = shot_loader.load_cli()
page = importlib.import_module("page")
IDS = ["shot-00-00-0", "shot-00-01-0", "shot-00-04-0"]
SHOTS = [(0, 10), (10, 40), (40, 60)]  # 时长 1、3、2 秒：格子宽度要按 1:3:2


def write_list(adapter, root, video_bytes=b"fake video one" * 50):
    video = root / "v.mp4"
    video.write_bytes(video_bytes)
    st = video.stat()
    h = adapter.Header("v.mp4", hashlib.sha256(video_bytes).hexdigest(), st.st_size, st.st_mtime_ns, 60, 0.25, 0.5)
    (root / "v.shots.md").write_text(adapter.format_list(h, SHOTS), encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    adapter = shot_loader.install(tmp_path)
    monkeypatch.setattr(adapter, "extract_frame", lambda path, seconds: b"\xff\xd8fake")
    (tmp_path / "refcov.toml").write_text(
        'requirements = ["req/*.md"]\n[adapters]\nshot = "apps/shot-coverage/adapter.py"\n', encoding="utf-8")
    (tmp_path / "req").mkdir()
    (tmp_path / "req" / "requirements.md").write_text(
        "### 需求 1：看第二个镜头\n正文\n\n出处：[ref:vid/shot-00-01-0]\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    write_list(adapter, tmp_path)
    store = Store(tmp_path)
    register(store, "v.shots.md", "vid", adapter="shot")
    return store, adapter


def cell_classes(text):
    return re.findall(r'<div class="(cell[^"]*)"', text)


def test_unread_strip_is_all_grey(repo):
    store, _ = repo
    data = page.collect(store)
    assert data["source"] == "vid" and data["shots"] == 3 and data["read"] == 0 and data["images"] == 0
    text = page.render_strip(data)
    assert cell_classes(text) == ["cell", "cell cited", "cell"]  # 第二个镜头被需求引用，三个都没读


def test_read_and_cited_cells_are_marked(repo):
    """性质（需求 5.1）：格子数等于镜头数；读过的格子带 read、被需求引用的带 cited；宽度（flex-grow）按时长成比例。"""
    store, _ = repo
    api.read(store, "vid", IDS[0])
    api.read(store, "vid", IDS[2])
    data = page.collect(store)
    assert [c["read"] for c in data["cells"]] == [True, False, True]
    assert [c["cited"] for c in data["cells"]] == [False, True, False]
    assert [c["ticks"] for c in data["cells"]] == [10, 30, 20]
    text = page.render_strip(data)
    classes = cell_classes(text)
    assert classes == ["cell read", "cell cited", "cell read"]
    assert re.findall(r'style="flex-grow:(\d+)"', text) == ["10", "30", "20"]
    assert "read <b>2</b> of <b>3</b> shots" in text and "<b>2</b> keyframe images" in text
    assert 'title="shot-00-01-0  1.0-4.0 s  not read, cited by a requirement"' in text


def test_numbers_come_from_the_core(repo):
    """需求 5.2：页面的数字就是核心层的数：读过几个、图片张数和 `count`、`list_units` 一致，同一个镜头读两次只算一个。"""
    store, _ = repo
    for u in (IDS[1], IDS[1], IDS[2]):
        api.read(store, "vid", u)
    data = page.collect(store)
    assert (data["read"], data["reads"], data["images"]) == (2, 3, 3)
    assert data["read"] == sum(u["read"] for u in api.list_units(store, "vid"))
    assert page.count_reads(store) == [{"source": "vid", "shots": 3, "read": 2, "reads": 3, "images": 3}]


def test_invalid_reads_are_not_lit(repo):
    """视频换了、清单重新登记后，旧读取记录失效，格子回到灰色，回放事件里也没有它们。"""
    store, adapter = repo
    for u in IDS:
        api.read(store, "vid", u)
    assert page.collect(store)["read"] == 3
    write_list(adapter, store.root, video_bytes=b"another video" * 60)
    register(store, "v.shots.md", "vid", adapter="shot")
    data = page.collect(store)
    assert data["read"] == 0 and data["events"] == [] and not any(c["read"] for c in data["cells"])


def test_events_are_first_valid_reads_in_log_order(repo):
    store, _ = repo
    for u in (IDS[2], IDS[0], IDS[2], IDS[1]):
        api.read(store, "vid", u)
    data = page.collect(store)
    assert [e["unit"] for e in data["events"]] == [IDS[2], IDS[0], IDS[1]]
    text = page.render_strip(data)
    embedded = re.search(r'<script id="events" type="application/json">(.*?)</script>', text, re.S).group(1)
    assert json.loads(embedded) == data["events"]


def test_page_is_self_contained_and_shows_the_final_state_without_scripts(repo):
    """需求 5.1、5.5：不联网、不嵌图片和视频画面；亮灰在服务端就写进 class，回放控件默认隐藏，脚本只在回放时改。"""
    store, _ = repo
    api.read(store, "vid", IDS[0])
    text = page.render_strip(page.collect(store))
    for forbidden in ("<img", "<video", "<canvas", "http", "src=", "href=", "@import", "url("):
        assert forbidden not in text, forbidden
    assert cell_classes(text)[0] == "cell read"  # 没有脚本也是亮的
    assert ".controls{display:none" in text


def test_limitations_are_on_the_page(repo):
    """需求 1.8：页面写明局限：只切硬切；一个镜头一张关键帧，看不到镜头里随时间出现的字。"""
    store, _ = repo
    text = page.render_strip(page.collect(store))
    assert "hard cuts only" in text and "does not show text or motion" in text and "not the same as having seen" in text


def test_render_escapes_ids_and_cannot_break_out_of_the_script_tag():
    data = {"source": "<b>x</b>", "shots": 1, "read": 1, "reads": 1, "images": 1,
            "cells": [{"id": '"><script>alert(1)</script>', "start": 0.0, "end": 1.0, "ticks": 10, "read": True,
                       "cited": False}],
            "events": [{"unit": "u", "time": "</script><script>alert(2)</script>"}]}
    text = page.render_strip(data)
    assert "<b>x</b>" not in text and "<script>alert(1)" not in text
    assert text.count("<script") == 2 and text.count("</script>") == 2  # 事件数据和回放脚本，别的都被转义了


def test_cli_page_writes_a_file(repo, capsys):
    store, _ = repo
    api.read(store, "vid", IDS[0])
    assert cli.main(["page", "--out", "out/strip.html"]) == 0
    text = (store.root / "out" / "strip.html").read_text(encoding="utf-8")
    assert cell_classes(text) == ["cell read", "cell cited", "cell"]
    assert "读过 1 / 3 个镜头" in capsys.readouterr().out
    assert not list(store.root.rglob("*.tmp"))
    assert cli.main(["page"]) == 0 and (store.root / "shot-strip.html").exists()


def test_cli_page_without_a_shot_source_fails(tmp_path, monkeypatch, capsys):
    (tmp_path / ".git").mkdir()
    (tmp_path / "n.md").write_text("# 笔记\n正文\n", encoding="utf-8")
    register(Store(tmp_path), "n.md", "notes")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["page"]) == 1
    assert "没有登记镜头适配器的参考源" in capsys.readouterr().err
    assert not (tmp_path / "shot-strip.html").exists()


def test_cli_page_unknown_source_fails(repo, capsys):
    assert cli.main(["page", "--source", "nope"]) == 1
    assert "（nope）" in capsys.readouterr().err


def test_page_does_not_write_to_the_state_directory(repo):
    """只读：生成数据不改状态目录里的任何文件。"""
    store, _ = repo
    api.read(store, "vid", IDS[0])
    snap = {p: p.read_bytes() for p in store.state_dir.rglob("*") if p.is_file()}
    page.render_strip(page.collect(store))
    assert {p: p.read_bytes() for p in store.state_dir.rglob("*") if p.is_file()} == snap
