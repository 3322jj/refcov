"""图层适配器的测试（设计第 4、11 节）：拆分、读取、事实、错误情况、编码，以及性质 A1（单元互不影响）。"""

import importlib.util
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "apps" / "layer-coverage" / "adapter.py"
_spec = importlib.util.spec_from_file_location("layer_adapter", ADAPTER_PATH)
adapter = importlib.util.module_from_spec(_spec)
sys.modules["layer_adapter"] = adapter  # dataclass 解析注解时要从 sys.modules 找回模块（同 test_layer_stats.py）
_spec.loader.exec_module(adapter)

FILE = "bayside.fields.md"

SAMPLE = """# 纽约建筑轮廓：Bayside 子集，字段清单

由 build.py 生成，手改会被覆盖。

## crs
kind: crs
几何类型：MultiPolygon 2 个。
坐标系：urn:ogc:def:crs:OGC:1.3:CRS84。

## extent
kind: extent
经度：最小 -73.785002，最大 -73.765003。
纬度：最小 40.754998，最大 40.769992。
条数：2。

## feature_code
kind: field
字典名：FEATURE_CODE；形状文件名：FEAT_CODE；字典类型：number。
字典说明：Type of Building. 建筑类型。
数据：非空 2 条；不同取值 2 个；值为 0 的条数 0。
取值分布（前 5 个，按条数从多到少，同数按文字排序）：
- 2100：1
- 5110：1
"""


def units(text: str):
    return adapter.split(text.encode("utf-8"), FILE)


def test_split_gives_units_in_order_with_kinds_and_titles():
    """拆分（设计第 4 节）：单元按清单顺序排列；ID 来自节标题；kind 来自节的第一行；标题按 kind 生成。"""
    us = units(SAMPLE)
    assert [u.id for u in us] == ["crs", "extent", "feature_code"]
    assert [u.kind for u in us] == ["crs", "extent", "field"]
    assert us[0].title == "坐标系"
    assert us[1].title == "范围和数据来源"
    assert us[2].title == "feature_code（字典名 FEATURE_CODE）"


def test_unit_text_is_the_section_body_without_heading_or_outer_blank_lines():
    """拆分（设计第 4 节）：单元正文不含标题行，首尾的空行去掉，第一行是 kind 行。"""
    us = units(SAMPLE)
    assert us[2].text.startswith("kind: field\n字典名：FEATURE_CODE")
    assert us[2].text.endswith("- 5110：1")
    assert "## feature_code" not in us[2].text
    assert not us[0].text.endswith("\n")


def test_text_before_the_first_heading_is_not_a_unit():
    """拆分（设计第 4 节）：标题前的说明不是单元。"""
    assert "由 build.py 生成" not in "".join(u.text for u in units(SAMPLE))


def test_read_returns_only_the_text_of_that_unit():
    """读取（设计第 4 节）：read 只返回这一单元的正文，没有图片。"""
    got = adapter.read(SAMPLE.encode("utf-8"), FILE, "extent")
    assert got == [units(SAMPLE)[1].text]
    assert all(isinstance(x, str) for x in got)


def test_read_of_missing_unit_raises_key_error():
    """读取（设计第 4 节）：单元不存在时抛 KeyError。"""
    with pytest.raises(KeyError):
        adapter.read(SAMPLE.encode("utf-8"), FILE, "no-such-unit")


def test_facts_of_field_extent_and_crs():
    """事实（设计第 4 节）：字段给非空数、不同取值数、零的条数；范围给经纬度和条数；每个单元都有 id 和 kind。"""
    data = SAMPLE.encode("utf-8")
    assert adapter.facts(data, FILE, "feature_code") == {
        "id": "feature_code", "kind": "field", "non_null": 2, "distinct": 2, "zeros": 0,
    }
    assert adapter.facts(data, FILE, "extent") == {
        "id": "extent", "kind": "extent",
        "lon_min": -73.785002, "lon_max": -73.765003, "lat_min": 40.754998, "lat_max": 40.769992, "rows": 2,
    }
    assert adapter.facts(data, FILE, "crs") == {"id": "crs", "kind": "crs"}


def test_facts_of_a_field_without_its_data_line_raise():
    """事实（设计第 4 节）：字段节缺少'数据：'行时抛 ValueError，而不是给出假数字。"""
    bad = SAMPLE.replace("数据：非空 2 条；不同取值 2 个；值为 0 的条数 0。\n", "")
    with pytest.raises(ValueError):
        adapter.facts(bad.encode("utf-8"), FILE, "feature_code")


MALFORMED = {
    "no kind line": "## crs\n几何类型：MultiPolygon。\n",
    "unknown kind": "## crs\nkind: map\n",
    "empty section": "## crs\n",
    "duplicate id": "## a\nkind: field\n\n## a\nkind: field\n",
    "id with a space": "## bad id\nkind: field\n",
    "id with brackets": "## [x]\nkind: field\n",
}


@pytest.mark.parametrize("case", sorted(MALFORMED), ids=sorted(MALFORMED))
def test_split_rejects_malformed_sections(case):
    """拆分（设计第 4 节）：缺 kind 行、kind 不认识、空段、ID 重复、ID 含空白或方括号，都抛 ValueError。"""
    with pytest.raises(ValueError):
        adapter.split(MALFORMED[case].encode("utf-8"), FILE)


def test_crlf_and_lf_give_the_same_units():
    """编码（设计第 4 节，核心层的换行规则）：CRLF 和 LF 拆出的单元完全相同。"""
    crlf = SAMPLE.replace("\n", "\r\n").encode("utf-8")
    assert adapter.split(crlf, FILE) == units(SAMPLE)


def test_bytes_that_are_not_utf8_raise_value_error():
    """编码（设计第 4 节）：不是 UTF-8 的字节抛 ValueError（UnicodeDecodeError 是它的子类）。"""
    with pytest.raises(ValueError):
        adapter.split(b"\xff\xfe## crs\nkind: crs\n", FILE)


TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r\n"),
    max_size=30,
)


def manifest_with_notes(note_f1: str, note_f2: str) -> bytes:
    field = "kind: field\n字典说明：{}\n数据：非空 1 条；不同取值 1 个；值为 0 的条数 0。\n"
    body = (
        "## crs\nkind: crs\n几何类型：MultiPolygon。\n\n"
        "## f1\n" + field.format(note_f1) + "\n"
        "## f2\n" + field.format(note_f2)
    )
    return body.encode("utf-8")


@settings(max_examples=200, deadline=None)
@given(TEXT, TEXT, TEXT)
def test_a1_changing_one_unit_changes_only_its_hash(a, b, c):
    """性质 A1 单元互不影响（设计第 4 节）：改动一个字段节的正文，只有它的校验值变；其他单元的校验值不变。"""
    before = {u.id: u.sha256 for u in adapter.split(manifest_with_notes(a, b), FILE)}
    after = {u.id: u.sha256 for u in adapter.split(manifest_with_notes(c, b), FILE)}
    if c == a:
        assert before == after
    else:
        assert after["f1"] != before["f1"]
    assert after["f2"] == before["f2"]
    assert after["crs"] == before["crs"]
