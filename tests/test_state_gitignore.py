"""状态目录的 .gitignore（检查点 3，Claude 的要求）：第一次写状态目录时写下，只列本机使用的文件；已经存在就不动。

用 `git check-ignore` 确认：cache/、proposals/、errors.log、log.lock、report-last.json 被忽略，
sources.json 和 log.jsonl 没被忽略（它们要提交）。
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from refcov import proposals
from refcov.store import STATE_GITIGNORE, Store

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="需要 git")


def git_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def git_ignored(root: Path, path: Path) -> bool:
    res = subprocess.run(["git", "check-ignore", "-q", "--", str(path)], cwd=root)
    assert res.returncode in (0, 1), f"git check-ignore 出错：{res.returncode}"
    return res.returncode == 0


def entries(text: str) -> list[str]:
    return [line for line in text.splitlines() if line and not line.startswith("#")]


def test_first_write_creates_a_gitignore_that_lists_only_the_local_files(tmp_path):
    """第一次建状态目录时写下 .gitignore；忽略的正好是 cache/、proposals/、errors.log、log.lock、report-last.json。"""
    store = Store(tmp_path)
    store.ensure_state_dir()
    gitignore = store.state_dir / ".gitignore"
    assert gitignore.is_file()
    assert gitignore.read_text(encoding="utf-8") == STATE_GITIGNORE
    assert entries(STATE_GITIGNORE) == ["cache/", "proposals/", "errors.log", "log.lock", "report-last.json"]
    assert not {"sources.json", "log.jsonl"} & set(entries(STATE_GITIGNORE))


@needs_git
def test_git_ignores_the_local_files_but_not_the_manifest_or_the_log(tmp_path):
    """性质（git check-ignore）：本机文件被忽略；清单和日志没有被忽略。"""
    root = git_repo(tmp_path / "repo")
    store = Store(root)
    store.ensure_state_dir()
    store.cache_dir.mkdir(exist_ok=True)
    (store.cache_dir / "abc").write_bytes(b"source text")
    (store.state_dir / "proposals").mkdir(exist_ok=True)
    (store.state_dir / "proposals" / "p-00000000.json").write_text("{}", encoding="utf-8")
    (store.state_dir / "errors.log").write_text("x", encoding="utf-8")
    store.lock_path.write_text("1", encoding="utf-8")
    (store.state_dir / "report-last.json").write_text("{}", encoding="utf-8")
    store.sources_path.write_text("{}", encoding="utf-8")
    store.log_path.write_text("", encoding="utf-8")
    for path in [store.cache_dir / "abc", store.state_dir / "proposals" / "p-00000000.json",
                 store.state_dir / "errors.log", store.lock_path, store.state_dir / "report-last.json"]:
        assert git_ignored(root, path), path
    for path in [store.sources_path, store.log_path]:
        assert not git_ignored(root, path), path


def test_an_existing_gitignore_is_never_overwritten(tmp_path):
    """性质：已经有 .gitignore 时，任何写入路径都不改它（用户自己加的内容保留）。"""
    store = Store(tmp_path)
    store.state_dir.mkdir(parents=True)
    own = "# 我自己加的\nmy-notes.txt\n"
    (store.state_dir / ".gitignore").write_text(own, encoding="utf-8")
    store.ensure_state_dir()
    store.write_sources({"version": 1, "sources": []})
    store.append("register", None, source="x", origin="docs/x.md", sha256="0", adapter="markdown",
                 units=0, changed=True)
    assert (store.state_dir / ".gitignore").read_text(encoding="utf-8") == own


def test_any_first_write_also_creates_it(tmp_path):
    """追加日志和写清单都经过 ensure_state_dir，所以第一次写任何东西都会带上 .gitignore。"""
    store = Store(tmp_path)
    store.append("register", None, source="x", origin="docs/x.md", sha256="0", adapter="markdown",
                 units=0, changed=True)
    assert (store.state_dir / ".gitignore").is_file()


def test_a_proposal_creates_the_gitignore_as_well(tmp_path):
    """提议写盘也经过 ensure_state_dir：提议目录是第一次出现时，.gitignore 也一起写下。"""
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("# A\n\nbody\n", encoding="utf-8")
    store = Store(tmp_path)
    proposals.propose(store, [{"path": "docs/a.md"}])
    assert "proposals/" in entries((store.state_dir / ".gitignore").read_text(encoding="utf-8"))
