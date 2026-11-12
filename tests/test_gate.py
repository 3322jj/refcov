"""写文件关卡和拦截次数提示（任务 15，需求 9.1、11.2、17.1、17.2）。

只用临时目录当仓库根目录（用户 2026-11-12 定），不碰真实仓库的日志。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from refcov import api
from refcov.sources import register
from refcov.store import Store

REPO = Path(__file__).resolve().parents[1]
SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"  # 5 个单元
CONFIG = """{extra}
requirements = ["specs/*/requirements.md"]
spec_files = ["specs/**"]

[[scope]]
paths = ["integrations/kiro/**"]
sources = ["other"]
"""
OTHER = [("other", "甲"), ("other", "乙")]
TARGET = "integrations/kiro/hook.py"


@pytest.fixture
def store(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copyfile(SAMPLE, tmp_path / "docs" / "sample-hooks.md")
    (tmp_path / "docs" / "other.md").write_text("# 甲\n内容一\n# 乙\n内容二\n", encoding="utf-8")
    (tmp_path / "integrations" / "kiro").mkdir(parents=True)
    shutil.copyfile(REPO / "integrations" / "kiro" / "hook.py", tmp_path / "integrations" / "kiro" / "hook.py")
    s = Store(tmp_path)
    register(s, "docs/sample-hooks.md", "sample")
    register(s, "docs/other.md", "other")
    (tmp_path / "refcov.toml").write_text(CONFIG.format(extra=""), encoding="utf-8")
    return s


def blocks(store):
    return [r for r in store.records() if r["type"] == "block"]


# ---- 核心层 api.check_write ----

def test_blocks_until_read_then_allows(store):
    """完成标志：没读完时写 integrations/kiro/** 被拦，读完后放行。"""
    res = api.check_write(store, TARGET, "sess_a")
    assert not res["allow"] and res["count"] == 1
    assert "other/甲" in res["reason"] and "other/乙" in res["reason"]
    for s, u in OTHER:
        api.read(store, s, u)
    res = api.check_write(store, TARGET, "sess_a")
    assert res["allow"] and res["reason"] is None
    assert len(blocks(store)) == 1  # 放行不写记录


def test_block_record_fields(store):
    """设计 3.2：block 记录带 gate、target、count、missing、session。"""
    api.check_write(store, str(store.root / "integrations" / "kiro" / "hook.py"), "sess_a")
    (rec,) = blocks(store)
    assert rec["gate"] == "write" and rec["target"] == TARGET and rec["session"] == "sess_a"
    assert rec["count"] == 1 and rec["missing"] == ["other/甲", "other/乙"]


def test_second_block_asks_to_stop(store):
    """需求 11.2：同一会话同一目标第 2 次起加"停下来，向用户说明情况"；别的会话、别的目标重新数。"""
    first = api.check_write(store, TARGET, "sess_a")
    assert "停下来" not in first["reason"]
    second = api.check_write(store, TARGET, "sess_a")
    assert second["count"] == 2 and "停下来，向用户说明情况" in second["reason"]
    assert api.check_write(store, TARGET, "sess_b")["count"] == 1
    assert api.check_write(store, "integrations/kiro/other.py", "sess_a")["count"] == 1
    assert api.check_write(store, "Integrations\\Kiro\\hook.py", "sess_a")["count"] == 3  # 同一目标的别的写法


def test_exempt_and_enforce_false_allow(store):
    """需求 8.3、17.1：豁免路径放行；enforce = false 时一律放行，不写 block 记录。"""
    assert api.check_write(store, "docs/DEVLOG.md", "sess_a")["allow"]
    (store.root / "refcov.toml").write_text(CONFIG.format(extra="enforce = false"), encoding="utf-8")
    res = api.check_write(store, TARGET, "sess_a")
    assert res["allow"] and res["enforce"] is False
    assert blocks(store) == []
    assert api.report_text(api.report(store, None)).splitlines()[0].startswith("RefCov 关卡已关闭")


def test_reason_lists_first_20_and_total(store):
    """拦截原因写清还差的单元：前 20 个和总数。"""
    (store.root / "docs" / "many.md").write_text("".join(f"# 节{i}\n正文\n" for i in range(25)), encoding="utf-8")
    register(store, "docs/many.md", "many")
    res = api.check_write(store, "refcov/api.py", "sess_a")  # 没有 scope：全部参考源
    assert "还差 32 个" in res["reason"] and "只列前 20 个" in res["reason"]
    assert res["reason"].count("many/节") == 20 - 7  # 前 20 个里有 sample 5 个、other 2 个


def test_reason_names_citation_problems(store):
    """拦截原因写清幻影需求、无效引用；单元都读了也因此被拦（严格模式）。"""
    (store.root / "specs" / "x").mkdir(parents=True)
    (store.root / "specs" / "x" / "requirements.md").write_text(
        "### 需求 1：没出处\n正文\n\n### 需求 2：错引用\n出处：[ref:other/丙]\n", encoding="utf-8")
    for s, u in OTHER:
        api.read(store, s, u)
    res = api.check_write(store, TARGET, "sess_a")
    assert not res["allow"]
    assert "幻影需求" in res["reason"] and "需求 1" in res["reason"]
    assert "无效引用" in res["reason"] and "other/丙" in res["reason"]
    assert api.check_write(store, "specs/x/requirements.md", "sess_a")["allow"] is False  # 全部参考源没读完


def test_reason_names_config_problems(store):
    (store.root / "refcov.toml").write_text(CONFIG.format(extra="").replace('["other"]', '["othr"]'),
                                           encoding="utf-8")
    res = api.check_write(store, TARGET, "sess_a")
    assert not res["allow"] and "othr" in res["reason"]


def test_check_write_reads_no_body(store):
    """需求 8.5：只看路径。check_write 没有正文参数。"""
    import inspect

    assert list(inspect.signature(api.check_write).parameters) == ["store", "path", "session"]


# ---- 钩子 pre-write：先保护，再关卡（只在临时目录里跑 hook.py）----

def run_hook(root, data, raw=None):
    stdin = raw if raw is not None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    env = dict(os.environ, PYTHONPATH=str(REPO))
    return subprocess.run([sys.executable, str(root / "integrations" / "kiro" / "hook.py"), "pre-write"],
                          input=stdin, capture_output=True, env=env, timeout=60, cwd=root)


def write(path, session="sess_a", tool="fs_write"):
    return {"hook_event_name": "PreToolUse", "session_id": session, "tool_name": tool,
            "tool_input": {"path": path, "text": "正文不影响结论"}}


def test_hook_blocks_then_allows(store):
    proc = run_hook(store.root, write(TARGET))
    assert proc.returncode == 2 and proc.stdout == b""
    err = proc.stderr.decode("utf-8")
    assert "写文件关卡" in err and "other/甲" in err
    for s, u in OTHER:
        api.read(store, s, u)
    proc = run_hook(store.root, write(TARGET, tool="str_replace"))
    assert proc.returncode == 0 and proc.stderr == b""
    assert [r["count"] for r in blocks(store)] == [1]


def test_hook_second_block_and_by_session(store):
    run_hook(store.root, write(TARGET))
    proc = run_hook(store.root, write(TARGET))
    assert proc.returncode == 2 and "停下来，向用户说明情况" in proc.stderr.decode("utf-8")
    api.attach_session(store, api.read(store, "other", "甲").call, "sess_a")
    rows = {b["session"]: b for b in api.report(store, "sess_a")["by_session"]}
    assert rows["sess_a"]["blocks"] == 2


def test_hook_protection_runs_first(store):
    """保护检查在关卡之前：写配置被保护拦下，只有 protect 记录，没有 block 记录。"""
    proc = run_hook(store.root, write("refcov.toml"))
    assert proc.returncode == 2 and "RefCov 保护" in proc.stderr.decode("utf-8")
    assert blocks(store) == [] and [r["type"] for r in store.records()][-1] == "protect"


def test_hook_gate_error_allows(store):
    """需求 11.1：关卡（不是保护检查）出错时放行，原因记 errors.log，stdout、stderr 都为空。"""
    (store.root / "refcov.toml").write_text("mode = [", encoding="utf-8")
    proc = run_hook(store.root, write(TARGET))
    assert proc.returncode == 0 and proc.stdout == b"" and proc.stderr == b""
    log = (store.root / ".refcov" / "errors.log").read_text(encoding="utf-8")
    assert "pre-write" in log and "mode = [" not in log


def test_hook_exempt_and_enforce_false(store):
    assert run_hook(store.root, write("docs/DEVLOG.md")).returncode == 0
    (store.root / "refcov.toml").write_text(CONFIG.format(extra="enforce = false"), encoding="utf-8")
    assert run_hook(store.root, write(TARGET)).returncode == 0
    assert run_hook(store.root, write(".refcov/log.jsonl")).returncode == 2  # 保护照常（需求 17.1）
    assert blocks(store) == []
