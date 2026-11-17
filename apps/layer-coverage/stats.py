"""字段统计（设计第 5 节）：非空数、文字形式、不同取值数、前 5 个、值为 0 的条数、类型。

只用标准库。`build.py` 用它算清单里每个字段的数字；适配器不用它。
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass

TOP_N = 5


@dataclass(frozen=True)
class FieldStats:
    rows: int
    non_null: int
    distinct: int
    top: tuple[tuple[str, int], ...]
    zeros: int
    types: tuple[str, ...]


def text_of(value) -> str | None:
    """非空值的文字形式：字符串原样，布尔和数字用 json.dumps。null 返回 None。"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def is_zero(value) -> bool:
    """数字等于 0，或字符串去掉空白后能读成 0。布尔、空字符串、null 不算。"""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return False
        try:
            return float(s) == 0
        except ValueError:
            return False
    return False


def value_counts(values) -> Counter:
    """每个文字形式出现的条数（不含 null）。"""
    return Counter(t for t in (text_of(v) for v in values) if t is not None)


def ranked(counts: Counter) -> list[tuple[str, int]]:
    """按条数从多到少，同数按文字的码位顺序。"""
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def stats_of(values) -> FieldStats:
    """一个属性在全部行里的值（缺键按 null 传入）的统计。"""
    values = list(values)
    counts = value_counts(values)
    return FieldStats(
        rows=len(values),
        non_null=sum(counts.values()),
        distinct=len(counts),
        top=tuple(ranked(counts)[:TOP_N]),
        zeros=sum(1 for v in values if is_zero(v)),
        types=tuple(sorted({type(v).__name__ for v in values if v is not None})),
    )
