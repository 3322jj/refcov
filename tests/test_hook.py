"""integrations/kiro/hook.py 的 post-mcp 分支（任务 6，需求 4.5、9.5、11.1、11.3）。

hook.py 按自己的位置算仓库根目录，所以测试把它复制到 <临时目录>/integrations/kiro/hook.py，
临时目录就是仓库根目录；核心层经 PYTHONPATH 从真实仓库 import。再用 subprocess 从 stdin 喂 JSON。

样例的结构取自 experiments/mcp-posttooluse/logs/hooks.jsonl（2026-11-10 Kiro 真发来的 PostToolUse）：
键是 cwd、hook_event_name、session_id、tool_input、tool_name、tool_response，tool_response 是字符串。
那份日志只存了 str(tool_response)[:300]，所以对象和列表两种形状是按 MCP 的返回格式构造的。
"""

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from refcov import api
from refcov.sources import register
from refcov.store import Store

REPO = Path(__file__).resolve().parents[1]
SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"
PROBE_LOG = REPO / "experiments" / "mcp-posttooluse" / "logs" / "hooks.jsonl"
REAL = [r for r in map(json.loads, PROBE_LOG.read_text(encoding="utf-8").splitlines())
        if r.get("event") == "PostToolUse" and r.get("tool_name") == "mcp_refcov_read_unit"]
SESSION_A = REAL[0]["session_id"]  # sess_da80f038-…（会话 A）
SESSION_B = REAL[-1]["session_id"]  # sess_cc2f272f-…（会话 B）


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "integrations" / "kiro").mkdir(parents=True)
    shutil.copyfile(REPO / "integrations" / "kiro" / "hook.py", tmp_path / "integrations" / "kiro" / "hook.py")
    shutil.copyfile(SAMPLE, tmp_path / "docs" / "sample-hooks.md")
    register(Store(tmp_path), "docs/sample-hooks.md", "sample")
    return tmp_path


def payload(root, tool_response, session=SESSION_A, tool="mcp_refcov_read_unit", tool_input=None,
            event="PostToolUse"):
    """和真实 PostToolUse 输入同样的键。"""
    return {"cwd": str(root), "hook_event_name": event, "session_id": session,
            "tool_input": tool_input if tool_input is not None else {"source": "sample", "unit": "Hooks"},
            "tool_name": tool, "tool_response": tool_response}


def run_hook(root, data, arg="post-mcp", raw=None, cwd=None):
    stdin = raw if raw is not None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    env = dict(os.environ, PYTHONPATH=str(REPO))
    return subprocess.run([sys.executable, str(root / "integrations" / "kiro" / "hook.py"), arg],
                          input=stdin, capture_output=True, env=env, timeout=60, cwd=cwd or root)


def errors(root):
    p = root / ".refcov" / "errors.log"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def sessions(root):
    return [(r["call"], r["session"]) for r in Store(root).records() if r["type"] == "session"]


def test_real_samples_have_the_expected_shape():
    """真实样例：4 次 MCP 调用都是 PostToolUse、工具名 mcp_refcov_read_unit、tool_response 转成字符串后是纯文字。"""
    assert len(REAL) == 4  # 会话 A 3 次 + 会话 B 1 次（另一条 PostToolUse 是 fs_write）
    for r in REAL:
        assert r["keys"] == ["cwd", "hook_event_name", "session_id", "tool_input", "tool_name", "tool_response"]
        assert not r["tool_response"].startswith(("{", "["))


def test_string_response_attaches_session(repo):
    """tool_response 是字符串（真实样例的形状）：按最后一行的调用编号补记会话，退出码 0，stdout 为空。"""
    r = api.read(Store(repo), "sample", "Hooks")
    proc = run_hook(repo, payload(repo, r.text()))
    assert proc.returncode == 0 and proc.stdout == b""
    assert sessions(repo) == [(r.call, SESSION_A)]
    assert Store(repo).verify_chain().ok
    assert errors(repo) == []


@pytest.mark.parametrize("shape", ["object", "content-object", "list-of-blocks", "list-of-strings"])
def test_object_and_list_responses(repo, shape):
    r = api.read(Store(repo), "sample", "Hooks")
    text = r.text()
    head, last = text.rsplit("\n", 1)
    resp = {
        "object": {"type": "text", "text": text},
        "content-object": {"content": [{"type": "text", "text": text}], "isError": False},
        "list-of-blocks": [{"type": "text", "text": head}, {"type": "text", "text": last}],
        "list-of-strings": [head, last],
    }[shape]
    assert run_hook(repo, payload(repo, resp)).returncode == 0
    assert sessions(repo) == [(r.call, SESSION_A)]
    assert errors(repo) == []


