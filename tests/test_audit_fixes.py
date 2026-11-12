"""外部审计（409afc2）发现的解析和记录问题的回归测试。只用临时目录当仓库根目录。

- 第 1 项：缩进的任务行、子任务（设计 7 第 6 条，需求 9.6）；状态标记认方括号里的任意单个字符（偏离需求 9.6 原文）。
- 第 2 项：同号需求块的引用合并，不是后一块覆盖前一块。
- 第 3 项：已经算出不达标之后，记录这一步出任何错都照样拦（会话 ID 含孤立代理字符）。
- 第 4 项：配置里把列表写成字符串时当成只有这一项的列表，并在"配置写错"里列出（偏离需求原文）。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from refcov import api, citations
from refcov.sources import register
from refcov.store import Store, path_matches

REPO = Path(__file__).resolve().parents[1]
SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"  # 5 个单元，含 Hooks
SURROGATE = "audit\ud800"  # JSON 里写成 "audit\ud800"，Python 能解码，UTF-8 编码不了

# 父任务自己引用 other/甲；子任务 1.1 只经需求 1 引用 sample/Hooks；兄弟任务 1.2 引用 other/乙。
# 任务 2 下有一个和 1.1 同名的子任务；最后一行顶格的说明不属于任何任务。
TASKS = """# 实施计划

- [ ] 1. 父任务
  - 父任务自己要读 [ref:other/甲]
  - [ ] 1.1 子任务
    - _需求：1_
  - [ ] 1.2 兄弟任务
    - 兄弟要读 [ref:other/乙]

- [ ] 2. 另一个父任务
  - [ ] 2.1 子任务
    - [ref:sample/匹配-工具名]

说明：顶格的非任务行 [ref:sample/退出码]
"""
REQS = """### 需求 1：一
出处：[ref:sample/Hooks]
"""
CONFIG = """{extra}
requirements = ["specs/*/requirements.md"]
spec_files = ["specs/**"]

[[scope]]
paths = ["integrations/kiro/**"]
sources = ["other"]
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


def refs_of(tasks_text, name, reqs_text=REQS):
    tasks = citations.parse_tasks(tasks_text)
    task = citations.find_task(tasks, name)
    assert task is not None, name
    refs, unknown = citations.task_refs(task, citations.parse_requirements(reqs_text))
    return [citations.ref_str(r) for r in refs], unknown


# ---- 第 1 项：缩进的任务行和子任务 ----

def test_child_task_found_with_own_refs_only():
    """子任务能找到；只算它自己这一行和它自己的子项（这里是需求 1 的引用），不含父任务和兄弟任务的。"""
    assert refs_of(TASKS, "1.1 子任务") == (["sample/Hooks"], [])
    assert refs_of(TASKS, "1.2 兄弟任务") == (["other/乙"], [])


def test_parent_includes_all_children():
    """父任务 = 自己的引用 + 全部子任务的（宁可多要求，设计 7 第 6 条"任务行和子项"）。"""
    refs, unknown = refs_of(TASKS, "1. 父任务")
    assert sorted(refs) == sorted(["other/甲", "sample/Hooks", "other/乙"]) and unknown == []
    task = citations.find_task(citations.parse_tasks(TASKS), "1. 父任务")
    assert task.requirements == ["1"]  # 子任务的 _需求：…_ 也算父任务的


def test_top_level_line_ends_all_tasks():
    """顶格的非任务行照旧结束所有任务：它里面的引用不算给任何任务。"""
    for t in citations.parse_tasks(TASKS):
        assert ("sample", "退出码") not in t.refs, t.title


def test_same_child_title_under_two_parents():
    """不同父任务下的同名子任务：按带编号的完整标题能找到对的那个。"""
    assert refs_of(TASKS, "2.1 子任务") == (["sample/匹配-工具名"], [])
    assert refs_of(TASKS, "1.1 子任务") == (["sample/Hooks"], [])


def test_full_title_wins_over_earlier_short_title():
    """先在全部任务里按完整标题找，找不到再按去掉编号的标题找：前面同名的短标题不能抢先命中。"""
    text = "- [ ] 1. 收尾\n  - [ref:other/甲]\n- [ ] 收尾\n  - [ref:other/乙]\n"
    assert refs_of(text, "收尾") == (["other/乙"], [])
    assert refs_of(text, "1. 收尾") == (["other/甲"], [])


