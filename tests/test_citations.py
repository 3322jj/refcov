"""任务 10：解析需求文档和 tasks.md（需求 6.1–6.4、9.6；设计 4 第 6、7 条，设计 7 第 6 条）。

样例是 tests/data/ 下两份固定文件，不用 requirements.md（任务 11 最后一步会改它）。
预期条数直接写在测试里，样例改了要同步改这里。
"""

import json
import shutil
from pathlib import Path

import pytest

from refcov import citations, cli

DATA = Path(__file__).parent / "data"
REQ_TEXT = (DATA / "sample-requirements.md").read_text(encoding="utf-8")
TASKS_TEXT = (DATA / "sample-tasks.md").read_text(encoding="utf-8")

# 测试里当作"已登记"的单元。demo/简介里的引用 也登记了：它出现在第一条需求之前，不应算被引用。
KNOWN = {
    ("demo", "Hooks"),
    ("demo", "退出码@2"),
    ("demo", "简介里的引用"),
    ("rules", "15.-Entrant’s-Personal-Information"),
    ("rules", "6.-Judges-&-Criteria@2"),
    ("dec-a", "分析-#4-附：默认豁免"),
}


@pytest.fixture(scope="module")
def result():
    return citations.check_requirements(REQ_TEXT, KNOWN)


def test_ref_pattern_is_citation_md_verbatim():
    """引用正则和 .kiro/steering/citation.md 里写的完全一致，不另改。"""
    assert citations.REF.pattern == r"\[ref:([a-z0-9-]+)/([^\]\s]+)\]"


def test_blocks_split_on_requirement_headings():
    """按 `### 需求 N：` 切块：12 条；`#### 验收标准` 不切；`### 其他说明` 结束上一块；简介不属于任何需求。"""
    reqs = citations.parse_requirements(REQ_TEXT)
    assert [r.number for r in reqs] == [str(n) for n in range(1, 13)]
    assert reqs[0].title == "出处行里一个有效引用"
    by_no = {r.number: r for r in reqs}
    assert by_no["10"].refs == []  # 大写参考源 ID 匹配不上；"其他说明"块里的引用不归需求 10
    assert all(("demo", "简介里的引用") not in r.refs for r in reqs)


def test_phantom_requirements(result):
    """幻影需求：块里没有有效引用，出处行也没有文字出处（需求 6.2；设计 4 第 7 条）。"""
    assert result.phantom == ["3", "4", "5", "9", "10", "12"]


def test_inline_reference_counts(result):
    """只在验收标准末尾写了行内引用、没有出处行，不算幻影需求（出处标到需求级）。"""
    assert "2" not in result.phantom and "2" not in result.unconverted


def test_invalid_refs(result):
    """无效引用：参考源或单元不存在；手打直引号对不上弯引号（需求 6.4）。"""
    assert result.invalid == [
        ("4", "demo/没有这个单元"),
        ("5", "nosuch/Hooks"),
        ("6", "demo/exit"),
        ("9", "rules/15.-Entrant's-Personal-Information"),
        ("11", "demo/exit"),
    ]


def test_valid_plus_invalid_is_not_phantom(result):
    """一个有效、一个无效：列出无效引用，不算幻影需求。"""
    assert "6" not in result.phantom


def test_unconverted(result):
    """未转换：没有有效引用，`出处：` 行去掉引用后还剩文字；只看出处行，行内别处的"出处："不算（需求 6.6）。"""
    assert result.unconverted == ["7", "11"]
    assert "12" in result.phantom


def test_cited_units_with_special_characters(result):
    """被引用的单元：只算有效引用，按第一次出现排序；弯引号、&、#、@、紧挨着的引用、后跟中文句号都能认。"""
    assert result.cited == [
        "demo/Hooks",
        "demo/退出码@2",
        "rules/15.-Entrant’s-Personal-Information",
        "rules/6.-Judges-&-Criteria@2",
        "dec-a/分析-#4-附：默认豁免",
    ]


