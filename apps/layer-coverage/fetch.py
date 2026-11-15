"""下载 Bayside 子集（设计第 6 节）：分页读 SODA 接口，核对条数和分组计数，写成 GeoJSON。

用法：
    python apps/layer-coverage/fetch.py --out <文件>    下载，核对通过后写入（输出不能在仓库里）
    python apps/layer-coverage/fetch.py --check         只查条数和分组计数，不写文件

只用标准库。接口读不到或核对不一致时退出码 1，什么也不写；--out 在仓库里时退出码 2，不联网。
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
API = "https://data.cityofnewyork.us/resource/5zhs-2jue.json"
PAGE = 50000
TIMEOUT = 60
RETRY_WAITS = (2, 4, 8)  # 第 1、2、3 次重试前等的秒数（设计第 6 节）
USER_AGENT = "refcov-layer-coverage/1"


def _sibling(name: str):
    """同目录的 build.py。子集条件和坐标系名只在那里写一份。"""
    key = f"layer_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod  # dataclass 解析注解时要从 sys.modules 找回模块
    spec.loader.exec_module(mod)
    return mod


build = _sibling("build")
SUBSET_WHERE = build.SUBSET_WHERE
CRS84 = build.CRS84


class FetchError(Exception):
    """接口读不到，或核对不一致。"""


def http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def query_url(params: dict) -> str:
    # quote 而不是 quote_plus：SoQL 里的空格要写成 %20
    return API + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def get_json(url: str, get=http_get, sleep=time.sleep):
    """读一个接口并解析 JSON。网络错误和 5xx 重试，等待见 RETRY_WAITS；4xx 和坏的 JSON 不重试。"""
    error = None
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            body = get(url)
        except urllib.error.HTTPError as e:
            if e.code < 500:
                raise FetchError(f"接口返回 {e.code}：{url}") from e
            error = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            error = e
        else:
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise FetchError(f"接口返回的不是 JSON：{e}") from e
        if attempt < len(RETRY_WAITS):
            sleep(RETRY_WAITS[attempt])
    raise FetchError(f"接口连续 {len(RETRY_WAITS) + 1} 次失败：{error}") from error


def count_total(read) -> int:
    rows = read(query_url({"$select": "count(*)", "$where": SUBSET_WHERE}))
    return int(next(iter(rows[0].values())))


def count_by_code(read) -> dict:
    rows = read(query_url({"$select": "feature_code,count(*)", "$where": SUBSET_WHERE, "$group": "feature_code"}))
    out = {}
    for row in rows:
        n = next(v for k, v in row.items() if k != "feature_code")
        out[row.get("feature_code")] = int(n)
    return out


def fetch_rows(read, total: int) -> list:
    """按 $order=:id 分页读完全部行，条数必须等于 count(*)。"""
    rows, offset = [], 0
    while True:
        page = read(query_url({"$where": SUBSET_WHERE, "$order": ":id", "$limit": str(PAGE), "$offset": str(offset)}))
        if not isinstance(page, list):
            raise FetchError("分页的结果不是列表")
        rows.extend(page)
        if len(page) < PAGE:
            break
        offset += PAGE
    if len(rows) != total:
        raise FetchError(f"下载了 {len(rows)} 条，接口计数是 {total} 条")
    return rows


def to_geojson(rows: list) -> dict:
    """SODA 的行变成 GeoJSON 要素：the_geom 是几何，其余键是属性；缺的键补 null。"""
    keys, seen = [], set()
    for row in rows:
        for k in row:
            if k != "the_geom" and k not in seen:
                seen.add(k)
                keys.append(k)
    features = []
    for row in rows:
        geom = row.get("the_geom")
        if not isinstance(geom, dict):
            raise FetchError("有一行没有几何（the_geom）")
        features.append({"type": "Feature", "properties": {k: row.get(k) for k in keys}, "geometry": geom})
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": CRS84}},
        "features": features,
    }


def download(read) -> bytes:
    """下载并核对，返回 GeoJSON 的字节。任何一步不对都抛 FetchError，不返回半成品。"""
    total = count_total(read)
    groups = count_by_code(read)
    if sum(groups.values()) != total:
        raise FetchError(f"分组计数加起来是 {sum(groups.values())}，总计数是 {total}")
    rows = fetch_rows(read, total)
    actual = dict(Counter(row.get("feature_code") for row in rows))
    if actual != groups:
        raise FetchError(f"每个 feature_code 的条数和分组查询不一致：下载 {actual}，接口 {groups}")
    return json.dumps(to_geojson(rows), ensure_ascii=False).encode("utf-8")


def inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
        return True
    except ValueError:
        return False


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def main(argv=None, get=http_get, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description="下载 Bayside 子集（只读接口，输出写到仓库外）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", help="输出的 GeoJSON 文件（不能在仓库里）")
    group.add_argument("--check", action="store_true", help="只查条数和分组计数，不写文件")
    args = parser.parse_args(argv)

    if args.out and inside_repo(Path(args.out)):
        print("错误：--out 不能在仓库里（数据不进仓库）", file=sys.stderr)
        return 2

    def read(url):
        return get_json(url, get=get, sleep=sleep)

    try:
        if args.check:
            total = count_total(read)
            groups = count_by_code(read)
            print(f"接口条数 {total}；分组：" + "、".join(f"{k} {v}" for k, v in sorted(groups.items(), key=str)))
            return 0
        data = download(read)
    except FetchError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    out = Path(args.out)
    write_atomic(out, data)
    print(f"已写入 {out}：{len(data)} 字节，sha256 {hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
