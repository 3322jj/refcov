"""`count` 子命令（镜头应用任务 5，需求 8.1、8.2）：读过几个镜头、几张图，只算有效读取。不用 ffmpeg。"""

import dataclasses
import hashlib
import json

import pytest

import shot_loader
from refcov import api
from refcov.sources import register
from refcov.store import Store

cli = shot_loader.load_cli()
IDS = ["shot-00-00-0", "shot-00-02-0", "shot-00-04-0"]


def write_list(adapter, root, video_bytes=b"fake video one" * 50, **kw):
    video = root / "v.mp4"
    video.write_bytes(video_bytes)
    st = video.stat()
    h = adapter.Header("v.mp4", hashlib.sha256(video_bytes).hexdigest(), st.st_size, st.st_mtime_ns, 60, 0.25, 0.5)
    (root / "v.shots.md").write_text(adapter.format_list(dataclasses.replace(h, **kw), [(0, 20), (20, 40), (40, 60)]),
                                     encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    adapter = shot_loader.install(tmp_path)
    monkeypatch.setattr(adapter, "extract_frame", lambda path, seconds: b"\xff\xd8fake")
    monkeypatch.chdir(tmp_path)
    write_list(adapter, tmp_path)
    store = Store(tmp_path)
    register(store, "v.shots.md", "vid", adapter="shot")
    return store, adapter


def counts(store, source=None):
    return cli.count_reads(store, source)


def test_nothing_read_yet(repo):
    store, _ = repo
    assert counts(store) == [{"source": "vid", "shots": 3, "read": 0, "reads": 0, "images": 0}]


def test_counts_distinct_shots_reads_and_images(repo):
    """同一个镜头读两次只算一个镜头，读取次数和图片张数照加。"""
    store, _ = repo
    for u in (IDS[0], IDS[2], IDS[0]):
        api.read(store, "vid", u)
    assert counts(store) == [{"source": "vid", "shots": 3, "read": 2, "reads": 3, "images": 3}]


def test_invalid_reads_are_not_counted(repo):
    """视频换了、清单重新登记后，旧读取记录失效，不再算。"""
    store, adapter = repo
    for u in IDS:
        api.read(store, "vid", u)
    assert counts(store)[0]["read"] == 3
    write_list(adapter, store.root, video_bytes=b"another video" * 60)
    register(store, "v.shots.md", "vid", adapter="shot")
    assert counts(store) == [{"source": "vid", "shots": 3, "read": 0, "reads": 0, "images": 0}]
    api.read(store, "vid", IDS[1])
    assert counts(store)[0]["read"] == 1 and counts(store)[0]["images"] == 1


def test_only_shot_sources_and_source_filter(repo):
    store, _ = repo
    (store.root / "notes.md").write_text("# 笔记\n正文\n", encoding="utf-8")
    register(store, "notes.md", "notes")
    api.read(store, "notes", "笔记")
    api.read(store, "vid", IDS[0])
    assert [r["source"] for r in counts(store)] == ["vid"]
    assert counts(store, "notes") == []
    assert counts(store, "vid")[0]["read"] == 1


def test_cli_text_and_json(repo, capsys):
    store, _ = repo
    api.read(store, "vid", IDS[1])
    assert cli.main(["count"]) == 0
    assert "vid：读过 1 / 3 个镜头，读取 1 次，送出图片 1 张" in capsys.readouterr().out
    assert cli.main(["count", "--json"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["shots_read"] == 1 and body["images"] == 1 and body["sources"][0]["source"] == "vid"
    assert cli.main(["count", "--source", "nope"]) == 0
    assert "没有登记镜头适配器的参考源（nope）" in capsys.readouterr().out


def test_count_is_read_only(repo):
    """只读：数完之后状态目录里的文件一个字节都没变。"""
    store, _ = repo
    api.read(store, "vid", IDS[0])
    snap = {p: p.read_bytes() for p in store.state_dir.rglob("*") if p.is_file()}
    cli.main(["count"])
    assert {p: p.read_bytes() for p in store.state_dir.rglob("*") if p.is_file()} == snap


def test_count_outside_a_repo_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["count"]) == 1
    assert "没有 .git" in capsys.readouterr().err
