"""字段统计的性质测试（设计第 5 节 P1–P5）和几个固定例子（apps/layer-coverage/stats.py）。"""

import dataclasses
import importlib.util
import sys
from pathlib import Path

from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("layer_stats", ROOT / "apps" / "layer-coverage" / "stats.py")
stats = importlib.util.module_from_spec(_spec)
# dataclass 解析字符串注解时要从 sys.modules 按模块名找回模块（核心层的适配器加载器也这样做）
sys.modules["layer_stats"] = stats
_spec.loader.exec_module(stats)

VALUE = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-3, max_value=3),
    st.floats(min_value=-3, max_value=3, allow_nan=False, allow_infinity=False),
    st.sampled_from(["0", "0.0", " 0 ", "-0", "1", "", "a", "2100", "4301", "纽约", "[x]"]),
)
VALUES = st.lists(VALUE, max_size=60)

# (值, 按设计应当算作零)
ZERO_CASES = [
    (0, True), (0.0, True), ("0", True), ("0.0", True), (" 0 ", True), ("-0", True),
    ("1", False), (-1, False), ("", False), ("a", False), (None, False),
    (True, False), (False, False),
]


@settings(max_examples=200, deadline=None)
@given(VALUES)
def test_p1_conservation(values):
    """性质 P1 守恒（设计第 5 节）：非空数等于各取值条数之和；不同取值数等于取值种类数；前 5 个的条数是真实条数。"""
    counts = stats.value_counts(values)
    s = stats.stats_of(values)
    assert s.non_null == sum(1 for v in values if v is not None) == sum(counts.values())
    assert s.distinct == len(counts)
    assert s.rows == len(values)
    assert len(s.top) == min(stats.TOP_N, s.distinct)
    for text, n in s.top:
        assert counts[text] == n


@settings(max_examples=200, deadline=None)
@given(VALUES)
def test_p2_top_is_first_five_in_order(values):
    """性质 P2 顺序（设计第 5 节）：前 5 个是按（条数降序、文字升序）排好的前 5 个。"""
    s = stats.stats_of(values)
    counts = stats.value_counts(values)
    expected = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[: stats.TOP_N]
    assert list(s.top) == expected
    keys = [(-n, t) for t, n in s.top]
    assert keys == sorted(keys)


@settings(max_examples=200, deadline=None)
@given(VALUES, st.data())
def test_p3_order_does_not_matter(values, data):
    """性质 P3 排列不变（设计第 5 节）：打乱输入的顺序，统计结果完全相同。"""
    shuffled = data.draw(st.permutations(values))
    assert stats.stats_of(shuffled) == stats.stats_of(values)


@settings(max_examples=200, deadline=None)
@given(VALUES, st.integers(min_value=0, max_value=5))
def test_p4_nulls_only_change_rows(values, extra):
    """性质 P4 null 不变（设计第 5 节）：加入 null 只让行数增加，其余统计不变。"""
    base = stats.stats_of(values)
    more = stats.stats_of(list(values) + [None] * extra)
    assert more == dataclasses.replace(base, rows=base.rows + extra)


@settings(max_examples=200, deadline=None)
@given(st.lists(st.sampled_from(ZERO_CASES), max_size=60))
def test_p5_zeros_follow_the_rule(pairs):
    """性质 P5 零（设计第 5 节）：零的条数等于按规则算作零的值的个数（布尔、空字符串、null 不算）。"""
    values = [v for v, _ in pairs]
    assert stats.stats_of(values).zeros == sum(1 for _, z in pairs if z)


def test_empty_input():
    """固定例子：空输入的统计全为 0 或空。"""
    s = stats.stats_of([])
    assert (s.rows, s.non_null, s.distinct, s.top, s.zeros, s.types) == (0, 0, 0, (), 0, ())


def test_only_nulls_has_no_types():
    """固定例子：只有 null 时，非空数和类型都为空。"""
    s = stats.stats_of([None, None])
    assert (s.rows, s.non_null, s.distinct, s.top, s.zeros, s.types) == (2, 0, 0, (), 0, ())


def test_name_column_of_bayside_is_all_null():
    """固定例子：子集里 name 全为 null（设计第 2.1 节）。"""
    s = stats.stats_of([None] * 6018)
    assert s.rows == 6018 and s.non_null == 0


def test_ties_are_sorted_by_text_and_empty_string_is_a_value():
    """固定例子：同数按文字排序；空字符串是一个取值，不是 null，也不算零。"""
    s = stats.stats_of(["0.0", "", "0", "a"])
    assert s.top == (("", 1), ("0", 1), ("0.0", 1), ("a", 1))
    assert s.zeros == 2
    assert s.non_null == 4


def test_top_is_capped_at_five():
    """固定例子：前 5 个之外的取值不列出，但不同取值数照常计。"""
    s = stats.stats_of(["a"] * 3 + ["b"] * 2 + ["c", "d", "e", "f", "g", "h"])
    assert s.top == (("a", 3), ("b", 2), ("c", 1), ("d", 1), ("e", 1))
    assert s.distinct == 8


def test_booleans_have_text_forms_and_are_not_zero():
    """固定例子：布尔有文字形式 true、false；布尔不算零，整数 0 算零。"""
    s = stats.stats_of([True, False, 0])
    assert s.zeros == 1  # 只有整数 0
    assert ("true", 1) in s.top and ("false", 1) in s.top
    assert s.types == ("bool", "int")


def test_int_and_string_with_same_text_are_one_value():
    """固定例子：整数 2100 和字符串 "2100" 的文字形式相同，算同一个取值。"""
    s = stats.stats_of([2100, "2100"])
    assert s.distinct == 1 and s.top == (("2100", 2),) and s.types == ("int", "str")
