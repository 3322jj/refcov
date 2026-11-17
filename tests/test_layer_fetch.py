"""下载脚本的测试（设计第 6 节）：假的 SODA 接口，不联网。

翻页读全部行；计数或分组计数不一致时不写文件；重试的等待是 2、4、8 秒；仓库里的输出路径在联网前就拒绝。
"""

import importlib.util
import json
import sys
import urllib.error
import urllib.parse
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("layer_fetch", ROOT / "apps" / "layer-coverage" / "fetch.py")
fetch = importlib.util.module_from_spec(_spec)
sys.modules["layer_fetch"] = fetch
_spec.loader.exec_module(fetch)
build = fetch.build

CRS84 = "urn:ogc:def:crs:OGC:1.3:CRS84"


def no_sleep(seconds):
    pass


def soda_row(code, objectid, height, **extra):
    """SODA 的一行：the_geom 是 GeoJSON 几何，其余都是字符串。"""
    lon, lat = -73.78, 40.76
    ring = [[lon, lat], [lon + 0.001, lat], [lon + 0.001, lat + 0.001], [lon, lat]]
    return {"the_geom": {"type": "MultiPolygon", "coordinates": [[ring]]},
            "feature_code": code, "objectid": objectid, "height_roof": height, **extra}


ROWS = [
    soda_row("2100", "1", "26.5"),
    soda_row("5110", "2", "0", name="GARAGE"),
    soda_row("2100", "3", "0"),
    soda_row("2100", "4", "9.1"),
    soda_row("1001", "5", "3"),
]


class FakeSoda:
    """假的接口：计数查询返回 count，分组查询返回每个 feature_code 的条数，分页查询按 $limit 和 $offset 切行。"""

    def __init__(self, rows, *, count=None, groups=None, failures=0, status=None, body=None):
        self.rows = rows
        self.count = len(rows) if count is None else count
        self.groups = groups
        self.failures = failures
        self.status = status
        self.body = body
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        if self.failures > 0:
            self.failures -= 1
            raise urllib.error.URLError("temporary failure")
        if self.status is not None:
            raise urllib.error.HTTPError(url, self.status, "fake", None, None)
        if self.body is not None:
            return self.body
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        if q.get("$select") == "count(*)":
            return json.dumps([{"count": str(self.count)}]).encode("utf-8")
        if q.get("$group") == "feature_code":
            counts = self.groups if self.groups is not None else dict(Counter(r["feature_code"] for r in self.rows))
            return json.dumps([{"feature_code": k, "count": str(v)} for k, v in counts.items()]).encode("utf-8")
        limit, offset = int(q["$limit"]), int(q["$offset"])
        return json.dumps(self.rows[offset: offset + limit]).encode("utf-8")


def test_download_pages_through_all_rows_and_writes_geojson(tmp_path, monkeypatch):
    """下载（设计第 6 节）：分页读完全部行，按 :id 排序；缺的键补 null；坐标系写 CRS84；输出能被 build 读。"""
    monkeypatch.setattr(fetch, "PAGE", 2)
    soda = FakeSoda(ROWS)
    out = tmp_path / "bayside.geojson"
    assert fetch.main(["--out", str(out)], get=soda, sleep=no_sleep) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["crs"]["properties"]["name"] == CRS84
    assert len(doc["features"]) == 5
    assert all(set(f["properties"]) == {"objectid", "feature_code", "height_roof", "name"} for f in doc["features"])
    assert doc["features"][0]["properties"]["name"] is None
    assert doc["features"][1]["properties"]["name"] == "GARAGE"
    pages = [u for u in soda.urls if "%24offset=" in u]
    assert len(pages) == 3  # 每页 2 行：偏移 0、2、4；第三页只有 1 行，停
    assert all("%24order=%3Aid" in u for u in pages)
    assert build._load_geojson(out.read_bytes())["rows"] == 5


def test_count_that_disagrees_with_the_rows_writes_nothing(tmp_path):
    """核对（设计第 6 节）：接口计数和下载的行数不一致，退出码 1，不写文件。"""
    out = tmp_path / "bayside.geojson"
    assert fetch.main(["--out", str(out)], get=FakeSoda(ROWS, count=6), sleep=no_sleep) == 1
    assert not out.exists()


