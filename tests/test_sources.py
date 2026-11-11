"""sources.py：单元 ID 生成、重名、超长拆分、适配器声明（任务 3，设计 4 第 1–3、8 条）。"""

import hashlib

import pytest
from hypothesis import example, given, strategies as st

from refcov.sources import (
    KindDecl,
    Unit,
    assign_ids,
    check_declarations,
    make_units,
    normalize_newlines,
    split_long,
    title_to_id,
    validate_unit_id,
)

# ---- 例子 ----


@pytest.mark.parametrize(
    "title, expected",
    [
        ("退出码", "退出码"),
        ("Exit  codes", "Exit-codes"),
        ("[beta] 钩子 @ 匹配", "beta-钩子-匹配"),
        ("  a\t\u3000b  ", "a-b"),  # 全角空格也算空白
        ("a - b", "a---b"),  # 原有的 - 保留，只换空白
        ("---", "section"),
        ("", "section"),
        ("[@]", "section"),
        ("Hooks😀", "Hooks😀"),
    ],
)
def test_title_to_id_examples(title, expected):
    assert title_to_id(title) == expected


def test_duplicates_get_suffixes_in_order():
    assert assign_ids(["退出码", "退出码", "退出码"]) == ["退出码", "退出码-2", "退出码-3"]


def test_suffix_skips_ids_reserved_by_later_headings():
    """设计 4 第 2 条（2026-11-11）：标题本身叫"退出码-2"时保留 `退出码-2`，重名的跳过它。"""
    assert assign_ids(["退出码", "退出码", "退出码-2"]) == ["退出码", "退出码-3", "退出码-2"]
    assert assign_ids(["退出码-2", "退出码", "退出码"]) == ["退出码-2", "退出码", "退出码-3"]


def test_duplicate_of_a_suffix_like_title():
    assert assign_ids(["a-2", "a-2", "a", "a"]) == ["a-2", "a-2-2", "a", "a-3"]


def test_duplicates_are_case_insensitive_and_keep_case():
    assert assign_ids(["Hooks", "hooks", "HOOKS"]) == ["Hooks", "hooks-2", "HOOKS-3"]
    assert assign_ids(["a", "A", "A-2"]) == ["a", "A-3", "A-2"]


def test_inserting_a_duplicate_does_not_rename_unique_titles():
    before = assign_ids(["退出码", "匹配", "退出码-2"])
    after = assign_ids(["退出码", "退出码", "匹配", "退出码-2"])
    assert before[2] == after[3] == "退出码-2"


@pytest.mark.parametrize("bad", ["", "a b", "a\tb", "a[b", "a]b", "退出码\u3000", "x\n"])
def test_ids_with_whitespace_or_brackets_are_rejected(bad):
    with pytest.raises(ValueError):
        validate_unit_id(bad)
    with pytest.raises(ValueError):
        Unit(bad, "t", "section", "")


def test_unit_checksum_and_chars():
    u = Unit("x", "x", "section", "第一行\n第二行\n")
    assert u.sha256 == hashlib.sha256("第一行\n第二行\n".encode("utf-8")).hexdigest()
    assert u.chars == 8
    assert u.manifest_entry() == {"id": "x", "title": "x", "kind": "section",
                                  "sha256": u.sha256, "chars": 8}


def test_normalize_newlines():
    assert normalize_newlines("a\r\nb\rc\n") == "a\nb\nc\n"


def test_split_long_cuts_after_last_blank_line():
    text = "a" * 5 + "\n\n" + "b" * 3 + "\n \t\n" + "c" * 10
    assert split_long(text, 15) == ["aaaaa\n\nbbb\n \t\n", "c" * 10]


def test_split_long_hard_cut_without_blank_line():
    assert split_long("x" * 25, 10) == ["x" * 10, "x" * 10, "x" * 5]


def test_split_long_never_cuts_an_empty_first_part():
    """开头就是空行时，切在它后面会得到只有空白的段：改成硬切。"""
    text = "\n  \n" + "y" * 20
    assert split_long(text, 10) == ["\n  \n" + "y" * 6, "y" * 10, "y" * 4]


def test_split_long_within_limit_is_one_part():
    assert split_long("", 10) == [""]
    assert split_long("x" * 10, 10) == ["x" * 10]


def test_make_units_split_titles_and_ids():
    body = "p1\n\n" + "q" * 8 + "\n\n" + "r" * 5
    units = make_units([("退出码", body), ("退出码", "short")], "section", limit=10)
    assert [(u.id, u.title) for u in units] == [
        ("退出码", "退出码"),
        ("退出码@2", "退出码 (2)"),
        ("退出码@3", "退出码 (3)"),
        ("退出码-2", "退出码"),
    ]
    assert "".join(u.text for u in units[:3]) == body


def test_make_units_normalizes_newlines_before_counting():
    units = make_units([("t", "ab\r\ncd")], "section", limit=5)
    assert [u.text for u in units] == ["ab\ncd"]


def test_check_declarations():
    check_declarations({"section": KindDecl(strict=True)})
    check_declarations({"shot": KindDecl(strict=True, key=True), "sample": KindDecl(strict=False)})
    with pytest.raises(ValueError):
        check_declarations({"sample": KindDecl(strict=False, key=True)})


# ---- 属性测试 ----

