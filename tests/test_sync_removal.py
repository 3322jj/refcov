"""移出清单的判断只比对清单（简化上手设计 1.5）：配置改过以后，不遍历仓库，也不读任何材料文件。"""

import os
from pathlib import Path

import pytest

from refcov import api
from refcov.store import Store

CONFIG_A = '[sources]\nfiles = ["docs/*.md"]\n'


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("# A\n\nalpha text\n", encoding="utf-8")
    (tmp_path / "docs" / "b.md").write_text("# B\n\nbeta text\n", encoding="utf-8")
    (tmp_path / "refcov.toml").write_text(CONFIG_A, encoding="utf-8")
    return tmp_path


def _set_config(root: Path, text: str) -> None:
    path = root / "refcov.toml"
    path.write_text(text, encoding="utf-8")
    later = os.path.getmtime(path) + 10
    os.utime(path, (later, later))


def test_removal_decision_reads_no_material_file(repo, monkeypatch):
    """性质 Y10：配置改过以后，判断哪些自动源已移出只比对清单里的 origin，不遍历仓库，也不读材料文件。"""
    store = Store(repo)
    api.sync(store)
    a_id, b_id = api.gen_id("docs/a.md"), api.gen_id("docs/b.md")
    _set_config(repo, 'mode = "strict"\n[sources]\nfiles = ["notes/*.md"]\n')
    records, sources, cfg = store.records(), api._manifest(store), store.load_config()

    def forbidden(*args, **kwargs):
        raise AssertionError("判断已移出时不应遍历仓库或读材料文件")

    with monkeypatch.context() as m:
        m.setattr(api, "_walk_files", forbidden)
        m.setattr(Path, "read_bytes", forbidden)
        inactive = api._inactive_auto(store, sources, records, cfg)
    assert {a_id, b_id} <= inactive


def test_origin_still_matching_keeps_a_source_required(repo):
    """性质 Y11：配置改过，但清单里记下的 origin 仍被通配符匹配，这个源仍必看（文件删了也一样）。"""
    store = Store(repo)
    api.sync(store)
    a_id, b_id = api.gen_id("docs/a.md"), api.gen_id("docs/b.md")
    (repo / "docs" / "b.md").unlink()
    _set_config(repo, 'mode = "strict"\n[sources]\nfiles = ["docs/*.md", "notes/*.md"]\n')
    inactive = api._inactive_auto(store, api._manifest(store), store.records(), store.load_config())
    assert a_id not in inactive and b_id not in inactive
