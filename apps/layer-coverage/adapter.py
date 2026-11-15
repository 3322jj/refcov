"""图层适配器 `layer`（设计第 4 节）：把 `bayside.fields.md` 拆成单元。

只用标准库和 `refcov.sources`。导入时不做任何耗时的事：顶层只有 import、常量、
`KindDecl(...)` 赋值、函数和类定义（tests/test_layer_adapter_import.py 守着这条）。

清单格式（设计第 3 节）：每个单元是一节 `## <单元 ID>`，节的第一行是 `kind: crs`、
`kind: extent` 或 `kind: field`，其余是正文。标题前的文字不是单元。
"""

import re

from refcov.sources import KindDecl, Unit, normalize_newlines, validate_unit_id

name = "layer"
kinds = {
    "field": KindDecl(strict=True, key=False),
    "crs": KindDecl(strict=True, key=True),
    "extent": KindDecl(strict=True, key=True),
}

TITLES = {"crs": "坐标系", "extent": "范围和数据来源"}


def _decode(data: bytes) -> str:
    return normalize_newlines(data.decode("utf-8"))


def _sections(text: str) -> list:
    """按行首的 `## ` 切段：返回 [(单元 ID, 正文行列表)]。"""
    out = []
    for line in text.split("\n"):
        m = re.match(r"^## (.+)$", line)
        if m:
            out.append((m.group(1).strip(), []))
        elif out:
            out[-1][1].append(line)
    return out


def _kind_of(unit_id: str, body: str) -> str:
    first = body.split("\n", 1)[0]
    m = re.match(r"^kind: (\w+)$", first)
    if not m or m.group(1) not in kinds:
        raise ValueError(f"单元 {unit_id} 的第一行必须是 kind: field、kind: crs 或 kind: extent")
    return m.group(1)


def _title(unit_id: str, kind: str, body: str) -> str:
    if kind in TITLES:
        return TITLES[kind]
    m = re.search(r"字典名：([^；\n]+)", body)
    return f"{unit_id}（字典名 {m.group(1).strip()}）" if m else unit_id


def split(data: bytes, file_name: str) -> list:
    """把清单拆成单元。ID 重复、ID 不合法、kind 缺失或不认识，都抛 ValueError。"""
    units = []
    seen = set()
    for unit_id, lines in _sections(_decode(data)):
        validate_unit_id(unit_id)
        if unit_id in seen:
            raise ValueError(f"单元 ID 重复：{unit_id}")
        seen.add(unit_id)
        body = "\n".join(lines).strip("\n")
        kind = _kind_of(unit_id, body)
        units.append(Unit(id=unit_id, title=_title(unit_id, kind, body), kind=kind, text=body))
    return units


def _find(data: bytes, file_name: str, unit_id: str) -> Unit:
    for unit in split(data, file_name):
        if unit.id == unit_id:
            return unit
    raise KeyError(unit_id)


def read(data: bytes, file_name: str, unit_id: str) -> list:
    """返回一个单元的正文（只有文字，没有图片）。单元不存在时抛 KeyError。"""
    return [_find(data, file_name, unit_id).text]


def _field_facts(unit: Unit) -> dict:
    m = re.search(r"^数据：非空 (\d+) 条；不同取值 (\d+) 个；值为 0 的条数 (\d+)。$", unit.text, re.M)
    if not m:
        raise ValueError(f"字段单元 {unit.id} 缺少'数据：'行")
    return {"non_null": int(m.group(1)), "distinct": int(m.group(2)), "zeros": int(m.group(3))}


def _extent_facts(unit: Unit) -> dict:
    lon = re.search(r"^经度：最小 (-?\d+(?:\.\d+)?)，最大 (-?\d+(?:\.\d+)?)。$", unit.text, re.M)
    lat = re.search(r"^纬度：最小 (-?\d+(?:\.\d+)?)，最大 (-?\d+(?:\.\d+)?)。$", unit.text, re.M)
    rows = re.search(r"^条数：(\d+)。$", unit.text, re.M)
    if not (lon and lat and rows):
        raise ValueError(f"范围单元 {unit.id} 缺少经度、纬度或条数的行")
    return {
        "lon_min": float(lon.group(1)), "lon_max": float(lon.group(2)),
        "lat_min": float(lat.group(1)), "lat_max": float(lat.group(2)),
        "rows": int(rows.group(1)),
    }


def facts(data: bytes, file_name: str, unit_id: str) -> dict:
    """单元可核对的事实。每个单元有 id 和 kind；字段另有非空数、不同取值数、零的条数；范围另有经纬度和条数。"""
    unit = _find(data, file_name, unit_id)
    out = {"id": unit.id, "kind": unit.kind}
    if unit.kind == "field":
        out.update(_field_facts(unit))
    elif unit.kind == "extent":
        out.update(_extent_facts(unit))
    return out