@pytest.mark.parametrize("sample", REAL, ids=lambda s: s["time"])
def test_real_probe_responses_without_call_line_do_nothing(repo, sample):
    """真实样例原文（试验服务的返回没有调用编号）：什么都不做，不写 errors.log。"""
    before = Store(repo).log_path.read_bytes()
    data = {k: sample[k] for k in ("session_id", "tool_input", "tool_name", "tool_response")}
    data.update(cwd=str(repo), hook_event_name=sample["event"])
    assert run_hook(repo, data).returncode == 0
    assert Store(repo).log_path.read_bytes() == before and errors(repo) == []


def test_list_units_and_failed_read_do_nothing(repo):
    """list_units 和出错的 read_unit 没有调用编号：什么都不做，不写 errors.log。"""
    before = Store(repo).log_path.read_bytes()
    listed = f"sample/Hooks\tHooks\tsection\t没看过\n\n{api.HINT}"
    assert run_hook(repo, payload(repo, listed, tool="mcp_refcov_list_units", tool_input={})).returncode == 0
    failed = {"content": [{"type": "text", "text": "参考源 sample 里没有单元 '退出'。"}], "isError": True}
    assert run_hook(repo, payload(repo, failed)).returncode == 0
    assert Store(repo).log_path.read_bytes() == before and errors(repo) == []


@pytest.mark.parametrize("data_change", [
    {"tool_name": "fs_write"}, {"tool_name": "refcov::read_unit"}, {"tool_name": "x_mcp_refcov_read_unit"},
    {"hook_event_name": "PreToolUse"},
])
def test_other_tools_and_events_are_ignored(repo, data_change):
    """需求 9.5：脚本里再核对一次工具名和事件，不是 RefCov MCP 工具的 PostToolUse 就什么都不做。"""
    r = api.read(Store(repo), "sample", "Hooks")
    data = {**payload(repo, r.text()), **data_change}
    assert run_hook(repo, data).returncode == 0
    assert sessions(repo) == [] and errors(repo) == []


def test_last_line_must_be_exact(repo):
    r = api.read(Store(repo), "sample", "Hooks")
    assert run_hook(repo, payload(repo, r.text() + " ")).returncode == 0
    assert run_hook(repo, payload(repo, r.text() + "\n其他")).returncode == 0
    assert sessions(repo) == [] and errors(repo) == []
    assert run_hook(repo, payload(repo, r.text() + "\n")).returncode == 0  # 只去末尾换行
    assert sessions(repo) == [(r.call, SESSION_A)]


def test_two_sessions_are_kept_apart(repo):
    a = api.read(Store(repo), "sample", "Hooks")
    b = api.read(Store(repo), "sample", "退出码")
    run_hook(repo, payload(repo, a.text(), session=SESSION_A))
    run_hook(repo, payload(repo, b.text(), session=SESSION_B, tool_input={"source": "sample", "unit": "退出码"}))
    assert sessions(repo) == [(a.call, SESSION_A), (b.call, SESSION_B)]


def test_duplicate_and_conflicting_session(repo):
    r = api.read(Store(repo), "sample", "Hooks")
    run_hook(repo, payload(repo, r.text()))
    run_hook(repo, payload(repo, r.text()))  # 同一会话再来一次：不写，不记错误
    assert sessions(repo) == [(r.call, SESSION_A)] and errors(repo) == []
    assert run_hook(repo, payload(repo, r.text(), session=SESSION_B)).returncode == 0
    assert sessions(repo) == [(r.call, SESSION_A)]
    (err,) = errors(repo)
    assert "已经补记成会话" in err["reason"]


def test_call_without_read_record_is_logged(repo):
    text = f"正文\n\n{api.HINT}\nrefcov-call: c-99"
    assert run_hook(repo, payload(repo, text)).returncode == 0
    assert sessions(repo) == []
    (err,) = errors(repo)
    assert err["call"] == "c-99" and "没有这个调用编号" in err["reason"]


def test_arguments_not_matching_read_record_are_logged(repo):
    r = api.read(Store(repo), "sample", "Hooks")
    run_hook(repo, payload(repo, r.text(), tool_input={"source": "sample", "unit": "退出码"}))
    assert sessions(repo) == []
    assert "不一致" in errors(repo)[0]["reason"]


