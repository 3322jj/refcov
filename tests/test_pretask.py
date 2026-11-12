"""任务开工关卡（任务 16，需求 9.6、9.7，设计 7 第 6 条）。只用临时目录当仓库根目录。

PreTaskExec 的输入取自 docs/验证结果.md 第 5 项的实测：spec_name 是 tasks.md 的完整路径，
task_name 是任务那一行（编号加标题），不含子项。
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
TASKS = """# 实施计划

- [ ] 1. 引用了没读的单元
  - 先看 [ref:other/甲]
  - _需求：1_

- [x] 2. 只引用需求
  - _需求：2_

- [ ]* 3. 引用了不存在的单元 [ref:other/丙]
"""
REQS = """### 需求 1：一
出处：[ref:sample/Hooks]

### 需求 2：二
出处：[ref:other/乙]
"""
CONFIG = """{extra}
requirements = ["specs/*/requirements.md"]
spec_files = ["specs/**"]
"""
TASKS_REL = "specs/x/tasks.md"


@pytest.fixture
def store(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copyfile(SAMPLE, tmp_path / "docs" / "sample-hooks.md")
    (tmp_path / "docs" / "other.md").write_text("# 甲\n内容一\n# 乙\n内容二\n", encoding="utf-8")
    (tmp_path / "specs" / "x").mkdir(parents=True)
    (tmp_path / TASKS_REL).write_text(TASKS, encoding="utf-8")
    (tmp_path / "specs" / "x" / "requirements.md").write_text(REQS, encoding="utf-8")
    (tmp_path / "integrations" / "kiro").mkdir(parents=True)
    shutil.copyfile(REPO / "integrations" / "kiro" / "hook.py", tmp_path / "integrations" / "kiro" / "hook.py")
    s = Store(tmp_path)
    register(s, "docs/sample-hooks.md", "sample")
    register(s, "docs/other.md", "other")
    (tmp_path / "refcov.toml").write_text(CONFIG.format(extra=""), encoding="utf-8")
    return s


def recs(store, type_):
    return [r for r in store.records() if r["type"] == type_]


# ---- 核心层 api.check_task ----

def test_task_needs_own_and_requirement_refs(store):
    """设计 7 第 6 条：任务行和子项的引用，加上 `_需求：…_` 指向的需求块里的引用，都要读过。"""
    res = api.check_task(store, TASKS_REL, "1. 引用了没读的单元", "sess_a")
    assert not res["allow"] and res["found"]
    assert res["missing"] == ["other/甲", "sample/Hooks"]
    assert "进行中" in res["reason"] and "other/甲" in res["reason"]
    (rec,) = recs(store, "block")
    assert rec["gate"] == "task" and rec["session"] == "sess_a" and rec["count"] == 1
    assert rec["target"] == "specs/x/tasks.md#1. 引用了没读的单元"
    api.read(store, "other", "甲")
    api.read(store, "sample", "Hooks")
    res = api.check_task(store, TASKS_REL, "1. 引用了没读的单元", "sess_a")
    assert res["allow"] and len(recs(store, "block")) == 1


def test_task_name_variants(store):
    """需求 9.7、设计 7 第 6 条：去掉状态标记、`*` 和首尾空白；完整标题或去掉编号的标题都能找到。"""
    for name in ("2. 只引用需求", "  - [x] 2. 只引用需求 ", "只引用需求"):
        res = api.check_task(store, str(store.root / TASKS_REL), name, "s")
        assert res["found"] and res["missing"] == ["other/乙"], name


def test_unknown_unit_in_task_blocks(store):
    """需求 6.5：引用了不存在的单元，读不到，一律不达标。"""
    res = api.check_task(store, TASKS_REL, "3. 引用了不存在的单元 [ref:other/丙]", "s")
    assert not res["allow"] and res["missing"] == ["other/丙"]


def test_task_not_found_allows_and_records(store):
    """需求 9.7：找不到任务时放行，追加 task_not_found 记录（报告里单独列出）。"""
    res = api.check_task(store, TASKS_REL, "9. 没有这个任务", "sess_a")
    assert res["allow"] and not res["found"]
    (rec,) = recs(store, "task_not_found")
    assert rec["session"] == "sess_a" and rec["tasks_file"] == TASKS_REL and rec["task"] == "9. 没有这个任务"


def test_strict_citation_problems_block_task(store):
    """设计 7 第 6 条：要读的单元都读过，严格模式下出处检查不通过也拦；轻量模式不拦。"""
    (store.root / "specs" / "x" / "requirements.md").write_text(REQS + "\n### 需求 3：没出处\n正文\n",
                                                               encoding="utf-8")
    api.read(store, "other", "乙")
    res = api.check_task(store, TASKS_REL, "2. 只引用需求", "s")
    assert not res["allow"] and res["missing"] == [] and "幻影需求" in res["reason"]
    (store.root / "refcov.toml").write_text(CONFIG.format(extra='mode = "light"'), encoding="utf-8")
    assert api.check_task(store, TASKS_REL, "2. 只引用需求", "s")["allow"]


def test_second_block_asks_to_stop_and_enforce_false(store):
    api.check_task(store, TASKS_REL, "1. 引用了没读的单元", "s")
    assert "停下来，向用户说明情况" in api.check_task(store, TASKS_REL, "1. 引用了没读的单元", "s")["reason"]
    (store.root / "refcov.toml").write_text(CONFIG.format(extra="enforce = false"), encoding="utf-8")
    assert api.check_task(store, TASKS_REL, "1. 引用了没读的单元", "s")["allow"]
    assert len(recs(store, "block")) == 2


def test_unreadable_tasks_file_raises(store):
    with pytest.raises(api.CheckError):
        api.check_task(store, "specs/x/nope.md", "1. x", "s")


# ---- 钩子 pretask（只在临时目录里跑 hook.py）----

def run_hook(root, data, raw=None):
    stdin = raw if raw is not None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    env = dict(os.environ, PYTHONPATH=str(REPO))
    return subprocess.run([sys.executable, str(root / "integrations" / "kiro" / "hook.py"), "pretask"],
                          input=stdin, capture_output=True, env=env, timeout=60, cwd=root)


def pretask(root, task, session="sess_a"):
    return {"session_id": session, "hook_event_name": "PreTaskExec", "cwd": str(root),
            "spec_name": str(root / "specs" / "x" / "tasks.md"), "task_name": task}


def errors(root):
    p = root / ".refcov" / "errors.log"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_hook_blocks_then_allows(store):
    proc = run_hook(store.root, pretask(store.root, "1. 引用了没读的单元"))
    assert proc.returncode == 2 and proc.stdout == b""
    err = proc.stderr.decode("utf-8")
    assert "任务开工关卡" in err and "other/甲" in err and "进行中" in err
    api.read(store, "other", "甲")
    api.read(store, "sample", "Hooks")
    proc = run_hook(store.root, pretask(store.root, "1. 引用了没读的单元"))
    assert proc.returncode == 0 and proc.stderr == b"" and errors(store.root) == []


def test_hook_task_not_found_allows(store):
    proc = run_hook(store.root, pretask(store.root, "9. 没有这个任务"))
    assert proc.returncode == 0 and proc.stderr == b""
    assert len(recs(store, "task_not_found")) == 1


@pytest.mark.parametrize("breakage", ["bad-config", "missing-tasks-file", "no-spec-name", "bad-json"])
def test_hook_errors_allow_and_log(store, breakage):
    """用户 2026-11-12 定：找得到但出错时放行，原因写 errors.log；stdout、stderr 都为空。"""
    data, raw = pretask(store.root, "1. 引用了没读的单元"), None
    if breakage == "bad-config":
        (store.root / "refcov.toml").write_text("mode = [", encoding="utf-8")
    elif breakage == "missing-tasks-file":
        data["spec_name"] = str(store.root / "specs" / "x" / "nope.md")
    elif breakage == "no-spec-name":
        del data["spec_name"]
    else:
        raw = b"{not json"
    proc = run_hook(store.root, data, raw=raw)
    assert proc.returncode == 0 and proc.stdout == b"" and proc.stderr == b""
    assert len(errors(store.root)) == 1 and errors(store.root)[0]["event"] == "pretask"
    assert recs(store, "block") == []


def test_hook_ignores_other_events(store):
    data = {**pretask(store.root, "1. 引用了没读的单元"), "hook_event_name": "PreToolUse"}
    proc = run_hook(store.root, data)
    assert proc.returncode == 0 and recs(store, "block") == [] and errors(store.root) == []


def test_pretask_config_matches_design():
    """设计 8：refcov-pretask.json 是 PreTaskExec，没有匹配条件，命令是 hook.py pretask。"""
    (h,) = json.loads((REPO / "integrations" / "kiro" / "hooks" / "refcov-pretask.json")
                      .read_text(encoding="utf-8"))["hooks"]
    assert h["trigger"] == "PreTaskExec" and "matcher" not in h
    assert h["action"]["command"] == "python integrations/kiro/hook.py pretask"


# ---- 用户 2026-11-12 补的几处 ----

def test_reminder_text(store):
    """需求 9.7 原文：任务会停在 [~]，读完再点 Start task 前可能要用户手动改回 [ ]。"""
    reason = api.check_task(store, TASKS_REL, "1. 引用了没读的单元", "s")["reason"]
    assert "[~]" in reason and "可能要用户手动把它改回 [ ]" in reason


def test_check_task_never_writes_tasks_md(store):
    before = (store.root / TASKS_REL).read_bytes()
    for name in ("1. 引用了没读的单元", "9. 没有这个任务", "2. 只引用需求"):
        api.check_task(store, TASKS_REL, name, "s")
    assert (store.root / TASKS_REL).read_bytes() == before


def test_hook_leaves_tasks_md_unchanged(store):
    """接入层不改 tasks.md：拦截和放行前后字节都不变。"""
    before = (store.root / TASKS_REL).read_bytes()
    assert run_hook(store.root, pretask(store.root, "1. 引用了没读的单元")).returncode == 2
    assert (store.root / TASKS_REL).read_bytes() == before
    api.read(store, "other", "甲")
    api.read(store, "sample", "Hooks")
    assert run_hook(store.root, pretask(store.root, "1. 引用了没读的单元")).returncode == 0
    assert (store.root / TASKS_REL).read_bytes() == before


def test_unknown_requirement_numbers(store):
    """任务列了需求文档里没有的编号：严格模式拦，原因写清；轻量模式只提示（同需求 6.4、6.6）。"""
    (store.root / TASKS_REL).write_text(TASKS + "\n- [ ] 4. 列了不存在的需求\n  - _需求：2、7_\n", encoding="utf-8")
    api.read(store, "other", "乙")
    res = api.check_task(store, TASKS_REL, "4. 列了不存在的需求", "s")
    assert not res["allow"] and res["missing"] == [] and res["unknown_requirements"] == ["7"]
    assert "任务列了需求 7，需求文档里没有" in res["reason"]
    (store.root / "refcov.toml").write_text(CONFIG.format(extra='mode = "light"'), encoding="utf-8")
    res = api.check_task(store, TASKS_REL, "4. 列了不存在的需求", "s")
    assert res["allow"] and res["unknown_requirements"] == ["7"]


@pytest.mark.parametrize("how", ["not-in-config", "missing-file"])
def test_requirement_doc_unusable_makes_all_numbers_unknown(store, how):
    """同一文件夹的 requirements.md 不存在或不在配置里：任务列的需求编号全算找不到，严格模式拦。"""
    if how == "not-in-config":
        (store.root / "refcov.toml").write_text(CONFIG.format(extra="").replace("specs/*/requirements.md",
                                                                                "other/*.md"), encoding="utf-8")
    else:
        (store.root / "specs" / "x" / "requirements.md").unlink()
    res = api.check_task(store, TASKS_REL, "2. 只引用需求", "s")
    assert not res["allow"] and res["unknown_requirements"] == ["2"] and res["requirement_doc"] is None
    assert "任务列了需求 2，需求文档里没有" in res["reason"]


@pytest.mark.parametrize("path", ["../outside/tasks.md", "specs/x/requirements.md", "specs/x/TODO.md"])
def test_bad_tasks_path_raises(store, tmp_path_factory, path):
    """仓库外、或者文件名不是 tasks.md：抛 CheckError，不算找不到任务、不写记录。"""
    outside = tmp_path_factory.mktemp("outside")
    (outside / "tasks.md").write_text(TASKS, encoding="utf-8")
    target = str(outside / "tasks.md") if path.startswith("..") else path
    with pytest.raises(api.CheckError):
        api.check_task(store, target, "1. 引用了没读的单元", "s")
    assert recs(store, "task_not_found") == [] and recs(store, "block") == []


def test_hook_bad_tasks_path_allows_and_logs(store, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "tasks.md").write_text(TASKS, encoding="utf-8")
    data = {**pretask(store.root, "1. 引用了没读的单元"), "spec_name": str(outside / "tasks.md")}
    proc = run_hook(store.root, data)
    assert proc.returncode == 0 and proc.stderr == b""
    assert len(errors(store.root)) == 1 and recs(store, "block") == []


def test_report_lists_tasks_not_found(store):
    """报告的 tasks_not_found 单独列出（需求 9.7、设计 3.5），文字版写次数。"""
    api.check_task(store, TASKS_REL, "9. 没有这个任务", "sess_a")
    rep = api.report(store, None)
    (row,) = rep["tasks_not_found"]
    assert row["session"] == "sess_a" and row["tasks_file"] == TASKS_REL and row["task"] == "9. 没有这个任务"
    assert "任务未找到，未检查：1 次" in api.report_text(rep)
