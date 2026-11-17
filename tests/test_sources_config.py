"""`[sources]` 的配置解析（简化上手设计 1.1、1.7）。纯函数，不碰文件系统。"""

import copy
import string

from hypothesis import given, strategies as st

from refcov.store import DEFAULT_CONFIG, source_specs, sources_problems

LOWER = string.ascii_lowercase
# 合法的相对路径：段里可以有中文、空格和方括号（生成数据要包含这些字符，测试约定）
SEGMENT = st.text(alphabet=LOWER + string.digits + "-_ 中文[]", min_size=1, max_size=8)
PATTERN = st.lists(SEGMENT, min_size=1, max_size=3).map(lambda parts: "/".join(parts) + "/*.md")
ADAPTER_NAME = st.text(alphabet=LOWER, min_size=1, max_size=8).filter(lambda s: s != "files")


@given(st.text(alphabet=string.ascii_letters + string.digits + "/.-_", min_size=1, max_size=30))
def test_urls_are_always_reported(tail):
    """性质 S1：网址一律报配置问题，不登记（网址只走 refcov add）。"""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["sources"] = {"files": ["https://" + tail]}
    problems = sources_problems(cfg)
    assert any("网址" in p["note"] for p in problems), problems


@given(st.lists(PATTERN, max_size=5))
def test_plain_relative_patterns_round_trip(patterns):
    """性质 S2：仓库内的相对路径原样保留，不报配置问题。"""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["sources"] = {"files": patterns}
    assert source_specs(cfg) == [("markdown", patterns)]
    assert sources_problems(cfg) == []


def test_no_sources_section_means_nothing():
    """性质 S3：没有 [sources] 时，展开和问题都是空的（现有配置不受影响）。"""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    assert source_specs(cfg) == []
    assert sources_problems(cfg) == []


@given(ADAPTER_NAME, st.booleans())
def test_undeclared_adapter_tables_are_reported(name, declared):
    """性质 S4：`[sources.<名字>]` 的名字要先在 [adapters] 里声明；声明了就不报。"""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["sources"] = {name: {"files": ["videos/*.mp4"]}}
    cfg["adapters"] = {name: "apps/x/adapter.py"} if declared else {}
    problems = sources_problems(cfg)
    assert (not problems) == declared, problems
    assert source_specs(cfg) == [(name, ["videos/*.mp4"])]


@given(st.text(min_size=1, max_size=20))
def test_files_written_as_a_string_is_reported(text):
    """性质 S5：`files` 写成字符串而不是列表，一定报配置问题（不静默当成一项）。"""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["sources"] = {"files": text}
    assert sources_problems(cfg)


def test_paths_outside_the_repo_are_reported():
    """性质 S6：绝对路径、盘符路径和带 `..` 的路径只能是仓库外的，报配置问题。"""
    for bad in ["/etc/*.md", "C:/docs/*.md", "../other/*.md", "docs/../../x.md"]:
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["sources"] = {"files": [bad]}
        problems = sources_problems(cfg)
        assert problems and "仓库内" in problems[0]["note"], (bad, problems)