def test_group_counts_that_disagree_with_the_rows_write_nothing(tmp_path):
    """核对（设计第 6 节）：每个 feature_code 的条数和分组查询不一致（总数相同），退出码 1，不写文件。"""
    out = tmp_path / "bayside.geojson"
    soda = FakeSoda(ROWS, groups={"2100": 2, "5110": 2, "1001": 1})
    assert fetch.main(["--out", str(out)], get=soda, sleep=no_sleep) == 1
    assert not out.exists()


def test_output_inside_the_repository_is_refused_before_any_request():
    """拒绝（设计第 6 节）：--out 在仓库里时退出码 2，不发出任何请求。"""
    soda = FakeSoda(ROWS)
    inside = ROOT / "bayside-test-output.geojson"
    assert fetch.main(["--out", str(inside)], get=soda, sleep=no_sleep) == 2
    assert soda.urls == []
    assert not inside.exists()


def test_check_prints_the_counts_and_writes_no_file(tmp_path, capsys, monkeypatch):
    """--check（设计第 6 节）：只查条数和分组计数，打印出来，不写任何文件。"""
    monkeypatch.chdir(tmp_path)
    assert fetch.main(["--check"], get=FakeSoda(ROWS), sleep=no_sleep) == 0
    out = capsys.readouterr().out
    assert "接口条数 5" in out and "2100 3" in out and "5110 1" in out
    assert list(tmp_path.iterdir()) == []


def test_network_errors_are_retried_with_waits_2_4_and_8():
    """重试（设计第 6 节）：网络错误连续失败时，等 2、4、8 秒，共 4 次尝试，然后报错。"""
    waits = []
    soda = FakeSoda(ROWS, failures=99)
    url = fetch.query_url({"$select": "count(*)"})
    with pytest.raises(fetch.FetchError):
        fetch.get_json(url, get=soda, sleep=waits.append)
    assert waits == [2, 4, 8]
    assert len(soda.urls) == 4


def test_a_failure_that_clears_is_retried_and_then_succeeds():
    """重试（设计第 6 节）：失败两次后成功，中间只等了 2 和 4 秒。"""
    waits = []
    soda = FakeSoda(ROWS, failures=2)
    url = fetch.query_url({"$select": "count(*)"})
    assert fetch.get_json(url, get=soda, sleep=waits.append) == [{"count": "5"}]
    assert waits == [2, 4]


def test_client_errors_are_not_retried_and_server_errors_are():
    """重试（设计第 6 节）：4xx 直接报错，不重试；5xx 按网络错误重试。"""
    url = fetch.query_url({"$select": "count(*)"})
    waits = []
    client = FakeSoda(ROWS, status=404)
    with pytest.raises(fetch.FetchError):
        fetch.get_json(url, get=client, sleep=waits.append)
    assert waits == [] and len(client.urls) == 1

    waits = []
    server = FakeSoda(ROWS, status=503)
    with pytest.raises(fetch.FetchError):
        fetch.get_json(url, get=server, sleep=waits.append)
    assert waits == [2, 4, 8] and len(server.urls) == 4


def test_a_body_that_is_not_json_is_an_error():
    """读取（设计第 6 节）：接口返回的不是 JSON，报错。"""
    url = fetch.query_url({"$select": "count(*)"})
    with pytest.raises(fetch.FetchError, match="JSON"):
        fetch.get_json(url, get=FakeSoda(ROWS, body=b"<html>"), sleep=no_sleep)


def test_a_failed_download_leaves_no_file(tmp_path):
    """下载（设计第 6 节）：接口一直失败时退出码 1，输出文件不存在。"""
    out = tmp_path / "bayside.geojson"
    assert fetch.main(["--out", str(out)], get=FakeSoda(ROWS, failures=99), sleep=no_sleep) == 1
    assert not out.exists()


def test_a_row_without_geometry_is_an_error():
    """转换（设计第 6 节）：有一行没有 the_geom，报错。"""
    bad = [dict(ROWS[0])]
    del bad[0]["the_geom"]
    with pytest.raises(fetch.FetchError, match="几何"):
        fetch.to_geojson(bad)


def test_queries_use_percent_encoding_not_plus_for_spaces():
    """查询（设计第 6 节）：SoQL 里的空格写成 %20，不写成加号。"""
    url = fetch.query_url({"$where": fetch.SUBSET_WHERE, "$order": ":id"})
    assert "+" not in urllib.parse.urlsplit(url).query
    assert "%20" in url and "%24where=" in url and "%24order=%3Aid" in url
