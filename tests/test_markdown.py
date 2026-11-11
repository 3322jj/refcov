"""adapters/markdown.py：按 `#` 到 `###` 拆章节（任务 3，需求 3，设计 4 第 3–5、8 条）。"""

import hashlib

import pytest
from hypothesis import given, strategies as st

from refcov.adapters import markdown
from refcov.sources import KindDecl, check_declarations

# kiro.dev 的 .md 页面开头是一段 "> ## Documentation Index" 引用（设计 4 第 4 条）
KIRO_LIKE = """\
> ## Documentation Index
> Fetch the complete documentation index at: https://kiro.dev/llms.txt

# Hooks

Hooks run commands when events happen.

## Exit codes

Only exit code 2 blocks.

```bash
# 注释：这一行不是标题
echo blocked >&2
exit 2
```

### Matchers

Use exact tool names.

#### Regex details

Deeper headings stay in the parent unit.

## Examples

See below.
"""


def titles(units):
    return [u.title for u in units]


def ids(units):
    return [u.id for u in units]


def test_kiro_like_page():
    """完成标志 2：引用块不当标题；代码块里的 "# 注释" 不当标题；章节数和标题对得上。"""
    units = markdown.split(KIRO_LIKE.encode("utf-8"), "hooks")
    assert titles(units) == ["hooks", "Hooks", "Exit codes", "Matchers", "Examples"]
    assert ids(units) == ["hooks-2", "Hooks", "Exit-codes", "Matchers", "Examples"]
    pre, _, exit_codes, matchers, _ = units
    assert pre.text.startswith("> ## Documentation Index\n")  # 引用块的正文照常留在单元里
    assert "# 注释：这一行不是标题\n" in exit_codes.text
    assert "#### Regex details" in matchers.text
    assert all(u.kind == "section" for u in units)


def test_file_name_unit_yields_to_real_heading():
    """设计 4 第 5 条（2026-11-11）：开头那段借文件名当标题，最后分 ID。
    kiro.dev 样例里 "# Hooks" 拿 `Hooks`，开头那段拿 `hooks-2`；清单里开头那段仍排第一。"""
    units = markdown.split(KIRO_LIKE.encode("utf-8"), "hooks")
    assert [(u.id, u.title) for u in units[:2]] == [("hooks-2", "hooks"), ("Hooks", "Hooks")]


def test_file_name_unit_skips_ids_of_later_headings():
    text = "前言\n# 说明\na\n# 说明-2\nb\n"
    assert ids(markdown.split(text.encode("utf-8"), "说明")) == ["说明-3", "说明", "说明-2"]


def test_file_name_unit_keeps_its_name_when_free():
    assert ids(markdown.split("前言\n# 一\n".encode("utf-8"), "hooks")) == ["hooks", "一"]


def test_crlf_gives_same_units_and_checksums():
    lf = markdown.split(KIRO_LIKE.encode("utf-8"), "hooks")
    crlf = markdown.split(KIRO_LIKE.replace("\n", "\r\n").encode("utf-8"), "hooks")
    cr = markdown.split(KIRO_LIKE.replace("\n", "\r").encode("utf-8"), "hooks")
    assert [u.manifest_entry() for u in lf] == [u.manifest_entry() for u in crlf]
    assert [u.manifest_entry() for u in lf] == [u.manifest_entry() for u in cr]


def test_bom_is_dropped():
    units = markdown.split("\ufeff# 标题\n正文\n".encode("utf-8"), "doc")
    assert titles(units) == ["标题"] and units[0].text == "正文\n"


def test_checksum_is_sha256_of_body_without_heading():
    (u,) = markdown.split("## 退出码\r\n只有 2 能拦。\r\n".encode("utf-8"), "doc")
    assert u.text == "只有 2 能拦。\n"
    assert u.sha256 == hashlib.sha256("只有 2 能拦。\n".encode("utf-8")).hexdigest()
    assert u.chars == len("只有 2 能拦。\n")


@pytest.mark.parametrize(
    "line, title",
    [
        ("# A", "A"),
        ("   ### A", "A"),  # 最多 3 个空格
        ("##\tA", "A"),
        ("## A ##", "A"),  # 收尾的 # 去掉
        ("## A ##  ", "A"),
        ("## A#", "A#"),  # 前面没有空白，不是收尾符号
        ("## C# 入门", "C# 入门"),
        ("##", ""),
        ("## ##", ""),
        ("#   ", ""),
    ],
)
def test_heading_lines(line, title):
    units = markdown.split(f"{line}\nbody\n".encode("utf-8"), "doc")
    assert titles(units) == [title]
    assert units[0].id == (title.replace(" ", "-") or "section")


@pytest.mark.parametrize(
    "line",
    ["#tag", "##A", "    # 缩进 4 格是代码", "\t# 制表符缩进", "#### 四级", "####### 七个",
     "> # 引用", "> ## Documentation Index", " > ## 有缩进的引用", "\\# 转义"],
)
def test_not_headings(line):
    units = markdown.split(f"intro\n{line}\nmore\n".encode("utf-8"), "doc")
    assert titles(units) == ["doc"]
    assert line in units[0].text


def test_tilde_fence_and_closing_rules():
    text = (
        "# 一\n"
        "~~~\n"
        "# 不是标题\n"
        "```\n"  # 字符不同，不闭合
        "# 也不是\n"
        "~~~\n"
        "````md\n"
        "# 还不是\n"
        "```\n"  # 比开头短，不闭合
        "```` 尾巴\n"  # 后面有别的字，不闭合
        "## 仍在代码块里\n"
        "   `````\n"  # 闭合：更长、缩进不超过 3
        "## 二\n"
    )
    units = markdown.split(text.encode("utf-8"), "doc")
    assert titles(units) == ["一", "二"]


