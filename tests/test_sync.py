"""`[sources]` 的同步（简化上手设计 1.2、1.3、1.5）。编号和同步的性质用 Hypothesis；仓库行为用临时目录。"""

import os
import string
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from refcov import api
from refcov.store import Store

CONFIG_A = '[sources]\nfiles = ["docs/*.md"]\n'
CONFIG_B = '[sources]\nfiles = ["notes/*.md"]\n'

# 路径段里要有中文、空格和方括号（测试约定：生成数据包含这些字符）
SEG = st.text(alphabet=string.ascii_letters + string.digits + " 中文[]()_-.", min_size=1, max_size=12)
PATH = st.lists(SEG, min_size=1, max_size=3).map(lambda parts: "/".join(parts) + ".md")


@given(PATH)
def test_generated_ids_are_valid_and_stable(path):
    """性质 Y6：编号符合 `f-…-六位十六进制`，只含 a–z、0–9 和 `-`，没有空白和方括号；同一路径每次得到同一个编号。"""
    gid = api.gen_id(path)
    assert api.AUTO_ID.fullmatch(gid), gid
    assert gid == api.gen_id(path)
    assert not any(ch in gid for ch in " []()")


@given(PATH, PATH)
def test_different_paths_get_different_ids(p, q):
    """性质 Y7：小写后不同的两个路径得到不同编号（哈希后缀把它们分开）。"""
    if p.lower() != q.lower():
        assert api.gen_id(p) != api.gen_id(q)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "notes").mkdir()
    (tmp_path / "docs" / "a.md").write_text("# A\n\nalpha text\n", encoding="utf-8")
    (tmp_path / "docs" / "b.md").write_text("# B\n\nbeta text\n", encoding="utf-8")
    (tmp_path / "notes" / "n.md").write_text("# N\n\nnote text\n", encoding="utf-8")
    (tmp_path / "refcov.toml").write_text(CONFIG_A, encoding="utf-8")
    return tmp_path


def _set_config(root: Path, text: str, mtime: float) -> None:
    (root / "refcov.toml").write_text(text, encoding="utf-8")
    os.utime(root / "refcov.toml", (mtime, mtime))


def _required_sources(root: Path) -> set:
    return {src for src, _ in api.gather(Store(root)).required.units}


def test_second_sync_registers_nothing(repo):
    """性质 Y1：同步两次，第二次不登记、不改动（幂等）；只多一条 sync 记录。"""
    store = Store(repo)
    first = api.sync(store)
    assert len(first["registered"]) == 2 and first["wrote"]
    before = len(store.records())
    second = api.sync(store)
    assert second["new"] == [] and second["changed"] == [] and second["registered"] == []
    assert len(store.records()) == before + 1


def test_changed_file_is_listed_and_reregistered(repo):
    """性质 Y2：内容变了的文件列在"改动"里，同步后不再列出（需求 1.4 的旧读取由校验值失效）。"""
    store = Store(repo)
    api.sync(store)
    (repo / "docs" / "a.md").write_text("# A\n\nalpha changed\n", encoding="utf-8")
    assert [c["file"] for c in api.plan_sync(store)["changed"]] == ["docs/a.md"]
    api.sync(store)
    assert api.plan_sync(store)["changed"] == []


def test_deleted_file_stays_required_while_config_is_unchanged(repo):
    """性质 Y3：文件删了、配置没改过，它的源仍必看（简化上手设计 1.5）。"""
    store = Store(repo)
    api.sync(store)
    b_id = api.gen_id("docs/b.md")
    assert b_id in _required_sources(repo)
    (repo / "docs" / "b.md").unlink()
    assert b_id in _required_sources(repo)
    assert api.plan_sync(store)["missing"] == [b_id]


def test_config_change_removes_sources_that_no_longer_match(repo):
    """性质 Y4：配置改过之后，不再匹配的源不再必看；配置没改过时不会因为别的原因移出（简化上手设计 1.5）。"""
    store = Store(repo)
    api.sync(store)
    a_id = api.gen_id("docs/a.md")
    assert a_id in _required_sources(repo)
    _set_config(repo, CONFIG_B, mtime=os.path.getmtime(repo / "refcov.toml") + 10)
    assert a_id not in _required_sources(repo)
    assert a_id in api.plan_sync(store)["removed"]


def test_without_sources_sync_writes_nothing(repo):
    """性质 Y5：没有 [sources]、也没有 sync 记录时，同步什么都不写（现有配置不受影响）。"""
    (repo / "refcov.toml").write_text('mode = "strict"\n', encoding="utf-8")
    store = Store(repo)
    result = api.sync(store)
    assert result["wrote"] is False and result["registered"] == []
    assert store.records() == []