# 标题里故意放中文、各种空白、方括号、@、emoji、短横线和数字（testing.md、设计 9）
_TITLE_CHARS = st.one_of(
    st.sampled_from(list("退出码钩子 \t\u3000\u00a0[]@-2aAßİ😀")),
    st.characters(codec="utf-8"),
)
titles = st.text(_TITLE_CHARS, max_size=12)
# 重名标题和本身以"-2"结尾的标题：从一个小池子里抽，再随机加 -2
title_lists = st.lists(
    st.one_of(
        titles,
        st.sampled_from(["退出码", "退出码-2", "Hooks", "hooks", "a", "a-2", "a-3", "", "-"]),
        titles.map(lambda t: t + "-2"),
    ),
    max_size=20,
)
# 小池子：重名、只差大小写、本身带 -2/-3 的标题挤在一起，撞号的情况才常出现
title_lists = st.one_of(
    title_lists,
    st.lists(st.sampled_from(["a", "A", "a-2", "A-2", "a-3", "a-2-2", " a ", "[a]"]), max_size=8),
)


@given(titles)
def test_prop_title_id_has_no_whitespace_brackets_or_at(title):
    """单元 ID 性质（设计 9）：标题生成的 ID 不含空白、方括号，也不含 `@`，且能通过 ID 校验。"""
    uid = title_to_id(title)
    assert uid
    assert not any(ch.isspace() or ch in "[]@" for ch in uid)
    validate_unit_id(uid)


@given(title_lists)
def test_prop_ids_are_stable_and_unique(ts):
    """单元 ID 性质（设计 9）：同一标题序列生成两次 ID 相同；同一参考源里 ID 不区分大小写也互不重复。"""
    ids = assign_ids(ts)
    assert ids == assign_ids(list(ts))
    assert len({i.casefold() for i in ids}) == len(ids)
    for uid in ids:
        assert not any(ch.isspace() or ch in "[]@" for ch in uid)


@given(title_lists)
@example(["a", "a", "a-2"])  # 先到先得的做法会给 "a-2" 改名成 a-2-2
def test_prop_unique_titles_keep_their_own_id(ts):
    """单元 ID 性质（设计 4 第 2 条，2026-11-11）：生成的 ID 只出现一次的标题，拿到的就是它自己的 ID。"""
    bases = [title_to_id(t) for t in ts]
    folded = [b.casefold() for b in bases]
    for base, uid in zip(bases, assign_ids(ts)):
        if folded.count(base.casefold()) == 1:
            assert uid == base


@given(title_lists, st.data())
@example(["hooks", "Hooks"], None)  # kiro.dev 页面：开头那段借文件名 hooks，后面是 "# Hooks"
def test_prop_borrowed_titles_yield_to_real_titles(ts, data):
    """单元 ID 性质（设计 4 第 5 条，2026-11-11）：借文件名的标题最后分 ID，不抢真标题的 ID。
    真标题之间仍按第 2 条：生成的 ID 在真标题里只出现一次的，拿到的就是它自己的 ID；全部 ID 互不重复。"""
    borrowed = {0} if data is None else data.draw(st.sets(st.integers(0, max(len(ts) - 1, 0))))
    borrowed &= set(range(len(ts)))
    ids = assign_ids(ts, borrowed)
    assert len({i.casefold() for i in ids}) == len(ids)
    real = [i for i in range(len(ts)) if i not in borrowed]
    folded = [title_to_id(ts[i]).casefold() for i in real]
    for i in real:
        base = title_to_id(ts[i])
        if folded.count(base.casefold()) == 1:
            assert ids[i] == base
    assert assign_ids(ts, borrowed) == ids


# 正文由片段拼成：多放空行、只含空白的行和 \r\n、\r，让切点和换行统一都常出现
bodies = st.lists(
    st.one_of(st.sampled_from(["\n", "\n\n", " ", "\t", " \t\n", "\r\n", "\r", "x", "退"]),
              st.characters(codec="utf-8")),
    max_size=120,
).map("".join)


@given(bodies, st.integers(min_value=1, max_value=40))
def test_prop_split_long_reassembles(text, limit):
    """拆分性质（设计 9）：一段正文拆出的各段按顺序拼起来等于这段正文；每段不为空、不超过上限；
    只含空白的段只可能是硬切出来的（长度正好等于上限）。"""
    parts = split_long(text, limit)
    assert "".join(parts) == text
    assert all(len(p) <= limit for p in parts)
    if len(parts) > 1:
        assert all(parts)
        for p in parts[:-1]:
            assert p.strip() or len(p) == limit


@given(
    st.lists(st.tuples(titles, bodies), max_size=8),
    st.integers(min_value=1, max_value=30),
)
def test_prop_split_sections_reassemble_and_ids_unique(secs, limit):
    """拆分性质（设计 9）：一个超长章节的各段（原 ID、`@2`、`@3`……）正文拼起来，等于这一节换行统一后的
    正文；同一参考源里所有 ID（含 `@N`）互不重复。整篇文档拼不回来，不在这条性质里。"""
    borrowed = {0} if secs else set()  # 和文档适配器一样：第一节借文件名
    units = make_units(secs, "section", limit=limit, borrowed=borrowed)
    ids = assign_ids([t for t, _ in secs], borrowed)
    assert len({u.id.casefold() for u in units}) == len(units)
    for uid, (_, body) in zip(ids, secs):
        parts = [u for u in units if u.id == uid or u.id.startswith(uid + "@")]
        assert "".join(u.text for u in parts) == normalize_newlines(body)
        assert [u.id for u in parts] == [uid] + [f"{uid}@{n}" for n in range(2, len(parts) + 1)]