def test_whole_list_indented_two_spaces():
    """整份任务列表整体缩进两格：顶层任务和子任务都找得到，层级照旧。"""
    text = "# 计划\n\n" + "".join(("  " + l if l.strip() else l) + "\n"
                                  for l in TASKS.split("\n")[2:-3])
    assert refs_of(text, "1.1 子任务") == (["sample/Hooks"], [])
    assert sorted(refs_of(text, "1. 父任务")[0]) == sorted(["other/甲", "sample/Hooks", "other/乙"])


def test_tab_indent_counts_as_four():
    """制表符按 4 格算：比父任务的两格深，算子任务。"""
    text = "- [ ] 1. 父任务\n  - [ref:other/甲]\n\t- [ ] 1.1 子任务\n\t  - [ref:other/乙]\n"
    assert refs_of(text, "1.1 子任务") == (["other/乙"], [])
    assert sorted(refs_of(text, "1. 父任务")[0]) == ["other/乙", "other/甲"]


@pytest.mark.parametrize("mark", ["-", "X", "!"])
def test_any_single_char_status_mark(mark):
    """状态标记认方括号里的任意单个字符（偏离需求 9.6 原文，原文只列三种）。task_name 带标记也能找到。"""
    text = f"- [{mark}] 3. 标记\n  - [ref:other/甲]\n"
    assert refs_of(text, "3. 标记") == (["other/甲"], [])
    assert refs_of(text, f"  - [{mark}] 3. 标记 ") == (["other/甲"], [])


def test_child_task_gate_blocks_and_parent_needs_child_units(store):
    """经 check_task：子任务能找到并被拦；读完父任务自己的单元，父任务仍因子任务的单元被拦。"""
    res = api.check_task(store, TASKS_REL, "1.1 子任务", "s")
    assert res["found"] and not res["allow"] and res["missing"] == ["sample/Hooks"]
    api.read(store, "other", "甲")
    res = api.check_task(store, TASKS_REL, "1. 父任务", "s")
    assert not res["allow"] and sorted(res["missing"]) == ["other/乙", "sample/Hooks"]
    api.read(store, "sample", "Hooks")
    assert api.check_task(store, TASKS_REL, "1.1 子任务", "s")["allow"]  # 兄弟的 other/乙 没读也放行


# ---- 第 2 项：同号需求块 ----

def test_duplicate_requirement_blocks_merge(store):
    """同号的需求块引用合并：前一块引用未读、后一块已读，任务关卡照样拦，不抛异常。"""
    reqs = "### 需求 1：前\n出处：[ref:other/甲]\n\n### 需求 1：后\n出处：[ref:other/乙]\n"
    (store.root / "specs" / "x" / "requirements.md").write_text(reqs, encoding="utf-8")
    (store.root / TASKS_REL).write_text("- [ ] 1. 工作\n  - _需求：1_\n", encoding="utf-8")
    api.read(store, "other", "乙")
    res = api.check_task(store, TASKS_REL, "1. 工作", "s")
    assert not res["allow"] and res["missing"] == ["other/甲"]
    assert refs_of("- [ ] 1. 工作\n  - _需求：1_\n", "1. 工作", reqs) == (["other/甲", "other/乙"], [])


# ---- 第 3 项：记录失败不能把拦截变成放行 ----

def test_check_write_surrogate_session_still_blocks(store):
    res = api.check_write(store, "integrations/kiro/hook.py", SURROGATE)
    assert not res["allow"] and res["count"] == 1
    assert "这次拦截没能记进日志" in res["reason"]


def test_check_task_surrogate_session_still_blocks(store):
    res = api.check_task(store, TASKS_REL, "1.2 兄弟任务", SURROGATE)
    assert not res["allow"] and res["count"] == 1
    assert "这次拦截没能记进日志" in res["reason"]


def test_records_failure_while_counting_falls_back_to_first(store, monkeypatch):
    """降级分支里数次数也出错时，按第 1 次算，照样拦。只在结论算出之后才让读日志出错。"""
    broken = {"on": False}
    real_records, real_check, real_needs = Store.records, api.check, api.task_needs

    def records(self, *a, **k):
        if broken["on"]:
            raise RuntimeError("坏日志")
        return real_records(self, *a, **k)

    def check(*a, **k):
        res = real_check(*a, **k)
        broken["on"] = True
        return res

    def task_needs(*a, **k):
        res = real_needs(*a, **k)
        broken["on"] = True
        return res

    monkeypatch.setattr(Store, "records", records)
    monkeypatch.setattr(api, "check", check)
    monkeypatch.setattr(api, "task_needs", task_needs)
    res = api.check_write(store, "integrations/kiro/hook.py", "s")
    broken["on"] = False
    assert not res["allow"] and res["count"] == 1 and "这次拦截没能记进日志" in res["reason"]
    res = api.check_task(store, TASKS_REL, "1.2 兄弟任务", "s")
    assert not res["allow"] and res["count"] == 1 and "这次拦截没能记进日志" in res["reason"]


