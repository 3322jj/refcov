"""需求 1.3：`.gitignore` 不得忽略 `.kiro` 目录及其任何内容（设计 2）。

对 `.kiro` 下所有文件（已跟踪和未跟踪的都算，直接遍历磁盘）加上几个构造路径，
跑 `git check-ignore -v --no-index`，按输出里命中的规则判断：

- 规则来自某个 `.gitignore` 文件、且不是否定规则（`!pattern`）→ 失败。
- 规则来自 `.git/info/exclude`（或全局 excludesFile）→ 不算失败。本机的
  `.kiro/settings/mcp.json` 是用户有意写进 exclude 的。
- 否定规则命中时 `-v` 也会输出、退出码也是 0，但它的意思是"不忽略"，不算失败。
  所以不能只看退出码。
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# CI 上 .kiro 下可能缺某些文件；这几个构造路径保证测试总有输入。
CONSTRUCTED = [
    ".kiro/specs/x/requirements.md",
    ".kiro/hooks/x.json",
    ".kiro/settings/mcp.json",
]


def _git() -> str:
    git = shutil.which("git")
    if git is None:
        pytest.fail("找不到 git：需求 1.3 的检查要用 git check-ignore，不能跳过")
    return git


def kiro_paths(root: Path) -> list[str]:
    """`.kiro` 下的所有文件（相对 root、`/` 分隔）加上构造路径，去重排序。"""
    found = set(CONSTRUCTED)
    kiro = root / ".kiro"
    for dirpath, _dirs, files in os.walk(kiro):
        for name in files:
            found.add((Path(dirpath) / name).relative_to(root).as_posix())
    return sorted(found)


def gitignore_hits(root: Path, paths: list[str]) -> list[tuple[str, str, str]]:
    """返回被某个 `.gitignore` 里的非否定规则命中的 (路径, 规则来源:行号, 规则)。"""
    proc = subprocess.run(
        [_git(), "check-ignore", "-v", "-z", "--no-index", "--non-matching", "--stdin"],
        cwd=root,
        input="\0".join(paths).encode("utf-8") + b"\0",
        capture_output=True,
    )
    # 退出码 0：至少一个路径命中；1：都没命中；其他：git 出错。
    if proc.returncode not in (0, 1):
        pytest.fail(
            "git check-ignore 出错（退出码 %d）：%s"
            % (proc.returncode, proc.stderr.decode("utf-8", "replace"))
        )
    fields = proc.stdout.decode("utf-8").split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    # -z -v 的输出：每个路径 4 个字段 <来源> <行号> <规则> <路径>；没命中时前三个为空。
    if len(fields) != 4 * len(paths):
        pytest.fail("git check-ignore 输出无法解析：%r" % proc.stdout[:500])
    hits = []
    for i in range(0, len(fields), 4):
        source, line, pattern, path = fields[i : i + 4]
        if not source:
            continue
        if Path(source).name != ".gitignore":
            continue  # .git/info/exclude 或全局 excludesFile，不归需求 1.3 管
        if pattern.startswith("!"):
            continue  # 否定规则：命中意味着"不忽略"
        hits.append((path, f"{source}:{line}", pattern))
    return hits


def test_gitignore_does_not_ignore_kiro():
    """需求 1.3：仓库的 .gitignore 没有忽略 .kiro 下的任何文件。"""
    paths = kiro_paths(REPO)
    assert set(CONSTRUCTED) <= set(paths)
    hits = gitignore_hits(REPO, paths)
    assert hits == [], "这些 .kiro 路径被 .gitignore 忽略了：%r" % hits


def _init_repo(root: Path) -> None:
    subprocess.run([_git(), "init", "-q"], cwd=root, check=True)


def test_check_catches_kiro_rule_in_gitignore(tmp_path):
    """检查本身有效：.gitignore 里忽略 .kiro（含子目录 .gitignore）会被报出来。"""
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text(".kiro/hooks/\n", encoding="utf-8")
    (tmp_path / ".kiro" / "specs").mkdir(parents=True)
    (tmp_path / ".kiro" / "specs" / ".gitignore").write_text("*.md\n", encoding="utf-8")
    (tmp_path / ".kiro" / "steering").mkdir()
    (tmp_path / ".kiro" / "steering" / "规则 [中文].md").write_text("x", encoding="utf-8")
    hits = gitignore_hits(tmp_path, kiro_paths(tmp_path))
    hit_paths = {h[0] for h in hits}
    assert ".kiro/hooks/x.json" in hit_paths
    assert ".kiro/specs/x/requirements.md" in hit_paths
    assert ".kiro/steering/规则 [中文].md" not in hit_paths


def test_exclude_and_negation_do_not_fail(tmp_path):
    """来自 .git/info/exclude 的命中不算失败；.gitignore 里的否定规则不算失败。"""
    _init_repo(tmp_path)
    (tmp_path / ".git" / "info").mkdir(exist_ok=True)
    (tmp_path / ".git" / "info" / "exclude").write_text(
        ".kiro/settings/mcp.json\n", encoding="utf-8"
    )
    (tmp_path / ".gitignore").write_text("*.json\n!.kiro/**\n", encoding="utf-8")
    assert gitignore_hits(tmp_path, kiro_paths(tmp_path)) == []
