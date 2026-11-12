"""解析需求文档和 tasks.md 里的出处（需求 6.1–6.4、9.6；设计 4 第 6、7 条，设计 7 第 6 条）。只用标准库。

只做解析和列举：幻影需求、无效引用、未转换的文字出处、被引用的单元，以及一个任务要读的单元。
是否达标（必看集合、严格/轻量模式）在 `coverage.py`（任务 11），这里不判断。

写法见引导文档里的出处约定：
- 一条需求 = 从 `### 需求 N：`（或 `### Requirement N:`，冒号全角半角都认）到下一个 `### ` 或文件结尾。
- 引用 `[ref:<参考源ID>/<单元ID>]`，正则照抄约定，不另改。
- 块里有一个有效引用就不是幻影需求；没有有效引用、但出处行去掉引用后还剩文字的，算"未转换"，
  不算幻影需求。只看行首是 `出处`、`Source`、`Sources` 加冒号的行。

已知局限：代码块里的引用照样算；代码块里的 `### ` 行也会切块。
"""

import re
from dataclasses import dataclass, field

REF = re.compile(r"\[ref:([a-z0-9-]+)/([^\]\s]+)\]")
# 中文 `### 需求 N：` 和英文 `### Requirement N:` 都认；英文词不分大小写，冒号全角半角都认（外部审阅 2026-11-12）
_REQ_HEADING = re.compile(r"^### (?:需求|(?i:requirement)) (\d+)\s*[:：](.*)$")
# 出处行：行首是 `出处`、`Source` 或 `Sources`（英文不分大小写），接全角或半角冒号
_SOURCE_LINE = re.compile(r"^(?:出处|(?i:sources?))\s*[:：]")
_PUNCT = " \t；;，,。.、"  # 出处行去掉引用后，只剩这些字符就算没有文字出处
# 只用来判断"还剩没剩文字"：写错的引用（例如参考源 ID 大写）也去掉，不当成文字出处。提取引用仍只用 REF。
_REF_LIKE = re.compile(r"\[ref:[^\]]*\]")

_TASK = re.compile(r"^- \[[ ~x]\]\*?\s+(.*?)\s*$")
_MARK = re.compile(r"^- \[[ ~x]\]")
_NUMBER = re.compile(r"^\d+(?:\.\d+)*\.\s*")
_REQ_LIST = re.compile(r"_(?:需求|(?i:requirements?))\s*[:：]([^_]*)_")  # `_需求：1.1_`、`_Requirements: 1.1, 2.3_`
_REQ_NO = re.compile(r"\d+(?:\.\d+)?")

Ref = tuple[str, str]


def _lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _refs(text: str) -> list[Ref]:
    return [(m.group(1), m.group(2)) for m in REF.finditer(text)]


def _unique(items):
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def ref_str(ref: Ref) -> str:
    return f"{ref[0]}/{ref[1]}"


# ---- 需求文档 ----

@dataclass
class Requirement:
    number: str
    title: str
    refs: list[Ref] = field(default_factory=list)  # 块里全部引用，按出现顺序，含无效的
    source_text: bool = False  # `出处：` 行去掉引用后还剩文字


@dataclass
class SpecCheck:
    requirements: list[Requirement]
    phantom: list[str]  # 需求编号
    invalid: list[tuple[str, str]]  # (需求编号, "参考源/单元")
    unconverted: list[str]  # 需求编号
    cited: list[str]  # 有效引用指向的 "参考源/单元"，按第一次出现排序，不重复


def parse_requirements(text: str) -> list[Requirement]:
    """按 `### 需求 N：` 切块。第一条需求之前的内容、别的 `### ` 小节不属于任何需求。"""
    reqs, cur = [], None
    for line in _lines(text):
        m = _REQ_HEADING.match(line)
        if m:
            cur = Requirement(m.group(1), m.group(2).strip())
            reqs.append(cur)
            continue
        if line.startswith("### "):
            cur = None
            continue
        if cur is None:
            continue
        cur.refs.extend(_refs(line))
        stripped = line.strip()
        label = _SOURCE_LINE.match(stripped)
        if label:
            rest = _REF_LIKE.sub("", stripped[label.end():]).strip(_PUNCT)
            if rest:
                cur.source_text = True
    return reqs


def check_requirements(text: str, known: set[Ref]) -> SpecCheck:
    """列出幻影需求、无效引用、未转换、被引用的单元。`known` 是已登记的 (参考源, 单元) 集合。"""
    reqs = parse_requirements(text)
    phantom, invalid, unconverted, cited = [], [], [], []
    for r in reqs:
        valid = [x for x in r.refs if x in known]
        invalid.extend((r.number, ref_str(x)) for x in r.refs if x not in known)
        cited.extend(ref_str(x) for x in valid)
        if not valid:
            (unconverted if r.source_text else phantom).append(r.number)
    return SpecCheck(reqs, phantom, invalid, unconverted, _unique(cited))


def known_units(manifest: dict) -> set[Ref]:
    """清单里已登记的 (参考源, 单元) 集合。"""
    return {(s["id"], u["id"]) for s in manifest.get("sources", []) for u in s.get("units", [])}


# ---- tasks.md ----

@dataclass
class Task:
    title: str  # 去掉状态标记、* 和首尾空白后的任务行
    short_title: str  # 再去掉开头的编号
    refs: list[Ref] = field(default_factory=list)  # 任务行和子项里的引用
    requirements: list[str] = field(default_factory=list)  # `_需求：…_` 里的需求编号（取整数部分，不重复）


def _short(title: str) -> str:
    return _NUMBER.sub("", title, count=1).strip()


def parse_tasks(text: str) -> list[Task]:
    """任务行是 `- [ ]`、`- [~]`、`- [x]`（可带 `*`）开头的行；子项是它后面缩进的行和空行，
    到下一个任务行或不缩进的行为止。"""
    tasks, cur, reqs = [], None, []
    for line in _lines(text):
        m = _TASK.match(line)
        if m:
            title = m.group(1)
            cur = Task(title, _short(title), _refs(title))
            reqs = []
            tasks.append(cur)
            continue
        if cur is None:
            continue
        if line and not line[0].isspace():
            cur = None
            continue
        cur.refs.extend(_refs(line))
        for lst in _REQ_LIST.findall(line):
            reqs.extend(n.split(".")[0] for n in _REQ_NO.findall(lst))
        cur.requirements = _unique(reqs)
    return tasks


def _normalize(name: str) -> str:
    s = _MARK.sub("", name.strip(), count=1).strip()
    return s[1:].strip() if s.startswith("*") else s


def find_task(tasks: list[Task], name: str) -> Task | None:
    """按任务名找任务：忽略状态标记、* 和首尾空白；和完整标题或去掉编号的标题相同就算找到。"""
    key = _normalize(name)
    if not key:
        return None
    for t in tasks:
        if key in (t.title, t.short_title):
            return t
    return None


def task_refs(task: Task, requirements: list[Requirement]) -> tuple[list[Ref], list[str]]:
    """任务要读的单元（任务自己的引用 + 所列需求块里的全部引用，不重复），以及需求文档里找不到的需求编号。"""
    by_no = {r.number: r for r in requirements}
    refs, unknown = list(task.refs), []
    for n in task.requirements:
        if n in by_no:
            refs.extend(by_no[n].refs)
        else:
            unknown.append(n)
    return _unique(refs), unknown
