"""Tests that the numbers on the demo page match the trial documents and the replay data.

Each expected value names the document and section it comes from. The trial documents are in
the repository's docs folder. The replay data is in site/data, written by site/convert_runs.py
from the four recorded runs.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = SITE / "data"
HTML = (SITE / "index.html").read_text(encoding="utf-8")
LEDGER = ROOT / "docs" / "施工账.md"
FIELDS = ROOT / "apps" / "layer-coverage" / "bayside.fields.md"

MANIFEST_PREFIX = "f-apps-layer-coverage-bayside-fields-md-631ad0/"
DICTIONARY_PREFIX = "nyc-bldg-dict/"
CJK = re.compile(r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]")

# Front-end trial, section 5 (first task, claude-haiku-5.5, 4 runs per group), and front-end
# extension trial, section 2 (four tasks, 3 runs per group). Columns: runs that opened a
# registered guide without RefCov; practices used without RefCov; runs that read every
# required unit with RefCov (with the unit count); practices used with RefCov.
EXPECTED_TASKS = {
    "Account settings page (first trial)": ("0 of 4", "0 / 16", "4 of 4 (82 units)", "14 / 16"),
    "FAQ accordion": ("0 of 3", "0 / 9", "3 of 3 (117 units)", "7 / 9"),
    "Dropdown menu": ("0 of 3", "0 / 15", "3 of 3 (92 units)", "5 / 15"),
    "Dark-mode switch": ("2 of 3", "7 / 9", "3 of 3 (101 units)", "7 / 9"),
    "Long article page": ("1 of 3", "2 / 9", "3 of 3 (54 units)", "6 / 9"),
}

# Front-end extension trial, section 7, and the story document, section 2: totals over 16 runs.
EXPECTED_TOTALS = ("3 of 16 runs", "9 / 58", "16 of 16 runs", "39 / 58")


def _section(section_id: str) -> str:
    start = HTML.index(f'<section id="{section_id}"')
    end = HTML.find("<section id=", start + 1)
    return HTML[start:] if end == -1 else HTML[start:end]


class _Tables(HTMLParser):
    """Collects the rows of every table, keyed by the table's class attribute."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: dict[str, list[list[str]]] = {}
        self._open: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            key = dict(attrs).get("class", "")
            self._open.append(key)
            self.tables.setdefault(key, [])
        elif tag == "tr" and self._open:
            self._row = []
            self.tables[self._open[-1]].append(self._row)
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr":
            self._row = None
        elif tag == "table" and self._open:
            self._open.pop()

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _table_rows(prefix: str) -> list[list[str]]:
    parser = _Tables()
    parser.feed(HTML)
    matches = [rows for key, rows in parser.tables.items() if key.split()[0] == prefix]
    assert len(matches) == 1, prefix
    return matches[0]


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _lead(text: str) -> int:
    match = re.match(r"\s*(\d+)", text)
    assert match, text
    return int(match.group(1))


def test_hero_shows_3_then_16_lit_cells_and_the_13_of_16_sentence():
    """性质（需求 1.2）：第 0 段两排各 16 格，不装时亮 3 格，装上后亮 16 格，并有"13 of 16"的文字。"""
    section = _section("s0")
    grids = re.findall(r'<ol class="cells" aria-label="([^"]+)">(.*?)</ol>', section, re.S)
    assert [label for label, _ in grids] == ["Without RefCov: 16 runs", "With RefCov: 16 runs"]
    counts = [(body.count('class="cell on"'), body.count('class="cell off"')) for _, body in grids]
    assert counts == [(3, 13), (16, 0)]
    assert "13 of 16 runs" in section
    assert "all 16 runs" in section.lower()


def test_five_task_rows_and_totals_match_the_trial_results():
    """性质（需求 3.1、3.3）：五行的数字与前端指南试验第 5 节、前端扩展试验第 2 节一致；合计行与前端扩展试验第 7 节、故事构思第 2 节一致。"""
    rows = _table_rows("tasks")
    body = [row for row in rows if row and row[0] in EXPECTED_TASKS]
    assert [row[0] for row in body] == list(EXPECTED_TASKS)
    for row in body:
        assert tuple(row[1:5]) == EXPECTED_TASKS[row[0]], row[0]
    totals = [row for row in rows if row and row[0] == "All five tasks"]
    assert len(totals) == 1
    assert tuple(totals[0][1:5]) == EXPECTED_TOTALS