def test_backtick_info_with_backtick_is_not_a_fence():
    units = markdown.split("```a`b\n# 是标题\n".encode("utf-8"), "doc")
    assert titles(units) == ["doc", "是标题"]


def test_unclosed_fence_runs_to_end():
    units = markdown.split("# 一\n```\n# 不是\n## 也不是\n".encode("utf-8"), "doc")
    assert titles(units) == ["一"]
    assert units[0].text == "```\n# 不是\n## 也不是\n"


def test_no_headings_is_one_unit_named_after_file():
    """需求 3.6：一个标题都没有，整篇一个单元，标题取文件名。"""
    units = markdown.split("只有正文\n\n第二段\n".encode("utf-8"), "说明 [草稿]")
    assert [(u.id, u.title, u.text) for u in units] == [("说明-草稿", "说明 [草稿]", "只有正文\n\n第二段\n")]
    (empty,) = markdown.split(b"", "empty")
    assert (empty.id, empty.text) == ("empty", "")


def test_whitespace_only_preamble_is_not_a_unit():
    units = markdown.split(" \n\t\n\n# 标题\n正文\n".encode("utf-8"), "doc")
    assert titles(units) == ["标题"]


def test_heading_without_body_is_still_a_unit():
    units = markdown.split("# 一\n## 二\n".encode("utf-8"), "doc")
    assert [(u.title, u.text) for u in units] == [("一", ""), ("二", "")]


def test_duplicate_headings_follow_design_rule():
    text = "## 退出码\na\n## 退出码\nb\n## 退出码-2\nc\n"
    assert ids(markdown.split(text.encode("utf-8"), "doc")) == ["退出码", "退出码-3", "退出码-2"]


def test_long_section_is_split_at_blank_lines():
    """需求 3.5，设计 4 第 3 条：超过 4000 字按空行切，@2、@3 依次编号，拼回等于这一节的正文。"""
    para = ("钩子" * 450 + "\n\n")  # 902 字一段
    body = para * 10  # 9020 字
    text = "# 长章节\r\n" + body.replace("\n", "\r\n") + "# 下一节\n短\n"
    units = markdown.split(text.encode("utf-8"), "doc")
    assert ids(units) == ["长章节", "长章节@2", "长章节@3", "下一节"]
    assert titles(units) == ["长章节", "长章节 (2)", "长章节 (3)", "下一节"]
    assert [u.chars for u in units[:3]] == [902 * 4, 902 * 4, 902 * 2]
    assert "".join(u.text for u in units[:3]) == body


def test_long_section_without_blank_line_is_hard_cut():
    body = "x" * 9001
    units = markdown.split(f"# 长\n{body}".encode("utf-8"), "doc")
    assert [u.chars for u in units] == [4000, 4000, 1001]


def test_declarations_match_requirement_2_3():
    """需求 2.3：章节严格模式必看，没有关键类型。"""
    assert markdown.name == "markdown"
    assert markdown.kinds == {"section": KindDecl(strict=True, key=False)}
    check_declarations(markdown.kinds)


def test_read_and_facts():
    data = KIRO_LIKE.encode("utf-8")
    (text,) = markdown.read(data, "hooks", "Exit-codes")
    assert text.startswith("\nOnly exit code 2 blocks.")
    facts = markdown.facts(data, "hooks", "Exit-codes")
    assert facts["title"] == "Exit codes" and facts["chars"] == len(text)
    with pytest.raises(KeyError):
        markdown.read(data, "hooks", "不存在")


def test_markdown_imports_only_stdlib_and_refcov():
    """需求 3.2：只用标准库（加上核心层自己的 refcov.sources）。"""
    import ast
    import sys
    from pathlib import Path

    tree = ast.parse(Path(markdown.__file__).read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods - {"refcov"} <= set(sys.stdlib_module_names)


# ---- 属性测试 ----

_MD_LINES = st.one_of(
    st.sampled_from(["# 标题", "## 退出码", "## 退出码", "### 退出码-2", "## Hooks", "## hooks",
                     "#tag", "> ## Documentation Index", "```", "~~~", "````", "# 注释", "",
                     " \t", "正文 [x] @y 😀", "#### 深"]),
    st.text(st.characters(codec="utf-8", exclude_characters="\n\r"), max_size=20),
)


@given(st.lists(_MD_LINES, max_size=40), st.sampled_from(["\n", "\r\n"]))
def test_prop_split_is_stable_and_ids_unique(lines, nl):
    """单元 ID 性质（设计 9）：同一份内容拆两次 ID 相同（需求 2.5），换行用 \\n 还是 \\r\\n 结果都一样；
    ID 不区分大小写互不重复，不含空白、方括号；每个单元不超过 4000 字。"""
    data = nl.join(lines).encode("utf-8")
    a = markdown.split(data, "doc")
    assert [u.manifest_entry() for u in a] == [u.manifest_entry() for u in markdown.split(data, "doc")]
    lf = markdown.split("\n".join(lines).encode("utf-8"), "doc")
    assert [u.manifest_entry() for u in a] == [u.manifest_entry() for u in lf]
    assert len({u.id.casefold() for u in a}) == len(a)
    assert all(not any(ch.isspace() or ch in "[]" for ch in u.id) for u in a)
    assert all(u.chars <= 4000 for u in a)
