"""登记参考源和 `refcov add`（任务 4，需求 1.1、1.4、1.5、3.4）。不连外网：网址走 127.0.0.1 上的本地服务。"""

import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from refcov import cli
from refcov.sources import RegisterError, content_sha256, register
from refcov.store import LockTimeout, Store

SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path):
    """临时目录当仓库根目录（有 `.git`，命令行要靠它认仓库根目录），样例放在 docs/ 下。"""
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copyfile(SAMPLE, tmp_path / "docs" / "sample-hooks.md")
    return tmp_path


def snapshot(root: Path) -> dict:
    """状态目录里所有文件的内容，用来确认"什么都没改"。"""
    state = root / ".refcov"
    if not state.exists():
        return {}
    return {p.relative_to(state).as_posix(): p.read_bytes() for p in state.rglob("*") if p.is_file()}


# ---- 本地文件 ----


def test_register_local_sample_units_match_headings(repo):
    """完成标志 2：清单里的单元和标题对得上；清单字段齐全（设计 3.1）；原文进缓存；日志有 register。"""
    store = Store(repo)
    r = register(store, "docs/sample-hooks.md", "sample-hooks")
    assert r.written and r.changed
    (entry,) = store.read_sources()["sources"]
    assert [(u["id"], u["title"]) for u in entry["units"]] == [
        ("sample-hooks", "sample-hooks"),
        ("Hooks", "Hooks"),
        ("退出码", "退出码"),
        ("匹配-工具名", "匹配 [工具名]"),
        ("退出码-2", "退出码"),
    ]
    assert entry["origin"] == "docs/sample-hooks.md"
    assert entry["adapter"] == "markdown"
    assert set(entry) == {"id", "origin", "fetched", "sha256", "adapter", "registered_seq", "units"}
    raw = SAMPLE.read_bytes()
    assert (repo / ".refcov" / "cache" / entry["sha256"]).read_bytes() == raw
    (rec,) = store.records()
    assert rec["type"] == "register" and rec["seq"] == entry["registered_seq"] == 1
    assert rec["session"] is None
    assert (rec["source"], rec["origin"], rec["units"], rec["changed"]) == (
        "sample-hooks", "docs/sample-hooks.md", 5, True)
    assert store.verify_chain().ok


def test_register_twice_same_content_writes_nothing(repo):
    """完成标志 2：同一内容登记两次，ID 相同；第二次什么都不写（不记 register，清单不动）。"""
    store = Store(repo)
    first = register(store, "docs/sample-hooks.md", "sample-hooks")
    before = snapshot(repo)
    second = register(store, str(repo / "docs" / "sample-hooks.md"), "sample-hooks")  # 绝对路径也一样
    assert not second.written and not second.changed
    assert [u["id"] for u in second.entry["units"]] == [u["id"] for u in first.entry["units"]]
    assert snapshot(repo) == before


def test_crlf_copy_counts_as_same_content(repo):
    """顶层校验值去掉 BOM、换行统一后再算：CRLF 版本和 LF 版本算同一内容（core.autocrlf）。"""
    store = Store(repo)
    register(store, "docs/sample-hooks.md", "sample-hooks")
    before = snapshot(repo)
    p = repo / "docs" / "sample-hooks.md"
    p.write_bytes(b"\xef\xbb\xbf" + SAMPLE.read_bytes().replace(b"\n", b"\r\n"))
    r = register(store, "docs/sample-hooks.md", "sample-hooks")
    assert not r.written
    assert snapshot(repo) == before
    assert r.entry["sha256"] == content_sha256(SAMPLE.read_text(encoding="utf-8"))


def test_changed_content_is_split_again(repo):
    """需求 1.4：校验值变了就重拆；新内容写新的缓存文件，旧的留着；registered_seq 跟着变。"""
    store = Store(repo)
    old = register(store, "docs/sample-hooks.md", "sample-hooks").entry
    p = repo / "docs" / "sample-hooks.md"
    p.write_text(SAMPLE.read_text(encoding="utf-8") + "\n## 新章节\n新内容\n", encoding="utf-8")
    r = register(store, "docs/sample-hooks.md", "sample-hooks")
    assert r.written and r.changed
    assert r.entry["sha256"] != old["sha256"]
    assert r.entry["units"][-1]["id"] == "新章节"
    assert r.entry["registered_seq"] == 2
    assert (repo / ".refcov" / "cache" / old["sha256"]).exists()
    assert (repo / ".refcov" / "cache" / r.entry["sha256"]).exists()
    assert len(store.read_sources()["sources"]) == 1


def test_same_content_new_origin_updates_origin_only(repo):
    store = Store(repo)
    register(store, "docs/sample-hooks.md", "sample-hooks")
    shutil.copyfile(SAMPLE, repo / "docs" / "moved.md")
    r = register(store, "docs/moved.md", "sample-hooks")
    assert r.written and not r.changed
    assert store.read_sources()["sources"][0]["origin"] == "docs/moved.md"
    assert store.records()[-1]["changed"] is False