def test_needles_table_matches_the_replay_records():
    """性质（需求 2.4）：四种写法的用上情况与两份回放记录里的 needles 一致（W-H-03 为 0/4，WB-H-03 为 3/4，没有 commandfor）。"""
    rows = [row for row in _table_rows("needles") if row and row[0] != "Practice"]
    without = _load("w-h-03.json")["needles"]
    with_refcov = _load("wb-h-03.json")["needles"]
    keys = {
        "closedby": "closedby",
        "commandfor": "commandfor",
        ":user-invalid": "user_invalid",
        "overscroll-behavior": "overscroll",
    }
    assert len(rows) == len(keys)
    for row in rows:
        key = next(value for label, value in keys.items() if row[0].startswith(label))
        assert row[1] == ("used" if without[key] else "not used"), row[0]
        assert row[2] == ("used" if with_refcov[key] else "not used"), row[0]


def _ledger_file_rows() -> list[list[str]]:
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.startswith("| 20"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            assert len(cells) == 10, line[:60]
            rows.append(cells)
    return rows


def test_ledger_rows_match_the_ledger_file_in_order():
    """性质（需求 6.1）：施工账每行的日期、模型、额度、测试数、读单元数、被拦次数与 docs/施工账.md 一致，行数和顺序也一致。"""
    file_rows = _ledger_file_rows()
    page_rows = [row for row in _table_rows("ledger") if row and re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[0])]
    assert file_rows
    assert len(page_rows) == len(file_rows)
    for page, source in zip(page_rows, file_rows):
        date, model, credits, tests, units, blocks = (source[i] for i in (0, 2, 3, 4, 5, 6))
        assert page[0] == date
        assert page[2] == model
        assert page[3] == ("unknown" if credits == "未知" else credits), date
        full = re.search(r"全量 (\d+)", tests)
        assert full, date
        assert re.search(rf"full suite {full.group(1)} passed", page[4]), date
        if "无目标测试" in tests:
            assert page[4].startswith("no targeted tests"), date
        elif "目标" in tests:
            assert "targeted" in page[4], date
        else:
            assert "targeted" not in page[4], date
        assert _lead(page[5]) == _lead(units), date
        assert _lead(page[6]) == _lead(blocks), date


def test_run_facts_match_the_status_files_and_records():
    """性质（需求 2.2、4.2、5.2）：四次运行的总秒数、版本、模型、日期、读单元数和拦截数与状态文件及读取记录一致。"""
    w, wb, g, vb = (_load(name) for name in ("w-h-03.json", "wb-h-03.json", "g-01.json", "vb-01.json"))
    assert (w["seconds"], w["tool_calls"], w["model"], w["date"]) == (39, 1, "claude-haiku-5.5", "2026-11-15")
    assert w["kiro_cli"] == {"basis": "inferred", "value": "3.3.0"}
    assert (wb["seconds"], wb["must_read"], wb["blocks"]) == (126, {"read": 82, "total": 82}, 0)
    assert wb["kiro_cli"] == {"basis": "inferred", "value": "3.3.0"}
    assert (g["seconds"], g["must_read"], g["blocks"]) == (91, {"read": 24, "total": 24}, 1)
    assert g["kiro_cli"] == {"basis": "record", "value": "3.3.0"}
    assert (vb["seconds"], vb["seconds_reconstructed"], vb["must_read"]) == (301, True, {"read": 46, "total": 46})
    assert vb["model"] == "claude-sonnet-5.5"
    assert vb["kiro_cli"] == {"basis": "record-batch-start", "value": "3.1.0"}


