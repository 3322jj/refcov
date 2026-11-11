"""文档适配器：Markdown 按 `#` 到 `###` 拆成章节单元（需求 3，设计 4 第 3–5、8 条）。只用标准库。

已知局限：下划线式标题（`===`、`---`）不拆；超长切分时代码块里的空行也可能被当成切点。
"""

import re

from refcov.sources import KindDecl, find_unit, make_units, normalize_newlines

name = "markdown"
kinds = {"section": KindDecl(strict=True, key=False)}  # 需求 2.3：章节严格必看，没有关键类型

_LINE = re.compile(r".*\n|.+")  # 逐行，带换行符
# 最多 3 个空格缩进，1–3 个 #，后面是空白或行尾；`>` 开头的行匹配不上，所以不算标题
_HEADING = re.compile(r" {0,3}(#{1,3})(?:[ \t](.*))?")
_CLOSING = re.compile(r"(?:^|[ \t])#+[ \t]*$")  # 标题末尾的收尾 #，前面要有空白
_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")


def _headings(text):
    """返回 [(行首位置, 下一行开头位置, 标题)]，跳过代码块里的行。没闭合的代码块算到文件末尾。"""
    found, fence = [], None
    for m in _LINE.finditer(text):
        line = m.group().rstrip("\n")
        f = _FENCE.fullmatch(line)
        if fence:  # 闭合围栏：同一种字符，不短于开头，后面只有空白
            if f and f[1][0] == fence[0] and len(f[1]) >= len(fence) and not f[2].strip():
                fence = None
        elif f and not (f[1][0] == "`" and "`" in f[2]):  # ``` 开头的说明里不能有 `
            fence = f[1]
        elif h := _HEADING.fullmatch(line):
            title = _CLOSING.sub("", (h[2] or "").strip()).strip()
            found.append((m.start(), m.end(), title))
    return found


def sections(text: str, name: str):
    """返回 ((标题, 正文) 序列, 标题借自文件名的位置)。正文不含标题行。第一个标题前的正文不全是空白时，
    单独成一节排在最前，标题取 `name`；一个标题都没有时整篇是一节（需求 3.6）。"""
    text = normalize_newlines(text)
    heads = _headings(text)
    if not heads:
        return [(name, text)], {0}
    out = [(name, text[: heads[0][0]])] if text[: heads[0][0]].strip() else []
    ends = [s for s, _, _ in heads[1:]] + [len(text)]
    return out + [(t, text[e:end]) for (_, e, t), end in zip(heads, ends)], set(range(len(out)))


def split(data: bytes, name: str):
    """按 UTF-8 解码（去掉开头的 BOM），拆成单元。`name` 是文件名，不带扩展名。
    借文件名的那节最后分 ID，不和真标题抢（设计 4 第 5 条）。"""
    secs, borrowed = sections(data.decode("utf-8-sig"), name)
    return make_units(secs, "section", borrowed=borrowed)


def read(data: bytes, name: str, unit_id: str):
    return [find_unit(split(data, name), unit_id).text]


def facts(data: bytes, name: str, unit_id: str) -> dict:
    u = find_unit(split(data, name), unit_id)
    return {"title": u.title, "chars": u.chars, "sha256": u.sha256}
