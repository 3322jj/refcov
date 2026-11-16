"""Tests for site/convert_runs.py.

The fixtures use the real run folder and file names, but every record is made
up, so no real run record is read and the tests run the same on Linux and
Windows CI.
"""

from __future__ import annotations

import builtins
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "site_convert_runs", ROOT / "site" / "convert_runs.py"
)
convert_runs = importlib.util.module_from_spec(_SPEC)
sys.modules["site_convert_runs"] = convert_runs
_SPEC.loader.exec_module(convert_runs)

STATE_DIR = ".refcov"
KEYS = ("w-h-03", "wb-h-03", "g-01", "vb-01")
W_FOLDER = "webhaiku-20261115-173415"
WB_FOLDER = "webrefcovhaiku-20261115-173528"
G_FOLDER = "gis-20261115-213112"
V_FOLDER = "20261114-180540"
CHINESE_UNIT = "演示页方案（用户-2026-11-16-拍板）"

WB_HTML = (
    '<dialog closedby="any"></dialog>\n'
    '<input required><span class="error">:user-invalid</span>\n'
    "<style>body { overscroll-behavior: contain; }</style>\n"
)
SHOTS_TEXT = """threshold: 0.25
min_shot: 0.5
shots: 3

## shot-00-00-0
start: 0.0
end: 3.9

## shot-00-03-9
start: 3.9
end: 6.6

## shot-00-06-6
start: 6.6
end: 9.0
"""