def test_parallel_hooks_all_attach(repo):
    """并行读取时几个钩子同时抢锁：都能补记上，链完整，没有重复。"""
    store = Store(repo)
    reads = [api.read(store, "sample", u) for u in ("Hooks", "退出码", "匹配-工具名", "退出码-2", "sample-hooks")]
    with ThreadPoolExecutor(len(reads)) as pool:
        procs = list(pool.map(lambda r: run_hook(repo, payload(repo, r.text(), tool_input={})), reads))
    assert all(p.returncode == 0 for p in procs)
    assert sorted(sessions(repo)) == sorted((r.call, SESSION_A) for r in reads)
    assert store.verify_chain().ok and errors(repo) == []


def test_lock_timeout_is_logged_and_allowed(repo):
    """2 秒拿不到锁：退出码 0，记 errors.log，日志不变，不卡住。"""
    store = Store(repo)
    r = api.read(store, "sample", "Hooks")
    store.lock_path.write_text("other", encoding="ascii")
    before = store.log_path.read_bytes()
    proc = run_hook(repo, payload(repo, r.text()))
    assert proc.returncode == 0 and proc.stdout == b""
    assert store.log_path.read_bytes() == before
    assert errors(repo)[0]["error"] == "LockTimeout"


@pytest.mark.parametrize("raw", [b"", b"not json", b"[1, 2]"])
def test_bad_input_is_allowed_and_logged(repo, raw):
    proc = run_hook(repo, None, raw=raw)
    assert proc.returncode == 0 and proc.stdout == b""
    assert len(errors(repo)) == 1


def test_invalid_utf8_is_decoded_with_replacement(repo):
    """stdin 按字节读、按 UTF-8 解码（坏字节换成 U+FFFD），不崩。这里解出的对象没有事件名，静默放行。"""
    proc = run_hook(repo, None, raw=b'{"x": "\xff\xfe"}')
    assert proc.returncode == 0 and proc.stdout == b"" and errors(repo) == []


def test_missing_session_id_is_logged(repo):
    r = api.read(Store(repo), "sample", "Hooks")
    data = payload(repo, r.text())
    del data["session_id"]
    assert run_hook(repo, data).returncode == 0
    assert sessions(repo) == [] and "session_id" in errors(repo)[0]["reason"]


def test_unknown_event_argument_is_logged(repo):
    assert run_hook(repo, {}, arg="nope").returncode == 0
    assert errors(repo)[0]["reason"] == "不认识的事件参数"


def test_root_comes_from_script_location_not_cwd(repo, tmp_path_factory):
    """当前目录不是仓库根目录时，仍按 hook.py 的位置找到根目录。"""
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    r = api.read(Store(repo), "sample", "Hooks")
    assert run_hook(repo, payload(repo, r.text()), cwd=elsewhere).returncode == 0
    assert sessions(repo) == [(r.call, SESSION_A)]
    assert not (elsewhere / ".refcov").exists()


def test_errors_log_is_ascii_escaped(repo):
    text = f"正文\n\n{api.HINT}\nrefcov-call: c-99"
    run_hook(repo, payload(repo, text))
    raw = (repo / ".refcov" / "errors.log").read_bytes()
    assert raw.isascii()  # 原因里的中文全部转义
    assert "日志里没有" in json.loads(raw)["reason"]


def test_hook_config_matches_design():
    """refcov-post-mcp.json：格式照抄实测能用的试验钩子，匹配 ^mcp_refcov_，命令调 hook.py post-mcp。"""
    cfg = json.loads((REPO / "integrations" / "kiro" / "hooks" / "refcov-post-mcp.json").read_text(encoding="utf-8"))
    probe = json.loads((REPO / "experiments" / "mcp-posttooluse" / "hooks-disabled" / "probe-mcp-post.json")
                       .read_text(encoding="utf-8"))
    (hook,) = cfg["hooks"]
    assert cfg["version"] == probe["version"] == "v1"
    assert set(hook) == set(probe["hooks"][0]) and set(hook["action"]) == set(probe["hooks"][0]["action"])
    assert hook["trigger"] == "PostToolUse" and hook["matcher"] == "^mcp_refcov_"
    assert hook["action"] == {"type": "command", "command": "python integrations/kiro/hook.py post-mcp",
                              "timeout": 10}