def test_markdown_extension_variants(repo):
    shutil.copyfile(SAMPLE, repo / "docs" / "X.MarkDown")
    r = register(Store(repo), "docs/X.MarkDown", "x")
    assert r.entry["units"][0]["id"] == "X"  # 文件名去掉扩展名当开头那段的标题


@pytest.mark.parametrize("bad_id", ["Sample", "a_b", "a b", "", "a/b", "退出码", "a.b"])
def test_bad_source_id_is_rejected(repo, bad_id):
    with pytest.raises(RegisterError, match="参考源 ID"):
        register(Store(repo), "docs/sample-hooks.md", bad_id)
    assert snapshot(repo) == {}


def _assert_rejected_and_unchanged(repo, origin, match, **kw):
    store = Store(repo)
    register(store, "docs/sample-hooks.md", "sample-hooks")
    before = snapshot(repo)
    with pytest.raises(RegisterError, match=match):
        register(store, origin, kw.pop("source_id", "other"), **kw)
    assert snapshot(repo) == before


def test_non_markdown_file_is_rejected_and_manifest_unchanged(repo):
    """完成标志 2：非 Markdown 登记失败，报"不支持该格式"，清单没变。"""
    (repo / "docs" / "page.html").write_text("<h1>x</h1>", encoding="utf-8")
    _assert_rejected_and_unchanged(repo, "docs/page.html", "不支持该格式")


def test_non_utf8_is_rejected(repo):
    (repo / "docs" / "gbk.md").write_bytes("# 标题\n正文\n".encode("gbk"))
    _assert_rejected_and_unchanged(repo, "docs/gbk.md", "不是 UTF-8")


def test_missing_file_is_rejected(repo):
    _assert_rejected_and_unchanged(repo, "docs/nope.md", "读取失败")