ALLOWED_NUMBERS = {
    ("blocks",),
    ("schema",),
    ("seconds",),
    ("tool_calls",),
    ("must_read", "read"),
    ("must_read", "total"),
    ("shots", "*", "start"),
    ("shots", "*", "end"),
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json(path: Path, obj: dict) -> None:
    _write(path, json.dumps(obj))


def _lines(path: Path, records: list[dict]) -> None:
    text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    _write(path, text)


def _update(kind: str, **fields: object) -> dict:
    update = {"sessionUpdate": kind, **fields}
    return {"type": "sessionUpdate", "data": {"sessionId": "sess-test", "update": update}}


def _call(call_id: str, title: str, raw: dict) -> dict:
    return _update("tool_call", toolCallId=call_id, title=title, status="in_progress", rawInput=raw)


def _done(call_id: str, status: str = "completed") -> dict:
    return _update("tool_call_update", toolCallId=call_id, status=status)


def _message() -> dict:
    return _update("agent_message_chunk", content={"type": "text", "text": "SECRET-REPORT-TEXT"})


def _rec(seq: int, kind: str, **fields: object) -> dict:
    return {"type": kind, "seq": seq, "time": "2026-11-15T17:35:00+09:00", "session": "sess-test", **fields}


def _read(seq: int, source: str, unit: str) -> dict:
    return _rec(seq, "read", source=source, unit=unit, call=f"call-{seq}", unit_sha256="0" * 64)


def _block(seq: int, target: str, missing: list[str]) -> dict:
    return _rec(seq, "block", target=target, count=len(missing), missing=missing, gate="write")


def _noise(seq: int) -> list[dict]:
    """Template-preparation records (register, sync, session) that must never be used."""
    return [
        _rec(seq, "register", source="bogus", unit="bogus/unit"),
        _rec(seq + 1, "sync", source="bogus", unit="bogus/unit"),
        _rec(seq + 2, "session", source="bogus", unit="bogus/unit"),
    ]


def make_runs(root: Path, *, long_unit: str | None = None) -> Path:
    """Build the four run folders with fake records and return the runs root."""
    # W-H-03: no RefCov, one file write, no reads.
    w = root / W_FOLDER
    _lines(
        w / "W-H-03.jsonl",
        [
            {"type": "runStarted", "data": {}},
            _call("w1", "Write File", {"path": "D:\\agent\\refcov-trial\\runs\\W-H-03\\index.html", "text": "BODY-SHOULD-NOT-LEAK"}),
            _done("w1"),
            _message(),
            {"type": "runFinished", "data": {}},
        ],
    )
    _json(w / "W-H-03.status.json", {"model": "claude-haiku-5.5", "seconds": 39, "exit_code": 0, "timed_out": False, "prompt": "PROMPT-NOT-USED"})
    _write(w / "W-H-03" / "index.html", "<main><p>plain page</p></main>\n")

    # WB-H-03: RefCov on, three reads (one with a Chinese unit ID), one file write.
    wb = root / WB_FOLDER
    units = [("g-color", "Color"), ("g-color", "Contrast"), ("demo-plan", CHINESE_UNIT)]
    if long_unit is not None:
        units[0] = ("g-color", long_unit)
    calls: list[dict] = []
    for i, (source, unit) in enumerate(units):
        calls.append(_call(f"r{i}", "@refcov/read_unit", {"source": source, "unit": unit}))
        calls.append(_done(f"r{i}"))
    _lines(
        wb / "WB-H-03.jsonl",
        [
            {"type": "runStarted", "data": {}},
            *calls,
            _call("wb-w", "Write File", {"path": "D:\\agent\\refcov-trial\\runs\\WB-H-03\\index.html", "text": "BODY-SHOULD-NOT-LEAK"}),
            _done("wb-w"),
            _message(),
            {"type": "runFinished", "data": {}},
        ],
    )
    _json(wb / "WB-H-03.status.json", {"model": "claude-haiku-5.5", "seconds": 126, "exit_code": 0, "timed_out": False, "prompt": "PROMPT-NOT-USED"})
    _write(wb / "WB-H-03" / "index.html", WB_HTML)
    _lines(
        wb / "WB-H-03" / STATE_DIR / "log.jsonl",
        [*_noise(0), *[_read(i + 3, s, u) for i, (s, u) in enumerate(units)]],
    )

    # G-01: a direct file read, a blocked write, two reads, then the write.
    g = root / G_FOLDER
    _lines(
        g / "G-01.jsonl",
        [
            {"type": "runStarted", "data": {}},
            _call("g1", "Read File", {"path": "D:\\agent\\refcov-trial\\runs\\G-01\\README.md"}),
            _done("g1"),
            _call("g2", "Write File", {"path": "D:\\agent\\refcov-trial\\runs\\G-01\\answer.md", "text": "42"}),
            _done("g2", "failed"),
            _call("g3", "@refcov/read_unit", {"source": "nyc-bldg-dict", "unit": "Identification"}),
            _done("g3"),
            _call("g4", "@refcov/read_unit", {"source": "nyc-bldg-dict", "unit": "Attribute"}),
            _done("g4"),
            _call("g5", "Write File", {"path": "D:\\agent\\refcov-trial\\runs\\G-01\\answer.md", "text": "42"}),
            _done("g5"),
            _message(),
            {"type": "runFinished", "data": {}},
        ],
    )
    _json(g / "G-01.status.json", {"group": "G", "model": "claude-haiku-5.5", "kiro_cli": "kiro-cli 3.3.0", "seconds": 91, "exit_code": 0, "timed_out": False, "prompt": "PROMPT-NOT-USED"})
    _write(g / "G-01" / "answer.md", "SENTINEL-4242 answer text\n")
    _lines(
        g / "G-01" / STATE_DIR / "log.jsonl",
        [
            *_noise(0),
            _block(3, "answer.md", ["unit-missing-a", "unit-missing-b"]),
            _read(4, "nyc-bldg-dict", "Identification"),
            _read(5, "nyc-bldg-dict", "Attribute"),
        ],
    )

    # VB-01: no stream; the shot file and the batch file carry the data.
    v = root / V_FOLDER
    _json(v / "VB-01.pgrade.json", {"seconds": 301, "status_reconstructed": True, "kiro_cli_at_batch_start": "kiro-cli 3.1.0", "tool_calls": 73})
    _json(v / "VB-01.status.json", {"model": "claude-sonnet-5.5", "seconds": 300, "exit_code": 0, "timed_out": False})
    _write(v / "VB-01" / "reference.shots.md", SHOTS_TEXT)
    _lines(
        v / "VB-01" / STATE_DIR / "log.jsonl",
        [
            *_noise(0),
            _read(3, "shots", "shot-00-00-0"),
            _read(4, "shots", "shot-00-03-9"),
            _read(5, "shots", "shot-00-06-6"),
        ],
    )
    return root


def _convert(tmp_path: Path, root: Path, name: str = "out") -> Path:
    out = tmp_path / name
    convert_runs.convert(root, out)
    return out


def _load(out: Path, key: str) -> dict:
    return json.loads((out / f"{key}.json").read_text(encoding="utf-8"))


def _all_text(out: Path) -> str:
    return "".join((out / f"{key}.json").read_text(encoding="utf-8") for key in KEYS)


def _all_strings(value) -> list[str]:
    """Every string in a decoded JSON value, keys included."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        found = list(value.keys())
        for item in value.values():
            found += _all_strings(item)
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found += _all_strings(item)
        return found
    return []


def _decoded_strings(out: Path) -> list[str]:
    found: list[str] = []
    for key in KEYS:
        found += _all_strings(_load(out, key))
    return found


def _numeric_paths(value, path: tuple = ()) -> list[tuple]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [path]
    if isinstance(value, dict):
        found: list[tuple] = []
        for key, item in value.items():
            found += _numeric_paths(item, path + (key,))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found += _numeric_paths(item, path + ("*",))
        return found
    return []


def test_rerun_is_byte_identical(tmp_path):
    """性质（需求 8.5）：同样的运行记录，运行两次，四个 JSON 的字节相同。"""
    root = make_runs(tmp_path / "runs")
    first = _convert(tmp_path, root, "first")
    second = _convert(tmp_path, root, "second")
    assert sorted(p.name for p in first.iterdir()) == sorted(f"{k}.json" for k in KEYS)
    for key in KEYS:
        assert (first / f"{key}.json").read_bytes() == (second / f"{key}.json").read_bytes()


def test_w_h_03_has_one_tool_call_and_one_write(tmp_path):
    """性质（需求 2.3）：W-H-03 只有一次工具调用，事件只有写 index.html 和汇报；不装 RefCov，没有必看数。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs"))
    data = _load(out, "w-h-03")
    assert data["tool_calls"] == 1
    assert data["events"] == [
        {"kind": "write", "label": "write:index.html"},
        {"kind": "final", "label": "final-report"},
    ]
    assert "must_read" not in data
    assert data["blocks"] == 0
    assert data["kiro_cli"] == {"basis": "inferred", "value": "3.3.0"}
    assert data["seconds"] == 39
    assert data["model"] == "claude-haiku-5.5"
    assert data["date"] == "2026-11-15"
    assert data["needles"] == {"closedby": False, "commandfor": False, "overscroll": False, "user_invalid": False}


def test_wb_h_03_reads_match_the_records(tmp_path):
    """性质（设计第 3.3 节）：读单元事件按输出流排列，与读取记录个数和集合相同；中文单元 ID 原样保留。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs"))
    data = _load(out, "wb-h-03")
    assert [e["kind"] for e in data["events"]] == ["read", "read", "read", "write", "final"]
    assert data["events"][0] == {"kind": "read", "label": "unit-read", "unit": "g-color/Color"}
    assert {"kind": "read", "label": "unit-read", "unit": f"demo-plan/{CHINESE_UNIT}"} in data["events"]
    assert data["must_read"] == {"read": 3, "total": 3}
    assert data["tool_calls"] == 4
    assert data["blocks"] == 0
    assert data["needles"] == {"closedby": True, "commandfor": False, "overscroll": True, "user_invalid": True}


def test_g_01_is_blocked_before_the_reads(tmp_path):
    """性质（需求 4.1）：G-01 先拦后读；失败的写文件对应一条 block，之后是读取，最后写成；缺的单元只计数，不输出。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs"))
    data = _load(out, "g-01")
    assert [e["label"] for e in data["events"]] == [
        "file-read",
        "gate:required-units-unread",
        "unit-read",
        "unit-read",
        "write:answer.md",
        "final-report",
    ]
    assert data["blocks"] == 1
    assert data["must_read"] == {"read": 2, "total": 2}
    assert data["kiro_cli"] == {"basis": "record", "value": "3.3.0"}
    assert data["seconds"] == 91
    assert "unit-missing-a" not in _all_text(out)


def test_vb_01_shots_come_from_the_shot_file(tmp_path):
    """性质（需求 5.1–5.4）：VB-01 的镜头来自镜头清单，读过状态来自读取记录，用时取批次文件。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs"))
    data = _load(out, "vb-01")
    assert [s["id"] for s in data["shots"]] == ["shot-00-00-0", "shot-00-03-9", "shot-00-06-6"]
    assert all(s["read"] for s in data["shots"])
    assert data["shots"][1] == {"id": "shot-00-03-9", "start": 3.9, "end": 6.6, "read": True}
    assert data["seconds"] == 301
    assert data["seconds_reconstructed"] is True
    assert data["kiro_cli"] == {"basis": "record-batch-start", "value": "3.1.0"}
    assert data["tool_calls"] == 73
    assert data["model"] == "claude-sonnet-5.5"
    assert data["must_read"] == {"read": 3, "total": 3}
    assert "events" not in data


def test_event_vocabulary_is_fixed(tmp_path):
    """性质（需求 8.3）：事件的 kind 和 label 只能是设计第 3.3 节的固定组合。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs"))
    allowed = {
        ("tool", "tool-call"),
        ("tool", "file-read"),
        ("tool", "mcp-call"),
        ("read", "unit-read"),
        ("write", "write:index.html"),
        ("write", "write:answer.md"),
        ("write", "write:edit-plan.md"),
        ("blocked", "gate:required-units-unread"),
        ("final", "final-report"),
    }
    for key in ("w-h-03", "wb-h-03", "g-01"):
        for event in _load(out, key)["events"]:
            assert (event["kind"], event["label"]) in allowed


def test_read_mismatch_fails_and_writes_nothing(tmp_path):
    """性质（设计第 3.5 节第 1 条）：输出流的读单元与读取记录不一致时报错，且不写任何文件。"""
    root = make_runs(tmp_path / "runs")
    state = root / WB_FOLDER / "WB-H-03" / STATE_DIR / "log.jsonl"
    lines = state.read_text(encoding="utf-8").splitlines(keepends=True)
    state.write_text("".join(lines[:-1]), encoding="utf-8")  # drop the last read record
    out = tmp_path / "out"
    with pytest.raises(convert_runs.ConvertError):
        convert_runs.convert(root, out)
    assert not out.exists() or not any(out.iterdir())


def test_block_count_mismatch_fails(tmp_path):
    """性质（设计第 3.5 节第 1 条）：失败的写文件个数与 block 记录个数不同，报错。"""
    root = make_runs(tmp_path / "runs")
    state = root / G_FOLDER / "G-01" / STATE_DIR / "log.jsonl"
    kept = [line for line in state.read_text(encoding="utf-8").splitlines(keepends=True) if '"type": "block"' not in line]
    state.write_text("".join(kept), encoding="utf-8")
    with pytest.raises(convert_runs.ConvertError):
        convert_runs.convert(root, tmp_path / "out")


def test_answer_md_is_never_opened(tmp_path, monkeypatch):
    """性质（需求 8.6，设计第 3.5 节第 5 条）：转换脚本不打开 answer.md，哨兵数字不出现在输出里。"""
    root = make_runs(tmp_path / "runs")
    opened: list[str] = []
    real_open = io.open

    def spy(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    out = _convert(tmp_path, root)
    assert not [name for name in opened if name.endswith("answer.md")]
    assert "SENTINEL-4242" not in _all_text(out)


def test_only_read_and_block_records_are_used(tmp_path):
    """性质（需求 8.1）：只用 read 和 block 记录；register、sync、session 里的假单元不出现在输出里。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs"))
    assert "bogus" not in _all_text(out)


def test_no_local_paths_or_free_text_in_output(tmp_path):
    """性质（需求 8.2，8.6）：输出的字符串里没有本机路径，也没有模型写的文字。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs"))
    strings = _decoded_strings(out)
    for banned in (
        "D:",
        "\\",
        "/Users/",
        "/home/",
        "refcov-trial",
        "BODY-SHOULD-NOT-LEAK",
        "SECRET-REPORT-TEXT",
        "PROMPT-NOT-USED",
    ):
        assert not any(banned in text for text in strings), banned


def test_long_unit_ids_are_cut_to_80_characters(tmp_path):
    """性质（设计第 3.4 节）：超长单元 ID 截断到 80 个字符，并以省略号结尾，前缀保留。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs", long_unit="x" * 100))
    unit = _load(out, "wb-h-03")["events"][0]["unit"]
    assert len(unit) == 80
    assert unit.endswith("\u2026")
    assert unit.startswith("g-color/")


@given(st.text(max_size=300))
def test_truncation_keeps_at_most_80_characters(text):
    """性质（设计第 3.4 节，属性测试）：任意字符串截短后最多 80 个字符；超出时以省略号结尾，并保留原来的前缀。"""
    cut = convert_runs._truncate(text)
    assert len(cut) <= 80
    if len(text) <= 80:
        assert cut == text
    else:
        assert len(cut) == 80
        assert cut.endswith("\u2026")
        assert text.startswith(cut[:-1])


def test_output_is_ascii_and_keeps_chinese_unit_ids(tmp_path):
    """性质（设计第 3.2 节，Windows 编码）：输出文件是纯 ASCII；解码后中文单元 ID 不变。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs"))
    for key in KEYS:
        raw = (out / f"{key}.json").read_bytes()
        assert all(byte < 128 for byte in raw), key
    units = [e.get("unit") for e in _load(out, "wb-h-03")["events"] if e["kind"] == "read"]
    assert f"demo-plan/{CHINESE_UNIT}" in units


def test_numbers_stay_within_the_allowed_fields(tmp_path):
    """性质（设计第 3.5 节第 5 条）：输出的数值字段只有允许的几个。"""
    out = _convert(tmp_path, make_runs(tmp_path / "runs"))
    for key in KEYS:
        for path in _numeric_paths(_load(out, key)):
            assert path in ALLOWED_NUMBERS, path


def test_main_writes_four_files_on_success(tmp_path, monkeypatch):
    """性质（设计第 3.6 节）：命令行在输入齐全时写出四个 JSON 文件并返回 0。"""
    root = make_runs(tmp_path / "runs")
    monkeypatch.setattr(convert_runs, "OUT_DIR", tmp_path / "out")
    assert convert_runs.main(["--runs", str(root)]) == 0
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(f"{k}.json" for k in KEYS)


def test_main_returns_2_and_names_the_run_when_an_input_is_missing(tmp_path, monkeypatch, capsys):
    """性质（设计第 3.5 节）：某个输入缺失时命令行返回 2，错误信息指出是哪次运行，不写任何文件。"""
    root = make_runs(tmp_path / "runs")
    (root / G_FOLDER / "G-01.jsonl").unlink()
    monkeypatch.setattr(convert_runs, "OUT_DIR", tmp_path / "out")
    assert convert_runs.main(["--runs", str(root)]) == 2
    assert "G-01" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
