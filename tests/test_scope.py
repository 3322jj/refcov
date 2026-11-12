"""按路径的必看集合（任务 11 第 2 步，设计 7 第 3 条，需求 8.1–8.3、6.5、6.7）。手写数据的普通测试。"""

from refcov.coverage import Decl, is_exempt, is_spec_file, required_for_path, required_set, scope_sources

DECLS = {"markdown": {"section": Decl(strict=True)}}
SOURCES = [
    {"id": "kiro-hooks", "adapter": "markdown", "units": [{"id": "Hooks", "kind": "section"},
                                                           {"id": "退出码", "kind": "section"}]},
    {"id": "rules", "adapter": "markdown", "units": [{"id": "1.-Dates", "kind": "section"},
                                                      {"id": "6.-Judges-&-Criteria", "kind": "section"}]},
    {"id": "dec-x", "adapter": "markdown", "units": [{"id": "意见-1", "kind": "section"}]},
]
NO_RELAX = {"sources": [], "kinds": [], "units": []}
SCOPES = [{"paths": ["integrations/kiro/**"], "sources": ["kiro-hooks"]},
          {"paths": ["integrations/**/*.py"], "sources": ["dec-x"]}]
EXEMPT = ["DEVLOG.md", "**/DEVLOG.md", "docs/decisions/**"]
ALL = {(s["id"], u["id"]) for s in SOURCES for u in s["units"]}


def _req(cited=frozenset()):
    return required_set(SOURCES, DECLS, "strict", NO_RELAX, cited)


def test_scope_hit():
    """需求 8.1：hook.py 命中 integrations/kiro/** 时，只要 kiro-hooks 的单元。"""
    scopes = SCOPES[:1]
    assert scope_sources("integrations/kiro/hook.py", scopes) == {"kiro-hooks"}
    assert required_for_path(_req(), set(), "integrations/kiro/hook.py", scopes) == {
        ("kiro-hooks", "Hooks"), ("kiro-hooks", "退出码")}


def test_scope_union():
    """设计 3.4：一个路径命中多条 scope，取这些规则的参考源并集。"""
    assert scope_sources("integrations/kiro/hook.py", SCOPES) == {"kiro-hooks", "dec-x"}
    assert required_for_path(_req(), set(), "integrations/kiro/hook.py", SCOPES) == {
        ("kiro-hooks", "Hooks"), ("kiro-hooks", "退出码"), ("dec-x", "意见-1")}


def test_no_scope_means_all_sources():
    """需求 8.2：没有为路径配置规则时要求全部参考源；不给路径、没有任何 scope 也一样。"""
    assert scope_sources("refcov/coverage.py", SCOPES) is None
    assert required_for_path(_req(), set(), "refcov/coverage.py", SCOPES) == ALL
    assert required_for_path(_req(), set(), None, SCOPES) == ALL
    assert required_for_path(_req(), set(), "integrations/kiro/hook.py", []) == ALL


def test_cited_outside_scope_still_required():
    """需求 6.5：被引用的单元不论在哪个参考源，都并进按路径的必看集合。"""
    cited = {("rules", "6.-Judges-&-Criteria")}
    got = required_for_path(_req(cited), cited, "integrations/kiro/hook.py", SCOPES[:1])
    assert ("rules", "6.-Judges-&-Criteria") in got
    assert ("rules", "1.-Dates") not in got


def test_path_case_and_separator():
    """设计 3.4：路径和模式都转小写、反斜杠当 /，Windows 和 Linux 结果一致。"""
    assert scope_sources("Integrations\\Kiro\\HOOK.py", SCOPES[:1]) == {"kiro-hooks"}


def test_exempt():
    """需求 8.3：默认豁免 DEVLOG.md（任何位置）和 docs/decisions/**；别的路径和不给路径不豁免。"""
    assert is_exempt("DEVLOG.md", EXEMPT)
    assert is_exempt("docs/DEVLOG.md", EXEMPT)
    assert is_exempt("docs/decisions/2026-11-10-review-reply.md", EXEMPT)
    assert not is_exempt("integrations/kiro/hook.py", EXEMPT)
    assert not is_exempt(None, EXEMPT)
    assert not is_exempt("DEVLOG.md", [])


def test_spec_file():
    """需求 6.7、8.4：规格文件只用来跳过出处检查，不是豁免；没配 spec_files 时什么都不是规格文件。"""
    spec = [".kiro/specs/**"]
    assert is_spec_file(".kiro/specs/refcov-skeleton/requirements.md", spec)
    assert not is_exempt(".kiro/specs/refcov-skeleton/requirements.md", EXEMPT)
    assert not is_spec_file(".kiro/specs/refcov-skeleton/requirements.md", [])
    assert not is_spec_file(None, spec)


# ---- scope、relax 写了清单里没有的东西（外部审阅 2026-11-12）----

from refcov.coverage import config_problems  # noqa: E402

KNOWN_SOURCES = {s["id"] for s in SOURCES}


def test_scope_with_unknown_source_means_all_sources():
    """scope 里有不存在的参考源：那条规则按全部参考源处理，宁可多要求，不因写错变宽松。"""
    scopes = [{"paths": ["integrations/kiro/**"], "sources": ["kiro-hoooks"]}]
    assert scope_sources("integrations/kiro/hook.py", scopes, KNOWN_SOURCES) is None
    assert required_for_path(_req(), set(), "integrations/kiro/hook.py", scopes, KNOWN_SOURCES) == ALL
    mixed = [{"paths": ["integrations/kiro/**"], "sources": ["kiro-hooks", "kiro-hoooks"]}]
    assert scope_sources("integrations/kiro/hook.py", mixed, KNOWN_SOURCES) is None
    # 没命中的规则写错不影响别的路径
    assert scope_sources("integrations/kiro/hook.py", SCOPES + [{"paths": ["docs/**"], "sources": ["x"]}],
                         KNOWN_SOURCES) == {"kiro-hooks", "dec-x"}


def test_empty_scope_sources_kept():
    """scope 的 sources 为空列表：保持现状（只要求被引用的单元），只提示（用户 2026-11-12 定）。"""
    scopes = [{"paths": ["integrations/kiro/**"], "sources": []}]
    assert scope_sources("integrations/kiro/hook.py", scopes, KNOWN_SOURCES) == frozenset()


def test_config_problems_lists_every_mistake():
    scopes = [{"paths": ["a/**"], "sources": ["kiro-hooks", "kiro-hoooks"]}, {"paths": ["b/**"], "sources": []}]
    relax = {"sources": ["rules", "rulez"], "kinds": ["section", "图表"],
             "units": ["kiro-hooks/Hooks", "kiro-hooks/没有", "nope/x", "坏格式"]}
    got = [(p["where"], p["value"]) for p in config_problems(SOURCES, scopes, relax)]
    assert got == [("scope 第 1 条 sources", "kiro-hoooks"), ("scope 第 2 条 sources", "[]"),
                   ("relax.sources", "rulez"), ("relax.kinds", "图表"),
                   ("relax.units", "kiro-hooks/没有"), ("relax.units", "nope/x"), ("relax.units", "坏格式")]
    notes = {p["value"]: p["note"] for p in config_problems(SOURCES, scopes, relax)}
    assert "按全部参考源处理" in notes["kiro-hoooks"]
    assert "只提示" in notes["rulez"]


def test_no_problems():
    assert config_problems(SOURCES, SCOPES[:1], {"sources": [], "kinds": [], "units": []}) == ()
