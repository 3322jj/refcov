"""提交的清单（apps/layer-coverage/bayside.fields.md）的核对：17 个单元，15 个字段，条数和代码分布和第 0 步一致。

清单由 build.py 从本地抽取文件生成（2026-11-15）。这里只守住它的结构和数字，不重新下载。
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "apps" / "layer-coverage" / "bayside.fields.md"
_spec = importlib.util.spec_from_file_location("layer_adapter", ROOT / "apps" / "layer-coverage" / "adapter.py")
adapter = importlib.util.module_from_spec(_spec)
sys.modules["layer_adapter"] = adapter
_spec.loader.exec_module(adapter)


def test_committed_manifest_has_17_units_and_15_fields():
    """清单结构（设计第 3 节）：crs、extent 各一个，15 个字段；前两个单元是 crs 和 extent。"""
    units = adapter.split(MANIFEST.read_bytes(), "bayside.fields.md")
    assert len(units) == 17
    assert sum(1 for u in units if u.kind == "field") == 15
    assert [u.id for u in units[:2]] == ["crs", "extent"]


def test_committed_manifest_matches_the_subset_counts():
    """数字（设计第 2、5 节）：范围单元的条数是 6018；feature_code 的非空 6018、4 个取值、前 5 个是 4301、1715、1、1。"""
    data = MANIFEST.read_bytes()
    assert adapter.facts(data, "bayside.fields.md", "extent")["rows"] == 6018
    fx = adapter.facts(data, "bayside.fields.md", "feature_code")
    assert (fx["non_null"], fx["distinct"], fx["zeros"]) == (6018, 4, 0)
    body = adapter.read(data, "bayside.fields.md", "feature_code")[0]
    assert "- 2100：4301\n- 5110：1715\n- 1001：1\n- 5100：1" in body


def test_name_is_the_only_field_without_values():
    """数字（设计第 2.1 节）：name 在子集里全为空，其他字段都有非空值。"""
    data = MANIFEST.read_bytes()
    assert adapter.facts(data, "bayside.fields.md", "name")["non_null"] == 0
    for unit_id in ("objectid", "bin", "height_roof", "shape_area"):
        assert adapter.facts(data, "bayside.fields.md", unit_id)["non_null"] == 6018
