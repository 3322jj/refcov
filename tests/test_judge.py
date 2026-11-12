"""达标判断和三类单元（任务 11 第 3 步，设计 7 第 4、5 条，需求 5.6、6.3、6.5–6.7、8.3）。手写数据的普通测试。"""

import pytest

from refcov.coverage import Decl, judge, required_for_path, required_set, unit_lists

DECLS = {"markdown": {"section": Decl(strict=True)}, "geo": {"crs": Decl(strict=True, key=True),
                                                               "sample": Decl(strict=False)}}
SOURCES = [
    {"id": "kiro-hooks", "adapter": "markdown", "units": [{"id": "Hooks", "kind": "section"},
                                                           {"id": "退出码", "kind": "section"}]},
    {"id": "rules", "adapter": "markdown", "units": [{"id": "6.-Judges-&-Criteria", "kind": "section"}]},
    {"id": "roads", "adapter": "geo", "units": [{"id": "CRS", "kind": "crs"}, {"id": "第 1 行", "kind": "sample"}]},
]
NO_RELAX = {"sources": [], "kinds": [], "units": []}
SCOPES = [{"paths": ["integrations/kiro/**"], "sources": ["kiro-hooks"]}]
HOOKS = {("kiro-hooks", "Hooks"), ("kiro-hooks", "退出码")}
PHANTOM = (("req.md", "3"),)
INVALID = (("req.md", "5", "kiro-hooks/exit"),)


def _path_req(mode, cited, path):
    r = required_set(SOURCES, DECLS, mode, NO_RELAX, cited)
    return required_for_path(r, cited, path, SCOPES)


def test_all_read_passes():
    """需求 5.6：按路径的必看单元全部看过就达标。"""
    v = judge(SOURCES, _path_req("strict", set(), "integrations/kiro/hook.py"), HOOKS, "strict")
    assert v.passed and v.missing == ()


def test_missing_listed_in_manifest_order():
    """需求 5.6：没看完时不达标，并按清单顺序列出还差的单元。"""
    v = judge(SOURCES, _path_req("strict", set(), None), {("kiro-hooks", "退出码")}, "strict")
    assert not v.passed
    assert v.missing == (("kiro-hooks", "Hooks"), ("rules", "6.-Judges-&-Criteria"), ("roads", "CRS"))


def test_cited_unread_fails_both_modes():
    """需求 6.5：需求引用了没有有效读取的单元，两种模式都不达标（hook.py 的 scope 外的单元也一样）。"""
    cited = {("rules", "6.-Judges-&-Criteria")}
    for mode in ("strict", "light"):
        v = judge(SOURCES, _path_req(mode, cited, "integrations/kiro/hook.py"), HOOKS | {("roads", "CRS")}, mode)
        assert not v.passed
        assert ("rules", "6.-Judges-&-Criteria") in v.missing


def test_strict_phantom_or_invalid_fails():
    """需求 6.6：严格模式下有幻影需求或无效引用就不达标，单元都看过也一样。"""
    req = _path_req("strict", set(), "integrations/kiro/hook.py")
    for ph, inv in ((PHANTOM, ()), ((), INVALID)):
        v = judge(SOURCES, req, HOOKS, "strict", ph, inv)
        assert not v.passed and v.citations_checked and v.citations_fail
        assert v.phantom == ph and v.invalid == inv


def test_light_only_lists():
    """需求 6.6：轻量模式下幻影需求和无效引用只列出，不影响达标。"""
    v = judge(SOURCES, _path_req("light", set(), "integrations/kiro/hook.py"), set(), "light", PHANTOM, INVALID)
    assert v.passed and not v.citations_checked and not v.citations_fail
    assert v.phantom == PHANTOM and v.invalid == INVALID


def test_spec_file_skips_citation_check_only():
    """需求 6.7：写规格文件时不因幻影需求、无效引用不达标；但没读的必看单元和被引用单元照样不达标（6.5、8.4）。"""
    cited = {("rules", "6.-Judges-&-Criteria")}
    spec = ".kiro/specs/x/requirements.md"
    req = _path_req("strict", cited, spec)
    everything = {(s["id"], u["id"]) for s in SOURCES for u in s["units"]}
    v = judge(SOURCES, req, everything, "strict", PHANTOM, INVALID, spec_file=True)
    assert v.passed and v.spec_file and not v.citations_checked
    v = judge(SOURCES, req, everything - cited, "strict", PHANTOM, INVALID, spec_file=True)
    assert not v.passed and v.missing == (("rules", "6.-Judges-&-Criteria"),)
    v = judge(SOURCES, req, everything - {("roads", "CRS")}, "strict", (), (), spec_file=True)
    assert not v.passed


def test_exempt_passes_but_lists_missing():
    """需求 8.3：豁免路径不检查是否达标；还差的单元照样列出。"""
    v = judge(SOURCES, _path_req("strict", set(), "DEVLOG.md"), set(), "strict", PHANTOM, INVALID, exempt=True)
    assert v.passed and v.exempt and v.missing


def test_unit_lists():
    """需求 6.3：幽灵单元 = 必看没看过；被忽略单元 = 看过没被引用；另列本模式未要求的单元。"""
    cited = {("kiro-hooks", "Hooks"), ("rules", "6.-Judges-&-Criteria")}
    r = required_set(SOURCES, DECLS, "strict", NO_RELAX, cited)
    valid = {("kiro-hooks", "Hooks"), ("kiro-hooks", "退出码"), ("roads", "第 1 行")}
    lists = unit_lists(SOURCES, r, valid, cited)
    assert lists.ghost == ("rules/6.-Judges-&-Criteria", "roads/CRS")
    assert lists.ignored == ("kiro-hooks/退出码", "roads/第 1 行")
    assert lists.not_required == ("roads/第 1 行",)


def test_bad_mode():
    with pytest.raises(ValueError):
        judge(SOURCES, set(), set(), "loose")


# ---- 需求文档一条需求都没解析出来（外部审阅 2026-11-12 发现的无声失效）----

EMPTY = ("specs/y/requirements.md",)


def test_strict_empty_requirement_doc_fails():
    """严格模式下，命中配置的需求文档解析出 0 条需求，按不达标处理（偏离需求原文：6.6 只列了幻影需求和无效引用）。"""
    req = _path_req("strict", set(), "integrations/kiro/hook.py")
    v = judge(SOURCES, req, HOOKS, "strict", empty_docs=EMPTY)
    assert not v.passed and v.citations_fail and v.empty_docs == EMPTY
    assert judge(SOURCES, req, HOOKS, "strict").passed


def test_light_empty_requirement_doc_only_listed():
    """轻量模式只列出，不影响达标（同需求 6.6 对幻影需求的处理）。"""
    v = judge(SOURCES, _path_req("light", set(), None), {("roads", "CRS")}, "light", empty_docs=EMPTY)
    assert v.passed and v.empty_docs == EMPTY


def test_spec_file_not_blocked_by_empty_requirement_doc():
    """需求 6.7：写规格文件时不因此不达标。"""
    everything = {(s["id"], u["id"]) for s in SOURCES for u in s["units"]}
    req = _path_req("strict", set(), EMPTY[0])
    v = judge(SOURCES, req, everything, "strict", empty_docs=EMPTY, spec_file=True)
    assert v.passed and v.empty_docs == EMPTY
