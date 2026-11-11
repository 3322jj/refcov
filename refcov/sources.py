"""适配器接口和单元 ID 规则（需求 2、3.5，设计 4 第 1–3、8 条）。

只用标准库。核心层不 import 任何具体适配器（需求 2.6）。登记参考源（抓取、缓存、
写清单）是任务 4 的事，不在这里。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable, Protocol, Sequence

LIMIT = 4000  # 单元正文上限，按换行统一后的 len 算（设计 4 第 3 条）
EMPTY_ID = "section"

_ID_JUNK = re.compile(r"[\s\[\]@]+")  # 空白、方括号、@ 换成一个 -（设计 4 第 1 条）
_ID_BAD = re.compile(r"[\s\[\]]")  # 任何单元 ID 都不许含的字符（需求 2.5）
_BLANK = re.compile(r"^[ \t]*\n", re.M)  # 空行：只含空格、制表符的行，连同它的换行


@dataclass(frozen=True)
class KindDecl:
    """单元类型的声明（需求 2.2）：严格模式下是否默认必看，是否关键类型（轻量模式必看）。"""

    strict: bool
    key: bool = False


@dataclass(frozen=True)
class Image:
    """`read` 返回里的图片（需求 2.1，例如视频关键帧）。"""

    data: bytes
    mime: str


@dataclass(frozen=True)
class Unit:
    """一个单元。`text` 是正文（不含标题行），换行已统一为 `\\n`。"""

    id: str
    title: str
    kind: str
    text: str
    sha256: str = field(init=False)
    chars: int = field(init=False)

    def __post_init__(self):
        validate_unit_id(self.id)
        object.__setattr__(self, "sha256", hashlib.sha256(self.text.encode("utf-8")).hexdigest())
        object.__setattr__(self, "chars", len(self.text))

    def manifest_entry(self) -> dict:
        """写进清单 `units` 的一项（设计 3.1）。"""
        return {"id": self.id, "title": self.title, "kind": self.kind,
                "sha256": self.sha256, "chars": self.chars}


class Adapter(Protocol):
    """适配器接口：三个函数（需求 2.1）加两项声明。

    - `name`：适配器名，写进清单的 `adapter`。
    - `kinds`：单元类型 → `KindDecl`（需求 2.2）。
    - `split(data, name)`：把参考源原文拆成单元。`name` 是文件名（不带扩展名），
      没有标题的部分用它当标题。
    - `read(data, name, unit_id)`：读一个单元，返回文字和图片的列表。
    - `facts(data, name, unit_id)`：这个单元可核对的事实。
    单元不存在时 `read` 和 `facts` 抛 `KeyError`。
    """

    name: str
    kinds: dict[str, KindDecl]

    def split(self, data: bytes, name: str) -> list[Unit]: ...

    def read(self, data: bytes, name: str, unit_id: str) -> list[str | Image]: ...

    def facts(self, data: bytes, name: str, unit_id: str) -> dict: ...


def check_declarations(kinds: dict[str, KindDecl]) -> None:
    """需求 2.4：关键类型一定也是严格模式必看的类型。不满足时抛 ValueError。"""
    bad = sorted(k for k, d in kinds.items() if d.key and not d.strict)
    if bad:
        raise ValueError(f"关键类型必须也是严格必看的类型：{', '.join(bad)}")


def normalize_newlines(text: str) -> str:
    """`\\r\\n` 和单独的 `\\r` 都换成 `\\n`。拆分、算长度、算校验值都在这之后（设计 4 第 8 条）。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def validate_unit_id(unit_id: str) -> None:
    """单元 ID 不能为空，不能含空白和方括号（需求 2.5）。不满足时抛 ValueError。"""
    if not unit_id or _ID_BAD.search(unit_id):
        raise ValueError(f"单元 ID 不能为空，也不能含空白或方括号：{unit_id!r}")


def title_to_id(title: str) -> str:
    """设计 4 第 1 条：连续的空白、`[`、`]`、`@` 换成一个 `-`，去掉首尾的 `-`；为空时用 `section`。"""
    return _ID_JUNK.sub("-", title).strip("-") or EMPTY_ID


def assign_ids(titles: Sequence[str], borrowed: Iterable[int] = ()) -> list[str]:
    """设计 4 第 2、5 条：同一参考源里的标题按文档顺序生成 ID，返回顺序和 `titles` 相同。

    先给每个标题保留它自己生成的 ID；同一个 ID 第二次出现起，从 `-2` 往后找空号。
    空号要避开已经给出的 ID，也要避开所有标题自己的 ID（包括后面才出现的）。
    查重用 `casefold`，不区分大小写；ID 保留原来的大小写。

    `borrowed` 是标题借自文件名的位置（例如第一个标题之前的那段）。它们不算标题：
    等所有真标题分完 ID 再分，和真标题撞了就从 `-2` 起找空号。
    """
    bases = [title_to_id(t) for t in titles]
    late = sorted(set(borrowed))
    reserved = {b.casefold() for i, b in enumerate(bases) if i not in late}
    taken: set[str] = set()
    ids = [""] * len(bases)
    for i in [i for i in range(len(bases)) if i not in late] + late:
        base = uid = bases[i]
        if uid.casefold() in taken:
            n = 2
            while (c := f"{base}-{n}".casefold()) in taken or c in reserved:
                n += 1
            uid = f"{base}-{n}"
        taken.add(uid.casefold())
        ids[i] = uid
    return ids


def split_long(text: str, limit: int = LIMIT) -> list[str]:
    """设计 4 第 3 条：正文超过 `limit` 个字符就切成几段，拼回去等于原文。

    切在不超过 `limit` 的最后一个空行之后（空行算前一段的）。没有这样的空行，或者
    前一段只剩空白，就在第 `limit` 个字符处硬切。每段都不为空；只含空白的段只可能
    来自硬切（前 `limit` 个字符全是空白）。
    """
    if limit < 1:
        raise ValueError("limit 至少为 1")
    parts = []
    while len(text) > limit:
        first = len(text) - len(text.lstrip())  # 第一个非空白字符的位置
        cuts = [m.end() for m in _BLANK.finditer(text, 0, limit) if m.end() > first]
        cut = cuts[-1] if cuts else limit
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    return parts


def make_units(sections: Iterable[tuple[str, str]], kind: str, limit: int = LIMIT,
               borrowed: Iterable[int] = ()) -> list[Unit]:
    """把 (标题, 正文) 序列变成单元：先按标题定 ID，再拆超长的（设计 4 第 3 条）。

    `borrowed` 见 `assign_ids`；它只影响分 ID 的先后，单元顺序和 `sections` 相同。
    拆出的第 n 段（n ≥ 2）标题是"原标题 (n)"，ID 是原 ID 加 `@n`。标题生成的 ID 里
    没有 `@`，所以拆分出的 ID 不用再查重名。
    """
    sections = list(sections)
    units = []
    ids = assign_ids([t for t, _ in sections], borrowed)
    for (title, body), uid in zip(sections, ids):
        for n, part in enumerate(split_long(normalize_newlines(body), limit), start=1):
            if n == 1:
                units.append(Unit(uid, title, kind, part))
            else:
                units.append(Unit(f"{uid}@{n}", f"{title} ({n})", kind, part))
    return units


def find_unit(units: Iterable[Unit], unit_id: str) -> Unit:
    """按 ID 精确查找单元，找不到抛 KeyError。"""
    for u in units:
        if u.id == unit_id:
            return u
    raise KeyError(unit_id)