def test_crlf_gives_same_result():
    """CRLF 换行（Windows 检出）和 LF 结果一样。"""
    crlf = REQ_TEXT.replace("\r\n", "\n").replace("\n", "\r\n")
    assert citations.check_requirements(crlf, KNOWN) == citations.check_requirements(REQ_TEXT, KNOWN)


def test_known_units_from_manifest():
    """从清单取出已登记的 (参考源, 单元) 集合。"""
    manifest = {"version": 1, "sources": [
        {"id": "demo", "units": [{"id": "Hooks"}, {"id": "退出码@2"}]},
        {"id": "rules", "units": [{"id": "8.-Prizes"}]},
    ]}
    assert citations.known_units(manifest) == {("demo", "Hooks"), ("demo", "退出码@2"), ("rules", "8.-Prizes")}


# ---- tasks.md ----

@pytest.fixture(scope="module")
def tasks():
    return citations.parse_tasks(TASKS_TEXT)


def test_parse_tasks(tasks):
    """任务行去掉状态标记（[ ]、[~]、[x]）和 *，子项是后面缩进的行，到下一个任务或不缩进的行为止。"""
    assert [t.title for t in tasks] == [
        "1. 普通任务",
        "2. 进行中的任务 [ref:demo/退出码@2]",
        "3. 已完成的任务",
        "18. 可选任务",
    ]
    assert [t.short_title for t in tasks] == [
        "普通任务", "进行中的任务 [ref:demo/退出码@2]", "已完成的任务", "可选任务"]
    assert tasks[0].refs == [("demo", "Hooks")] and tasks[0].requirements == ["6"]
    assert tasks[1].refs == [("demo", "退出码@2")] and tasks[1].requirements == ["1", "99"]
    assert tasks[2].refs == [] and tasks[2].requirements == []
    assert tasks[3].refs == [("rules", "6.-Judges-&-Criteria@2")] and tasks[3].requirements == ["8"]
    assert all(("demo", "不算") not in t.refs for t in tasks)


@pytest.mark.parametrize("name, title", [
    ("1. 普通任务", "1. 普通任务"),
    ("普通任务", "1. 普通任务"),
    ("  18. 可选任务  ", "18. 可选任务"),
    ("- [ ]* 18. 可选任务", "18. 可选任务"),
    ("可选任务", "18. 可选任务"),
    ("- [x] 3. 已完成的任务", "3. 已完成的任务"),
    ("2. 进行中的任务 [ref:demo/退出码@2]", "2. 进行中的任务 [ref:demo/退出码@2]"),
])
def test_find_task(tasks, name, title):
    """找任务：忽略状态标记和首尾空白，也比较去掉编号后的标题（需求 9.6；设计 7 第 6 条）。"""
    found = citations.find_task(tasks, name)
    assert found is not None and found.title == title


@pytest.mark.parametrize("name", ["不存在的任务", "5. 普通任务", ""])
def test_find_task_not_found(tasks, name):
    """找不到时返回 None；编号不同不算同一个任务。"""
    assert citations.find_task(tasks, name) is None


def test_task_refs_include_requirement_blocks(tasks):
    """任务要读的单元 = 任务行和子项里的引用 + `_需求：…_` 指向的需求块里的全部引用；6.1、6.5 合并成需求 6。"""
    reqs = citations.parse_requirements(REQ_TEXT)
    refs, unknown = citations.task_refs(tasks[0], reqs)
    assert refs == [("demo", "Hooks"), ("demo", "exit")] and unknown == []
    refs, unknown = citations.task_refs(tasks[1], reqs)
    assert refs == [("demo", "退出码@2"), ("demo", "Hooks")] and unknown == ["99"]
    refs, unknown = citations.task_refs(tasks[3], reqs)
    assert refs == [
        ("rules", "6.-Judges-&-Criteria@2"),
        ("rules", "15.-Entrant’s-Personal-Information"),
        ("dec-a", "分析-#4-附：默认豁免"),
    ] and unknown == []