def test_replay_event_order_matches_the_records():
    """性质（需求 2.3、4.1）：WB-H-03 读 82 次；G-01 先被拦、再读 24 次，最后写 answer.md。"""
    wb_kinds = [event["kind"] for event in _load("wb-h-03.json")["events"]]
    assert wb_kinds.count("read") == 82
    g_events = _load("g-01.json")["events"]
    g_kinds = [event["kind"] for event in g_events]
    assert g_kinds.count("read") == 24
    assert g_kinds.count("blocked") == 1
    assert g_kinds.index("blocked") < g_kinds.index("read")
    assert g_events[-2]["label"] == "write:answer.md"


def test_shot_strip_is_contiguous_and_fully_read():
    """性质（需求 5.1、5.4）：46 个镜头首尾相接，从 0 秒开始，全部标为读过。"""
    shots = _load("vb-01.json")["shots"]
    assert len(shots) == 46
    assert shots[0]["start"] == 0.0
    for previous, current in zip(shots, shots[1:]):
        assert previous["end"] == current["start"]
    assert all(shot["read"] for shot in shots)


def test_gis_field_units_are_the_manifest_and_dictionary_units():
    """性质（需求 5.1）：字段表的 17 个清单单元与 bayside.fields.md 的字段标题一致，另有 7 个字典单元，共 24 格。"""
    units = [event["unit"] for event in _load("g-01.json")["events"] if event["kind"] == "read"]
    manifest = sorted(unit[len(MANIFEST_PREFIX):] for unit in units if unit.startswith(MANIFEST_PREFIX))
    dictionary = [unit for unit in units if unit.startswith(DICTIONARY_PREFIX)]
    headings = sorted(re.findall(r"^## (\S+)$", FIELDS.read_text(encoding="utf-8"), re.M))
    assert len(headings) == 17
    assert manifest == headings
    assert len(dictionary) == 7
    assert len(units) == 24


def test_replay_data_has_no_chinese_text_and_no_local_paths():
    """性质（需求 8.2、9.1、12.3）：site/data 下的 JSON 没有中文字符，也没有本机路径。"""
    for path in sorted(DATA.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        assert not CJK.search(text), path.name
        assert not re.search(r"[A-Za-z]:[\\/]", text), path.name
        assert "/Users/" not in text and "/home/" not in text, path.name


def test_replay_data_has_no_markdown_bold_markers():
    """性质（设计第 3.2 节，显示名）：JSON 里的显示名没有 Markdown 粗体标记 **。"""
    for path in sorted(DATA.glob("*.json")):
        assert "**" not in path.read_text(encoding="utf-8"), path.name


def test_practice_denominators_match_each_task_and_its_run_count():
    """性质（需求 3.1）：第 2 段每行的分母等于"写法个数 × 每组次数"；写法个数与第 2 段说明一致（第一轮 4 个写法、4 次；其余 4 个任务 3 次）。"""
    rows = _table_rows("tasks")
    practices = {
        "Account settings page (first trial)": (4, 4),
        "FAQ accordion": (3, 3),
        "Dropdown menu": (5, 3),
        "Dark-mode switch": (3, 3),
        "Long article page": (3, 3),
    }
    body = {row[0]: row for row in rows if row and row[0] in practices}
    assert set(body) == set(practices)
    for task, (count, runs) in practices.items():
        assert int(body[task][2].split("/")[1]) == count * runs, task
        assert int(body[task][4].split("/")[1]) == count * runs, task
    assert (
        "four for the first task, three for the FAQ accordion, five for the dropdown menu, "
        "and three each for the dark-mode switch and the long article page"
    ) in _section("s2")


def test_ledger_summary_sentence_matches_the_ledger_file():
    """性质（需求 6.1，用户要求）：第 5 段的一句摘要与施工账一致：件数、模型，以及全量测试从第一行到最后一行的通过数。"""
    file_rows = _ledger_file_rows()
    section = _section("s5")
    assert f"{len(file_rows)} pieces of work, all with claude-haiku-5.5." in section
    assert all(row[2] == "claude-haiku-5.5" for row in file_rows)
    first = re.search(r"全量 (\d+)", file_rows[0][4]).group(1)
    last = re.search(r"全量 (\d+)", file_rows[-1][4]).group(1)
    assert f"from {first} passing to {last}." in section