def test_path_outside_repo_is_rejected(repo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "a.md"
    shutil.copyfile(SAMPLE, outside)
    _assert_rejected_and_unchanged(repo, str(outside), "要放在仓库里")
    _assert_rejected_and_unchanged(repo, f"docs/../../{outside.parent.name}/a.md", "要放在仓库里")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 上路径不分大小写")
def test_repo_check_ignores_case_on_windows(repo):
    upper = Path(str(repo).upper()) / "docs" / "sample-hooks.md"
    r = register(Store(repo), str(upper), "sample-hooks")
    assert r.entry["origin"].lower() == "docs/sample-hooks.md"


def test_symlink_pointing_outside_is_rejected(repo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "a.md"
    shutil.copyfile(SAMPLE, outside)
    link = repo / "docs" / "link.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("这台机器不允许建符号链接")
    _assert_rejected_and_unchanged(repo, "docs/link.md", "要放在仓库里")


def test_lock_timeout_changes_nothing(repo):
    """日志锁拿不到时，缓存、清单、日志都不变。"""
    store = Store(repo)
    register(store, "docs/sample-hooks.md", "sample-hooks")
    (repo / "docs" / "sample-hooks.md").write_text("# 改了\n", encoding="utf-8")
    store.lock_path.write_text("other", encoding="ascii")  # 新鲜的锁：别的进程拿着
    before = snapshot(repo)
    with pytest.raises(LockTimeout):  # 等满 2 秒
        register(store, "docs/sample-hooks.md", "sample-hooks")
    assert snapshot(repo) == before


# ---- 网址（本地 http.server，不连外网）----


class _Handler(http.server.BaseHTTPRequestHandler):
    routes = {}

    def do_GET(self):
        route = self.routes.get(self.path)
        if route is None:
            self.send_error(404, "Not Found")
            return
        ctype, body = route
        self.send_response(200)
        if ctype is not None:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    raw = SAMPLE.read_bytes()
    _Handler.routes = {
        "/docs/hooks.md": ("text/markdown; charset=utf-8", raw),
        "/docs/X-Markdown.txt": ("Text/X-Markdown", raw),
        "/raw/%E9%92%A9%E5%AD%90.md": ("text/plain; charset=utf-8", raw),
        "/raw/notes.txt": ("text/plain", raw),
        "/docs/page.md": ("text/html; charset=utf-8", b"<html>x</html>"),
        "/docs/none.md": (None, raw),
        "/docs/": ("text/markdown", raw),
        "/docs/gbk.md": ("text/markdown", "# 标题\n".encode("gbk")),
    }
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def test_register_url_markdown(repo, server):
    """网址：text/markdown（带参数也认）；origin 原样存网址；文件名取路径最后一段。"""
    store = Store(repo)
    r = register(store, f"{server}/docs/hooks.md", "kiro-hooks")
    assert r.written
    assert r.entry["origin"] == f"{server}/docs/hooks.md"
    # 开头那段借文件名 hooks，和 "# Hooks" 撞了，由它让：hooks-2（设计 4 第 5 条）
    assert [u["id"] for u in r.entry["units"]] == ["hooks-2", "Hooks", "退出码", "匹配-工具名", "退出码-2"]
    assert (repo / ".refcov" / "cache" / r.entry["sha256"]).read_bytes() == SAMPLE.read_bytes()


def test_url_content_type_case_and_x_markdown(repo, server):
    r = register(Store(repo), f"{server}/docs/X-Markdown.txt", "x")
    assert r.entry["units"][0]["id"] == "X-Markdown"


def test_text_plain_accepted_only_with_md_name_and_name_is_unquoted(repo, server):
    r = register(Store(repo), f"{server}/raw/%E9%92%A9%E5%AD%90.md", "raw")
    assert r.entry["units"][0]["title"] == "钩子"  # unquote 以后再当文件名
    _assert_rejected_and_unchanged(repo, f"{server}/raw/notes.txt", "不支持该格式")


def test_url_without_last_segment_uses_source_id(repo, server):
    r = register(Store(repo), f"{server}/docs/", "kiro-docs")
    assert r.entry["units"][0]["id"] == "kiro-docs"


@pytest.mark.parametrize("path", ["/docs/page.md", "/docs/none.md"])
def test_url_html_or_missing_type_is_rejected_even_with_md_suffix(repo, server, path):
    """完成标志 2：返回 text/html（或没有 Content-Type）时，地址以 .md 结尾也拒绝，清单没变。"""
    _assert_rejected_and_unchanged(repo, server + path, "不支持该格式")


def test_url_fetch_failure_reports_reason_and_changes_nothing(repo, server):
    """完成标志 2：抓取失败（404）时原样报原因，清单没变。"""
    _assert_rejected_and_unchanged(repo, f"{server}/missing.md", "抓取失败.*404")


def test_url_connection_refused(repo):
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # 这个端口现在没人听
    _assert_rejected_and_unchanged(repo, f"http://127.0.0.1:{port}/a.md", "抓取失败")


def test_url_non_utf8_is_rejected(repo, server):
    _assert_rejected_and_unchanged(repo, f"{server}/docs/gbk.md", "不是 UTF-8")


def test_fetch_gets_timeout_and_user_agent(repo, monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["ua"] = req.get_header("User-agent")
        seen["timeout"] = timeout
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(RegisterError, match="抓取失败.*timed out"):
        register(Store(repo), "https://example.invalid/a.md", "a")
    assert seen["timeout"] == 10 and seen["ua"].startswith("refcov/")


# ---- 命令行 ----


def test_cli_add_success_and_unchanged(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    assert cli.main(["add", "docs/sample-hooks.md", "--id", "sample-hooks"]) == 0
    out = capsys.readouterr().out
    assert "已登记 sample-hooks：5 个单元" in out and "匹配-工具名" in out and "标题：匹配 [工具名]" in out
    assert cli.main(["add", "docs/sample-hooks.md", "--id", "sample-hooks"]) == 0
    assert "内容没变，未改动" in capsys.readouterr().out


def test_cli_add_failure_exit_code_and_stderr(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    assert cli.main(["add", "docs/nope.html", "--id", "x"]) != 0
    captured = capsys.readouterr()
    assert captured.out == "" and "登记失败：不支持该格式" in captured.err
    assert not (repo / ".refcov").exists()


def test_cli_add_refuses_outside_repo_root(repo, monkeypatch, capsys):
    """在仓库的子目录里跑 refcov add：报"请在仓库根目录运行 refcov"，退出码 1，子目录和根目录都不建 .refcov。"""
    monkeypatch.chdir(repo / "docs")
    assert cli.main(["add", "sample-hooks.md", "--id", "sample-hooks"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "请在仓库根目录运行 refcov" in captured.err
    assert not (repo / "docs" / ".refcov").exists()
    assert not (repo / ".refcov").exists()


def test_cli_accepts_git_file_of_a_worktree(repo, monkeypatch, capsys):
    """worktree 里 `.git` 是文件，也算仓库根目录。"""
    (repo / ".git").rmdir()
    (repo / ".git").write_text("gitdir: /elsewhere/.git/worktrees/x\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    assert cli.main(["add", "docs/sample-hooks.md", "--id", "sample-hooks"]) == 0
    assert (repo / ".refcov" / "sources.json").exists()


def test_cli_add_in_subprocess_keeps_chinese(repo):
    """另起进程跑 `python -m refcov add`，捕获 stderr：失败时退出码非 0，中文按声明的编码能解出来。"""
    env = dict(os.environ, PYTHONPATH=str(REPO))
    proc = subprocess.run([sys.executable, "-m", "refcov", "add", "docs/x.pdf", "--id", "x"],
                          cwd=repo, capture_output=True, env=env)
    assert proc.returncode != 0 and proc.stdout == b""
    enc = "utf-8"  # Linux：Python 的默认输出编码
    if sys.platform == "win32":
        import ctypes

        import locale

        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        # 没有控制台时 cli 不改编码，Python 用默认编码（UTF-8 模式下是 utf-8）
        enc = f"cp{cp}" if cp else locale.getpreferredencoding(False)
    assert "登记失败：不支持该格式" in proc.stderr.decode(enc)
