"""命令行的 `sync` 和 `add` 的编号规则（简化上手设计 1.3、0 的第 10 条）。"""

import pytest

from refcov import cli

CONFIG = '[sources]\nfiles = ["docs/*.md"]\n'


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("# A\n\nalpha text\n", encoding="utf-8")
    (tmp_path / "docs" / "b.md").write_text("# B\n\nbeta text\n", encoding="utf-8")
    (tmp_path / "refcov.toml").write_text(CONFIG, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_sync_command_prints_what_it_registered(repo, capsys):
    """性质 Y8：`refcov sync` 打印新增的文件和编号，让用户看得出登记了什么。"""
    assert cli.main(["sync"]) == 0
    out = capsys.readouterr().out
    assert "新增，已登记：2 个" in out
    assert "docs/a.md" in out and "docs/b.md" in out


def test_add_refuses_ids_reserved_for_sources(repo, capsys):
    """性质 Y9：手动登记不能用 `f-` 开头的编号，那是 [sources] 自动登记的编号。"""
    assert cli.main(["add", "docs/a.md", "--id", "f-anything"]) == 1
    assert "f-" in capsys.readouterr().err
