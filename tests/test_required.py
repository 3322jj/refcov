"""必看集合（任务 11 第 1 步，设计 7 第 2 条，需求 5.1、5.3、15.2）。手写数据的普通测试；属性测试在任务 12。"""

import pytest

from refcov.coverage import Decl, required_set

# 一个适配器：章节严格必看；坐标系是关键类型；样本行是可选类型（严格模式也不必看）
DECLS = {
    "doc": {"section": Decl(strict=True)},
    "geo": {"crs": Decl(strict=True, key=True), "field": Decl(strict=True), "sample": Decl(strict=False)},
}

SOURCES = [
    {"id": "hooks", "adapter": "doc", "units": [
        {"id": "退出码", "kind": "section"},
        {"id": "退出码@2", "kind": "section"},
        {"id": "更新日志", "kind": "section"},
    ]},
    {"id": "roads", "adapter": "geo", "units": [
        {"id": "CRS", "kind": "crs"},
        {"id": "名称", "kind": "field"},
        {"id": "第 1 行", "kind": "sample"},
    ]},
]

NO_RELAX = {"sources": [], "kinds": [], "units": []}
ALL_STRICT = {("hooks", "退出码"), ("hooks", "退出码@2"), ("hooks", "更新日志"), ("roads", "CRS"), ("roads", "名称")}


def test_strict_base_is_strict_kinds():
    """需求 5.1：严格模式的基础集合是严格必看类型的单元；可选类型（样本行）不在里面。"""
    r = required_set(SOURCES, DECLS, "strict", NO_RELAX, set())
    assert r.units == ALL_STRICT
    assert r.relaxed == frozenset() and r.cited_but_relaxed == ()


def test_light_base_is_key_kinds():
    """需求 15.2：轻量模式的基础集合是关键类型的单元。"""
    r = required_set(SOURCES, DECLS, "light", NO_RELAX, set())
    assert r.units == {("roads", "CRS")}


def test_cited_optional_unit_is_required():
    """需求 5.1：被引用的单元永远必看，含可选类型（样本行），两种模式都是。"""
    cited = {("roads", "第 1 行"), ("hooks", "退出码")}
    assert required_set(SOURCES, DECLS, "strict", NO_RELAX, cited).units == ALL_STRICT | {("roads", "第 1 行")}
    assert required_set(SOURCES, DECLS, "light", NO_RELAX, cited).units == {("roads", "CRS"), ("roads", "第 1 行"),
                                                                            ("hooks", "退出码")}


def test_relax_by_source_kind_unit():
    """需求 5.3：按参考源、单元类型、单个单元放宽，都移出基础集合。"""
    r = required_set(SOURCES, DECLS, "strict", {"sources": ["hooks"], "kinds": [], "units": []}, set())
    assert r.units == {("roads", "CRS"), ("roads", "名称")}
    assert r.relaxed == {("hooks", "退出码"), ("hooks", "退出码@2"), ("hooks", "更新日志")}
    r = required_set(SOURCES, DECLS, "strict", {"sources": [], "kinds": ["field"], "units": []}, set())
    assert r.units == ALL_STRICT - {("roads", "名称")}
    r = required_set(SOURCES, DECLS, "strict", {"sources": [], "kinds": [], "units": ["hooks/更新日志"]}, set())
    assert r.units == ALL_STRICT - {("hooks", "更新日志")}
    assert r.relaxed == {("hooks", "更新日志")}


def test_relax_cannot_remove_cited():
    """需求 5.3：在放宽范围内但被需求引用的单元仍然必看，并单独列出。"""
    relax = {"sources": ["hooks"], "kinds": [], "units": []}
    r = required_set(SOURCES, DECLS, "strict", relax, {("hooks", "退出码@2")})
    assert ("hooks", "退出码@2") in r.units
    assert ("hooks", "退出码") not in r.units
    assert r.cited_but_relaxed == ("hooks/退出码@2",)
    assert ("hooks", "退出码@2") not in r.relaxed


def test_relax_only_shrinks():
    """需求 5.3：放宽项只能缩小必看集合：放宽一个本来就不必看的类型，结果不变。"""
    r = required_set(SOURCES, DECLS, "strict", {"sources": [], "kinds": ["sample"], "units": []}, set())
    assert r.units == ALL_STRICT
    assert r.relaxed == frozenset()


def test_unknown_kind_or_adapter_is_strict():
    """清单里的类型或适配器在声明里找不到时，按严格必看、不是关键类型处理（用户 2026-11-12 同意）。"""
    sources = [{"id": "x", "adapter": "doc", "units": [{"id": "a", "kind": "图表"}]},
               {"id": "y", "adapter": "没有这个", "units": [{"id": "b", "kind": "section"}]}]
    assert required_set(sources, DECLS, "strict", NO_RELAX, set()).units == {("x", "a"), ("y", "b")}
    assert required_set(sources, DECLS, "light", NO_RELAX, set()).units == frozenset()


def test_cited_not_in_manifest_ignored():
    """不在清单里的引用不进必看集合（它们是无效引用，在出处检查里报）。"""
    r = required_set(SOURCES, DECLS, "light", NO_RELAX, {("hooks", "没有"), ("nope", "x")})
    assert r.units == {("roads", "CRS")}


def test_bad_mode():
    with pytest.raises(ValueError):
        required_set(SOURCES, DECLS, "loose", NO_RELAX, set())


def test_pure_inputs_unchanged():
    """纯函数：不改输入。"""
    import copy

    before = copy.deepcopy(SOURCES)
    cited = {("hooks", "退出码")}
    required_set(SOURCES, DECLS, "strict", {"sources": ["hooks"], "kinds": [], "units": []}, cited)
    assert SOURCES == before and cited == {("hooks", "退出码")}