# ---- 命令行 refcov check-spec ----

@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".refcov").mkdir()
    manifest = {"version": 1, "sources": [
        {"id": src, "units": [{"id": u} for s, u in sorted(KNOWN) if s == src]}
        for src in sorted({s for s, _ in KNOWN})
    ]}
    (tmp_path / ".refcov" / "sources.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "docs").mkdir()
    shutil.copy(DATA / "sample-requirements.md", tmp_path / "docs" / "req.md")
    return tmp_path


def snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_cli_check_spec(repo, monkeypatch, capsys):
    """`refcov check-spec`：列出幻影需求、无效引用、未转换、被引用的单元；只读，不写任何文件。"""
    monkeypatch.chdir(repo)
    before = snapshot(repo)
    assert cli.main(["check-spec", "docs/req.md"]) == 0
    out = capsys.readouterr().out
    assert "12 条需求" in out
    assert "幻影需求 6 条：3、4、5、9、10、12" in out
    assert "无效引用 5 条" in out and "需求 9：rules/15.-Entrant's-Personal-Information" in out
    assert "未转换 2 条：7、11" in out
    assert "被引用的单元 5 个" in out and "rules/6.-Judges-&-Criteria@2" in out
    assert snapshot(repo) == before


def test_cli_check_spec_missing_file(repo, monkeypatch, capsys):
    """文件不存在：退出码 1，原因写 stderr。"""
    monkeypatch.chdir(repo)
    assert cli.main(["check-spec", "docs/nope.md"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "检查失败" in captured.err


def test_cli_check_spec_needs_repo_root(repo, monkeypatch, capsys):
    """在子目录里跑：报"请在仓库根目录运行 refcov"，退出码 1。"""
    monkeypatch.chdir(repo / "docs")
    assert cli.main(["check-spec", "req.md"]) == 1
    assert "请在仓库根目录运行 refcov" in capsys.readouterr().err


# ---- 英文写法（外部审阅 2026-11-12：英文需求文档解析出 0 条）----

EN_TEXT = (DATA / "sample-requirements-en.md").read_text(encoding="utf-8")
EN_TASKS = (DATA / "sample-tasks-en.md").read_text(encoding="utf-8")


def test_english_headings_split():
    """`### Requirement N:` 也切块：英文词不分大小写，冒号全角半角都认，冒号前可有空格；
    `### 需求 N:`（半角冒号）也认；`####` 不切；没有编号的 `### Requirements` 结束上一块。"""
    reqs = citations.parse_requirements(EN_TEXT)
    assert [r.number for r in reqs] == ["1", "2", "3", "4", "5", "6", "8"]
    assert reqs[0].title == "Valid reference on the source line"
    assert {r.number: r for r in reqs}["8"].refs == [("demo", "nope")]  # "### Requirements" 里的引用不归需求 6


def test_english_source_lines():
    """出处行认 `出处`、`Source`、`Sources`，不分大小写，冒号全角半角都认；只看行首。"""
    res = citations.check_requirements(EN_TEXT, KNOWN)
    assert res.phantom == ["2", "6", "8"]
    assert res.unconverted == ["4", "5"]
    assert res.invalid == [("8", "demo/nope")]
    assert res.cited == ["demo/Hooks", "demo/退出码@2"]


def test_english_task_requirement_lists():
    """tasks.md 里 `_Requirements: 1.1, 3.2_`、`_Requirement：4_` 和 `_需求：5.1_` 都认，取整数部分。"""
    tasks = citations.parse_tasks(EN_TASKS)
    assert [t.short_title for t in tasks] == ["Set up the project", "Second task"]
    assert tasks[0].requirements == ["1", "3"] and tasks[0].refs == [("demo", "Hooks")]
    assert tasks[1].requirements == ["4", "5"]
