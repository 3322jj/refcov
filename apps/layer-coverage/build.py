"""生成 `bayside.fields.md`（设计第 2.1、3、7 节）：读本地 GeoJSON 和字典网址，写清单。

用法：python apps/layer-coverage/build.py --geojson <文件> [--dictionary-url <网址>] [--out <文件>]
退出码：0 成功；1 数据和字典对不上，或读不了网址和文件；2 命令行写错。只用标准库。
"""

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DICTIONARY_URL = (
    "https://raw.githubusercontent.com/CityOfNewYork/nyc-geo-metadata/main/Metadata/Metadata_BuildingFootprints.md"
)
# 下载子集用的条件（fetch.py 也用它）
SUBSET_WHERE = "within_box(the_geom, 40.770, -73.785, 40.755, -73.765)"
CRS84 = "urn:ogc:def:crs:OGC:1.3:CRS84"
MANIFEST_NAME = "bayside.fields.md"
DEFAULT_OUT = HERE / MANIFEST_NAME
PREAMBLE = "# 纽约建筑轮廓：Bayside 子集，字段清单\n\n由 apps/layer-coverage/build.py 生成，手改会被覆盖。\n"
HEADER_ROW = re.compile(r"^\|\s*Attribute\s*\|\s*Shapefile Attribute\s*\|")
SEPARATOR_ROW = re.compile(r"^\|[-\s|]+\|?$")


def _sibling(name: str):
    """同目录的模块（stats、adapter）。已经登记过的直接用，避免同一个文件装了两份。"""
    key = f"layer_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod  # dataclass 解析注解时要从 sys.modules 找回模块
    spec.loader.exec_module(mod)
    return mod


layer_adapter = _sibling("adapter")
stats = _sibling("stats")


class BuildError(Exception):
    """数据或字典对不上，清单写不出来。"""


