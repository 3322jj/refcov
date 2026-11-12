"""api.check 和报告里的达标字段（任务 11 第 4 步，设计 7、3.5，需求 5、6、8、15）。临时仓库，普通测试。"""

import shutil
from pathlib import Path

import pytest

from refcov import api
from refcov.sources import register
from refcov.store import Store

SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"  # 5 个单元
DOC = "specs/x/requirements.md"
REQS = """# 需求

### 需求 1：有出处
出处：[ref:sample/Hooks]

### 需求 2：没有出处
只有验收标准。

### 需求 3：单元不存在
出处：[ref:sample/没有这个]

### 需求 4：文字出处
出处：交接说明·核心功能 1
"""
CONFIG = f"""mode = "{{mode}}"
requirements = ["specs/*/requirements.md"]
spec_files = ["specs/**"]
{{extra}}
[[scope]]
paths = ["integrations/kiro/**"]
sources = ["other"]
"""
OTHER = [("other", "甲"), ("other", "乙")]


@pytest.fixture
def store(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copyfile(SAMPLE, tmp_path / "docs" / "sample-hooks.md")
    (tmp_path / "docs" / "other.md").write_text("# 甲\n内容一\n# 乙\n内容二\n", encoding="utf-8")
    (tmp_path / "specs" / "x").mkdir(parents=True)
    (tmp_path / DOC).write_text(REQS, encoding="utf-8")
    s = Store(tmp_path)
    register(s, "docs/sample-hooks.md", "sample")
    register(s, "docs/other.md", "other")
    return s


def configure(store, mode="strict", extra=""):
    (store.root / "refcov.toml").write_text(CONFIG.format(mode=mode, extra=extra), encoding="utf-8")


def read_all(store, units):
    for s, u in units:
        api.read(store, s, u)


def units_of(res):
    return [(m["source"], m["unit"]) for m in res["missing"]]


def test_no_config_requires_everything(store):
    """没有 refcov.toml：严格模式、没有需求文档、没有 scope，必看 = 全部 7 个单元；出处检查报未配置。"""
    res = api.check(store)
    assert res["required"] == 7 and not res["pass"] and len(res["missing"]) == 7
    assert res["requirement_docs"] == [] and res["phantom_requirements"] == []
    assert "未配置需求文档" in api.check_text(res)


def test_scope_plus_cited(store):
    """需求 8.1、6.5：命中 scope 时必看 = scope 的参考源 + 全部被引用单元（这里是 sample/Hooks）。"""
    configure(store)
    res = api.check(store, "integrations/kiro/hook.py")
    assert res["required"] == 3
    assert units_of(res) == [("sample", "Hooks"), *OTHER]
    read_all(store, OTHER)
    res = api.check(store, "integrations/kiro/hook.py")
    assert not res["pass"] and units_of(res) == [("sample", "Hooks")]  # 引用了没读的单元：不达标


def test_strict_phantom_and_invalid_fail(store):
    """需求 6.6：单元都读了，严格模式下仍因幻影需求（2、3）和无效引用不达标；未转换（4）不算。"""
    configure(store)
    read_all(store, [*OTHER, ("sample", "Hooks")])
    res = api.check(store, "integrations/kiro/hook.py")
    assert res["missing"] == [] and not res["pass"] and res["citations_checked"]
    assert res["phantom_requirements"] == [{"doc": DOC, "requirement": "2"}, {"doc": DOC, "requirement": "3"}]
    assert res["invalid_refs"] == [{"doc": DOC, "requirement": "3", "ref": "sample/没有这个"}]


def test_spec_file_exception(store):
    """需求 6.7、8.4：写规格文件不因幻影需求、无效引用不达标；没有 scope，全部参考源都要读。"""
    configure(store)
    res = api.check(store, DOC)
    assert res["spec_file"] and not res["citations_checked"] and res["required"] == 7 and not res["pass"]
    read_all(store, [(u["source"], u["unit"]) for u in res["missing"]])
    res = api.check(store, DOC)
    assert res["pass"] and res["phantom_requirements"]  # 照样列出


def test_light_mode(store):
    """需求 15.2、6.6：轻量模式必看 = 关键类型（markdown 没有）+ 被引用单元；幻影需求只列出。"""
    configure(store, mode="light")
    res = api.check(store)
    assert res["required"] == 1 and units_of(res) == [("sample", "Hooks")]
    api.read(store, "sample", "Hooks")
    res = api.check(store)
    assert res["pass"] and len(res["phantom_requirements"]) == 2


def test_exempt(store):
    """需求 8.3：豁免路径达标（不检查），还差的单元照样列出。"""
    configure(store)
    res = api.check(store, "docs/DEVLOG.md")
    assert res["exempt"] and res["pass"] and res["missing"]
    assert "豁免路径" in api.check_text(res)


def test_absolute_path_and_backslashes(store):
    configure(store)
    res = api.check(store, str(store.root / "integrations" / "kiro" / "hook.py"))
    assert res["path"] == "integrations/kiro/hook.py" and res["required"] == 3
    assert api.check(store, "Integrations\\Kiro\\Hook.py")["required"] == 3


def test_report_fields(store):
    """设计 3.5：报告列出幽灵、被忽略、本模式未要求的单元，出处检查三类，放宽项（含被引用仍必看的）。"""
    configure(store, extra='[relax]\nsources = ["sample"]\n')
    api.read(store, "other", "甲")
    api.read(store, "sample", "退出码")
    rep = api.report(store, None)
    assert rep["mode"] == "strict" and rep["pass"] is False
    # 放宽了 sample：必看 = other 两个 + 被引用的 sample/Hooks
    assert rep["ghost_units"] == ["sample/Hooks", "other/乙"]
    assert [m["unit"] for m in rep["missing"]] == ["Hooks", "乙"]
    assert rep["ignored_units"] == ["sample/退出码", "other/甲"]
    assert rep["not_required_units"] == ["sample/sample-hooks", "sample/退出码", "sample/匹配-工具名",
                                         "sample/退出码-2"]
    assert rep["relaxed"] == {"sources": ["sample"], "kinds": [], "units": [], "cited_but_relaxed": ["sample/Hooks"]}
    assert rep["phantom_requirements"] == [{"doc": DOC, "requirement": "2"}, {"doc": DOC, "requirement": "3"}]
    assert rep["unconverted_requirements"] == [{"doc": DOC, "requirement": "4"}]
    assert rep["requirement_docs"] == [DOC] and rep["config_mtime"]
    srcs = {s["id"]: s for s in rep["sources"]}
    assert (srcs["sample"]["units"], srcs["sample"]["required"], srcs["sample"]["read_history"],
            srcs["sample"]["required_read_history"]) == (5, 1, 1, 0)
    text = api.report_text(rep)
    assert "放宽项：参考源 sample" in text and "仍然必看：sample/Hooks" in text
    assert "幻影需求 2 条" in api.status_line(store, None)


def test_enforce_false_head(store):
    """需求 17.2：enforce = false 时第一行写"关卡已关闭"，判断照常给出。"""
    configure(store, extra="enforce = false\n")
    rep = api.report(store, None)
    assert rep["enforce"] is False and rep["pass"] is False
    assert api.report_text(rep).splitlines()[0].startswith("RefCov 关卡已关闭")
    assert "关卡已关闭" in api.check_text(api.check(store))


def test_check_is_read_only(store):
    configure(store)
    before = {p: p.read_bytes() for p in store.root.rglob("*") if p.is_file()}
    api.check(store, "integrations/kiro/hook.py")
    api.report(store, None)
    assert {p: p.read_bytes() for p in store.root.rglob("*") if p.is_file()} == before


def test_unreadable_requirement_doc(store):
    configure(store)
    (store.root / DOC).write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(api.CheckError, match="需求文档读不了"):
        api.check(store)


def test_check_text_limit(store):
    """MCP 工具只列前 20 个还差的单元，另写总数（设计 5）。"""
    text = api.check_text(api.check(store), limit=3)
    assert "还差 7 个（只列前 3 个）" in text and text.endswith(api.HINT)


# ---- 命令行 refcov check（第 5 步）----

def _run(store, *args):
    import os
    import subprocess
    import sys

    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    return subprocess.run([sys.executable, "-m", "refcov", "check", *args], cwd=store.root, capture_output=True,
                          env=env, timeout=60)


def _enc() -> str:
    """和 test_register 一样：Windows 上 cli 输出被捕获时改用控制台代码页；没有控制台时用默认编码。"""
    import sys

    if sys.platform != "win32":
        return "utf-8"
    import ctypes
    import locale

    cp = ctypes.windll.kernel32.GetConsoleOutputCP()
    return f"cp{cp}" if cp else locale.getpreferredencoding(False)


def test_cli_check_exit_codes(store):
    """退出码：不达标 1、达标 0、出错 2（用户 2026-11-12 定）；结论和还差几个在 stdout。"""
    configure(store)
    proc = _run(store, "integrations/kiro/hook.py")
    out = proc.stdout.decode(_enc())
    assert proc.returncode == 1, proc.stderr.decode(_enc(), "replace")
    assert "integrations/kiro/hook.py：未达标" in out and "必看 3 个，还差 3 个" in out
    proc = _run(store, "DEVLOG.md")
    assert proc.returncode == 0 and "豁免路径" in proc.stdout.decode(_enc())
    (store.root / "refcov.toml").write_text("mode = [", encoding="utf-8")
    proc = _run(store)
    assert proc.returncode == 2 and "检查失败" in proc.stderr.decode(_enc()) and proc.stdout == b""


def test_cli_check_passes_after_reading(store, monkeypatch, capsys):
    from refcov import cli

    configure(store, mode="light")
    monkeypatch.chdir(store.root)
    assert cli.main(["check"]) == 1
    assert "全部参考源：未达标" in capsys.readouterr().out
    api.read(store, "sample", "Hooks")
    assert cli.main(["check"]) == 0
    assert "全部参考源：达标" in capsys.readouterr().out


def test_cli_check_needs_repo_root(store, monkeypatch, capsys):
    from refcov import cli

    monkeypatch.chdir(store.root / "docs")
    assert cli.main(["check"]) == 2
    assert "请在仓库根目录运行 refcov" in capsys.readouterr().err


# ---- 需求文档一条需求都没解析出来 / 模式没匹配到文件（外部审阅 2026-11-12）----

UNPARSED = Path(__file__).parent / "data" / "sample-requirements-unparsed.md"
EMPTY_DOC = "specs/y/requirements.md"


def add_unparsed(store):
    (store.root / "specs" / "y").mkdir(parents=True)
    shutil.copyfile(UNPARSED, store.root / EMPTY_DOC)


def test_empty_requirement_doc_strict(store):
    """命中配置的需求文档解析出 0 条需求：报告、check、状态行都写明；严格模式不达标，写规格文件不因此被拦。"""
    configure(store)
    add_unparsed(store)
    everything = [(u["source"], u["unit"]) for u in api.check(store)["missing"]]
    read_all(store, everything)
    (store.root / DOC).write_text("### 需求 1：有出处\n出处：[ref:sample/Hooks]\n", encoding="utf-8")
    res = api.check(store, "integrations/kiro/hook.py")
    assert res["missing"] == [] and res["phantom_requirements"] == [] and res["invalid_refs"] == []
    assert res["empty_requirement_docs"] == [EMPTY_DOC] and not res["pass"]
    assert f"{EMPTY_DOC} 没解析出任何需求" in api.check_text(res)
    assert api.check(store, EMPTY_DOC)["pass"]  # 规格文件（需求 6.7）
    rep = api.report(store, None)
    assert rep["empty_requirement_docs"] == [EMPTY_DOC] and rep["pass"] is False
    assert rep["requirement_docs"] == [DOC, EMPTY_DOC]
    assert f"{EMPTY_DOC} 没解析出任何需求" in api.report_text(rep)
    assert f"{EMPTY_DOC} 没解析出任何需求" in api.status_line(store, None)


def test_empty_requirement_doc_light_only_listed(store):
    configure(store, mode="light")
    add_unparsed(store)
    api.read(store, "sample", "Hooks")
    res = api.check(store)
    assert res["pass"] and res["empty_requirement_docs"] == [EMPTY_DOC]
    assert "没解析出任何需求" in api.status_line(store, None)


def test_requirement_patterns_match_no_file(store):
    """配置了 requirements 但一个文件都没匹配到：只改提示文字，达标判断不变（用户 2026-11-12 定）。"""
    (store.root / "refcov.toml").write_text('requirements = ["specs/*/needs.md"]\n', encoding="utf-8")
    rep = api.report(store, None)
    assert rep["requirement_docs"] == [] and rep["requirement_patterns"] == ["specs/*/needs.md"]
    text = api.report_text(rep)
    assert "配置了 specs/*/needs.md，但没找到文件" in text and "未配置需求文档" not in text
    assert "配置了 specs/*/needs.md，但没找到文件" in api.check_text(api.check(store))
    assert api.report(store.__class__(store.root), None)["empty_requirement_docs"] == []
    (store.root / "refcov.toml").unlink()
    assert "未配置需求文档" in api.report_text(api.report(store, None))


# ---- scope、relax 写错（外部审阅 2026-11-12）----

def test_scope_typo_requires_all_and_is_reported(store):
    """scope 写错参考源 ID：那条规则按全部参考源处理；报告、check、状态行都标出来。relax 写错只提示。"""
    (store.root / "refcov.toml").write_text(
        '[relax]\nsources = ["sampel"]\n\n[[scope]]\npaths = ["integrations/kiro/**"]\nsources = ["othr"]\n',
        encoding="utf-8")
    res = api.check(store, "integrations/kiro/hook.py")
    assert res["required"] == 7  # 不是 0：按全部参考源
    assert [(p["where"], p["value"]) for p in res["config_problems"]] == [
        ("scope 第 1 条 sources", "othr"), ("relax.sources", "sampel")]
    assert "配置有 2 处写错" in api.check_text(res) and "othr" in api.check_text(res)
    rep = api.report(store, None)
    assert len(rep["config_problems"]) == 2
    assert sum(s["required"] for s in rep["sources"]) == 7  # relax 写错：判断不变
    assert "othr" in api.report_text(rep)
    line = api.status_line(store, None)
    assert "配置有 2 处写错" in line and "\n" not in line


def test_no_config_problems_by_default(store):
    assert api.report(store, None)["config_problems"] == []
    assert "写错" not in api.status_line(store, None)