def run_hook(root, event, data):
    stdin = json.dumps(data, ensure_ascii=True).encode("utf-8")  # 孤立代理字符写成 \ud800 转义
    env = dict(os.environ, PYTHONPATH=str(REPO))
    return subprocess.run([sys.executable, str(root / "integrations" / "kiro" / "hook.py"), event],
                          input=stdin, capture_output=True, env=env, timeout=60, cwd=root)


def test_hooks_surrogate_session_exit_2(store):
    """会话 ID 含孤立代理字符：写文件关卡和任务关卡都退出码 2。"""
    proc = run_hook(store.root, "pre-write", {
        "hook_event_name": "PreToolUse", "session_id": SURROGATE, "tool_name": "fs_write",
        "tool_input": {"path": "integrations/kiro/hook.py", "text": "x"}})
    assert proc.returncode == 2 and "没能记进日志" in proc.stderr.decode("utf-8")
    proc = run_hook(store.root, "pretask", {
        "hook_event_name": "PreTaskExec", "session_id": SURROGATE,
        "spec_name": str(store.root / TASKS_REL), "task_name": "1.2 兄弟任务"})
    assert proc.returncode == 2 and "没能记进日志" in proc.stderr.decode("utf-8")


# ---- 第 4 项：配置里把列表写成字符串 ----

def test_exempt_string_is_one_pattern(store):
    """exempt = "docs/*.md"：只豁免这一个模式，src/code.py 不豁免；报告的"配置写错"里有提示。"""
    (store.root / "refcov.toml").write_text(CONFIG.format(extra='exempt = "docs/*.md"'), encoding="utf-8")
    assert not api.check_write(store, "src/code.py", "s")["allow"]
    assert api.check_write(store, "docs/note.md", "s")["allow"]
    probs = api.report(store, None)["config_problems"]
    assert any(p["where"] == "exempt" and "docs/*.md" in p["value"] for p in probs), probs
    assert "exempt" in api.report_text(api.report(store, None))


def test_scope_paths_string(store):
    """[[scope]] 的 paths 写成字符串：只命中这一个模式，别的路径仍按全部参考源。"""
    cfg = CONFIG.format(extra="").replace('paths = ["integrations/kiro/**"]', 'paths = "integrations/kiro/**"')
    (store.root / "refcov.toml").write_text(cfg, encoding="utf-8")
    assert api.check(store, "integrations/kiro/hook.py")["required"] == 3  # other 2 个 + 需求引用的 sample/Hooks
    assert api.check(store, "refcov/api.py")["required"] == 7  # 不命中 scope：全部参考源
    probs = api.check(store, "refcov/api.py")["config_problems"]
    assert any(p["where"] == "scope 第 1 条 paths" for p in probs), probs


def test_other_string_lists_listed(store):
    """requirements、spec_files、watch、confirm、scope 的 sources、relax 三项写成字符串：都列出，判断和写成列表一样。"""
    cfg = """requirements = "specs/*/requirements.md"
spec_files = "specs/**"
watch = "a"
confirm = "b"

[relax]
sources = "sample"
kinds = "nothing"
units = "other/甲"

[[scope]]
paths = ["integrations/kiro/**"]
sources = "other"
"""
    (store.root / "refcov.toml").write_text(cfg, encoding="utf-8")
    wheres = [p["where"] for p in api.report(store, None)["config_problems"]]
    for w in ("requirements", "spec_files", "watch", "confirm", "relax.sources", "relax.kinds",
              "relax.units", "scope 第 1 条 sources"):
        assert w in wheres, (w, wheres)
    res = api.check(store, "integrations/kiro/hook.py")
    assert res["required"] == 2  # other/甲 被放宽；剩 other/乙 和需求引用的 sample/Hooks（放宽移不掉）
    assert res["requirement_docs"] == ["specs/x/requirements.md"]


def test_path_matches_string_pattern():
    """path_matches 收到字符串时当成一个模式，不逐字符拆开。"""
    assert not path_matches("src/code.py", "docs/*.md")
    assert path_matches("docs/a.md", "docs/*.md")