def fetch_dictionary(url: str, timeout: float = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "refcov-layer-coverage/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_attribute_table(text: str) -> list:
    """字典的 Attribute 表：每行 5 列。返回每行的别名列表（`<br>` 分开）和其余四列。"""
    lines = text.split("\n")
    start = next((i + 1 for i, line in enumerate(lines) if HEADER_ROW.match(line)), None)
    if start is None:
        raise BuildError("字典里找不到 Attribute 表的表头")
    rows = []
    for line in lines[start:]:
        s = line.strip()
        if not s.startswith("|"):
            break
        if SEPARATOR_ROW.match(s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) != 5:
            raise BuildError(f"Attribute 表有一行不是 5 列：{s[:80]}")
        aliases = [a.strip() for a in cells[0].split("<br>") if a.strip()]
        rows.append({
            "aliases": aliases, "shapefile": cells[1], "description": cells[2],
            "type": cells[3], "notes": cells[4],
        })
    if not rows:
        raise BuildError("Attribute 表没有数据行")
    return rows


def map_keys(keys: list, rows: list):
    """数据里的键对应字典的哪一行（别名不分大小写）。

    返回 (按字典顺序排好的 [(键, 行)], 字典有而数据没有的名字, 数据里字典对不上的键)。
    """
    by_alias = {}
    for row in rows:
        for alias in row["aliases"]:
            # 同一行里大小写不同的别名（SHAPE_AREA 和 shape_area）是同一个名字，不算重复
            if alias.lower() in by_alias and by_alias[alias.lower()] is not row:
                raise BuildError(f"字典里的名字 {alias} 出现在两行")
            by_alias[alias.lower()] = row
    pairs = {}
    unmatched = []
    for key in keys:
        row = by_alias.get(key.lower())
        if row is None:
            unmatched.append(key)
            continue
        if any(r is row for r in pairs.values()):
            raise BuildError(f"数据里的 {key} 和另一个键对应字典的同一行")
        pairs[key] = row
    order = {id(r): i for i, r in enumerate(rows)}
    matched = sorted(pairs.items(), key=lambda kv: order[id(kv[1])])
    used = {id(row) for _, row in matched}
    dictionary_only = [" / ".join(r["aliases"]) for r in rows if id(r) not in used and r["aliases"] != ["SHAPE"]]
    return matched, dictionary_only, unmatched


def _find_alias(rows: list, alias: str) -> dict:
    for row in rows:
        if alias.lower() in (a.lower() for a in row["aliases"]):
            return row
    raise BuildError(f"字典里没有 {alias} 那一行")


def _text_lines(text: str) -> list:
    """字典的一格文字：`<br>` 换成换行，去掉空行；以 # 开头的行会被当成标题，拒绝。"""
    lines = [line.strip() for line in text.split("<br>")]
    lines = [line for line in lines if line]
    for line in lines:
        if line.startswith("#") or "\r" in line:
            raise BuildError(f"字典文字里有以 # 开头的行，会被当成标题：{line[:40]}")
    return lines or ["（无）"]


def _plain(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise BuildError(f"数据里的取值有换行，清单写不下：{value!r}")
    return value


def _load_geojson(data: bytes) -> dict:
    try:
        gj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BuildError(f"GeoJSON 读不了：{e}") from e
    if not isinstance(gj, dict) or gj.get("type") != "FeatureCollection":
        raise BuildError("不是 FeatureCollection")
    crs = ((gj.get("crs") or {}).get("properties") or {}).get("name")
    if crs != CRS84:
        raise BuildError(f"坐标系不是 CRS84：{crs!r}")
    features = gj.get("features") or []
    if not features:
        raise BuildError("GeoJSON 里没有要素")
    props, keys, types = [], [], Counter()
    lon_min = lat_min = math.inf
    lon_max = lat_max = -math.inf
    try:
        for feature in features:
            geom = feature.get("geometry") or {}
            if geom.get("type") != "MultiPolygon":
                raise BuildError(f"几何不是 MultiPolygon：{geom.get('type')!r}")
            types[geom["type"]] += 1
            for polygon in geom["coordinates"]:
                for ring in polygon:
                    for point in ring:
                        lon_min, lon_max = min(lon_min, point[0]), max(lon_max, point[0])
                        lat_min, lat_max = min(lat_min, point[1]), max(lat_max, point[1])
            p = feature.get("properties") or {}
            props.append(p)
            for k in p:
                if k not in keys:
                    keys.append(k)
    except (AttributeError, IndexError, KeyError, TypeError) as e:
        raise BuildError(f"GeoJSON 的要素格式不对：{e}") from e
    if math.isinf(lon_min):
        raise BuildError("GeoJSON 里没有坐标")
    return {
        "props": props, "keys": keys, "types": types, "rows": len(features),
        "bbox": (lon_min, lon_max, lat_min, lat_max), "sha256": hashlib.sha256(data).hexdigest(),
    }


def _labelled(label: str, text: str) -> list:
    """字典的一格文字，第一行接在标签后面，其余行原样接下去。"""
    lines = _text_lines(text)
    return [label + lines[0], *lines[1:]]


def _crs_section(gj: dict, area_row: dict, shape_row: dict) -> str:
    kinds = "、".join(f"{t} {n} 个" for t, n in sorted(gj["types"].items()))
    lines = [
        "## crs", "kind: crs",
        f"几何类型：{kinds}。",
        f"坐标系：{CRS84}（经度在前，纬度在后）。",
        *_labelled("字典 SHAPE 行原文（几何）：", shape_row["description"]),
        *_labelled("字典 Area 行原文：", area_row["description"]),
    ]
    return "\n".join(lines)


def _extent_section(gj: dict, dictionary_url: str, dictionary_sha: str, dictionary_only: list) -> str:
    lon_min, lon_max, lat_min, lat_max = gj["bbox"]
    only = "、".join(dictionary_only) if dictionary_only else "（无）"
    return "\n".join([
        "## extent", "kind: extent",
        f"经度：最小 {lon_min:.6f}，最大 {lon_max:.6f}。",
        f"纬度：最小 {lat_min:.6f}，最大 {lat_max:.6f}。",
        f"条数：{gj['rows']}。",
        f"子集的取法：{SUBSET_WHERE}。",
        f"GeoJSON 的 sha256：{gj['sha256']}。",
        f"字典网址：{dictionary_url}",
        f"字典的 sha256：{dictionary_sha}。",
        f"字典里有、数据里没有的字段：{only}。",
    ])


def _field_section(key: str, row: dict, values: list) -> str:
    st = stats.stats_of(values)
    desc = _text_lines(row["description"])
    notes = _text_lines(row["notes"])
    lines = [
        f"## {key}", "kind: field",
        f"字典名：{' / '.join(row['aliases'])}；形状文件名：{row['shapefile']}；字典类型：{row['type']}。",
        "字典说明：" + desc[0], *desc[1:],
        "字典注意：" + notes[0], *notes[1:],
        f"数据：非空 {st.non_null} 条；不同取值 {st.distinct} 个；值为 0 的条数 {st.zeros}。",
        "数据里的类型：" + ("、".join(st.types) if st.types else "（全部为空）") + "。",
        "取值分布（前 5 个，按条数从多到少，同数按文字排序）：",
    ]
    if st.top:
        lines += [f"- {_plain(text)}：{n}" for text, n in st.top]
    else:
        lines.append("（没有非空值）")
    return "\n".join(lines)


def build_manifest(geojson_bytes: bytes, dictionary_bytes: bytes, dictionary_url: str) -> str:
    """由 GeoJSON 字节和字典字节生成清单文字。同样的输入，输出的字节相同。数据和字典对不上时抛 BuildError。"""
    gj = _load_geojson(geojson_bytes)
    try:
        dictionary_text = dictionary_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise BuildError(f"字典不是 UTF-8：{e}") from e
    rows = parse_attribute_table(dictionary_text)
    matched, dictionary_only, unmatched = map_keys(gj["keys"], rows)
    if unmatched:
        raise BuildError("数据里有字典对不上的字段：" + "、".join(unmatched))
    sections = [
        _crs_section(gj, _find_alias(rows, "shape_area"), _find_alias(rows, "SHAPE")),
        _extent_section(gj, dictionary_url, hashlib.sha256(dictionary_bytes).hexdigest(), dictionary_only),
    ]
    for key, row in matched:
        sections.append(_field_section(key, row, [p.get(key) for p in gj["props"]]))
    text = PREAMBLE + "\n" + "\n\n".join(sections) + "\n"
    try:
        units = layer_adapter.split(text.encode("utf-8"), MANIFEST_NAME)
    except ValueError as e:
        raise BuildError(f"生成的清单拆不开：{e}") from e
    expected = ["crs", "extent"] + [key for key, _ in matched]
    if [u.id for u in units] != expected:
        raise BuildError("生成的清单单元和预期不一致")
    return text


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成 Bayside 子集的字段清单（不下载，只读本地 GeoJSON）")
    parser.add_argument("--geojson", required=True, help="本地 GeoJSON 文件（仓库外）")
    parser.add_argument("--dictionary-url", default=DICTIONARY_URL, help="字典的网址")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="清单输出文件")
    args = parser.parse_args(argv)
    try:
        geojson_bytes = Path(args.geojson).read_bytes()
        dictionary_bytes = fetch_dictionary(args.dictionary_url)
        text = build_manifest(geojson_bytes, dictionary_bytes, args.dictionary_url)
    except BuildError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"错误：读不了文件或网址：{e}", file=sys.stderr)
        return 1
    write_atomic(Path(args.out), text.encode("utf-8"))
    fields = [u for u in layer_adapter.split(text.encode("utf-8"), MANIFEST_NAME) if u.kind == "field"]
    print(f"已写入 {args.out}：{len(fields)} 个字段；另有坐标系和范围各 1 个。")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
