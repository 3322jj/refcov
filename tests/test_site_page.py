"""Tests for the static demo page in site/ (index.html, style.css, app.js).

These are checks on the page source, not on a rendered page. They run on Linux and
Windows CI without a browser and without reading any file outside the repository.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
HTML = (SITE / "index.html").read_text(encoding="utf-8")
CSS = (SITE / "style.css").read_text(encoding="utf-8")
JS = (SITE / "app.js").read_text(encoding="utf-8")

CJK = re.compile(r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]")

SECTION_IDS = ["s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7"]

FIXED_SENTENCES = [
    # Requirement 4.1: the gate message, in English, with the translation note.
    "Write blocked by the RefCov gate: required units not read yet.",
    "(gate message, translated)",
    # Requirement 4.3: the result sentence, with no area figure.
    "answer.md written. Graded outside this repository: within \u00b13% of the reference answer.",
    # Requirement 4.4: the sentence about the dictionary and the 24 units.
    "Without RefCov, the model also looked up the dictionary on this dataset. RefCov adds a count "
    "you can check, and here the answer file could not be written until all 24 units had been read.",
    # Requirement 1.2: the one-sentence claim and its scope.
    "How much of your reference material did the AI actually read?",
    "not statistics",
]

# Claims the product rules do not allow (product.md, the "do not say" list), written as the
# page would have to word them. Matching is case-insensitive on the whole HTML source.
FORBIDDEN_PHRASES = [
    "faster and cheaper",
    "pages are better",
    "makes the answer right",
    "stops the ai",
    "ai can only",
    "the ai cannot write",
    "installing refcov guarantees",
]


def test_eight_sections_in_order():
    """性质（需求 1.1）：八段按 s0 到 s7 的顺序出现，每段是一个带 id 的 section，id 不重复。"""
    ids = re.findall(r'<section id="(s\d)"', HTML)
    assert ids == SECTION_IDS


def test_one_page_in_english_with_a_skip_link():
    """性质（需求 1.1、12.3）：只有一页，一个 main，lang 为 en，跳过链接指向 main。"""
    assert '<html lang="en">' in HTML
    assert HTML.count("<main") == 1
    assert 'id="main"' in HTML
    assert 'href="#main"' in HTML


def test_no_external_resources_are_loaded():
    """性质（需求 9.4、12.1、15.1）：页面只加载同目录的 style.css 和 app.js，没有第三方资源；HTTPS 只出现在 a 的 href 里。"""
    assert re.findall(r"<script[^>]*>", HTML) == ['<script src="app.js" defer>']
    assert re.findall(r"<link[^>]*>", HTML) == ['<link rel="stylesheet" href="style.css">']
    assert not re.search(r"<(img|iframe|source|video|audio|object|embed)\b", HTML)
    all_urls = re.findall(r"https?://[^\s\"'<>)]+", HTML)
    href_urls = re.findall(r'href="(https?://[^"]+)"', HTML)
    assert sorted(all_urls) == sorted(href_urls)
    assert "@import" not in CSS
    assert "url(" not in CSS
    assert not re.search(r"https?://", JS)


def test_no_chinese_characters_in_the_page_files():
    """性质（需求 12.3）：页面的 HTML、CSS 和 JavaScript 里没有中文字符。"""
    for name, text in (("index.html", HTML), ("style.css", CSS), ("app.js", JS)):
        assert not CJK.search(text), name


def test_app_js_writes_text_only():
    """性质（安全，设计第 2 节）：app.js 用 textContent 写数据，不用会把数据当 HTML 解析的接口。"""
    for pattern in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert pattern not in JS, pattern


def test_fixed_sentences_appear_as_written():
    """性质（需求 1.2、4.1、4.3、4.4）：固定英文句原样出现在页面上。"""
    for sentence in FIXED_SENTENCES:
        assert sentence in HTML, sentence


def test_every_cell_has_an_accessible_name():
    """性质（需求 13.5）：页面上每个格子都有文字替代，屏幕阅读器能读到单元名或运行的状态。"""
    cells = re.findall(r'<li class="cell (?:on|off)">(.*?)</li>', HTML)
    assert len(cells) == 32  # two rows of 16 cells in the first section
    for cell in cells:
        assert 'class="sr"' in cell
    # The replay cells are built in app.js with the same accessible-name pattern.
    assert 'srText("read: " + name)' in JS


def test_reduced_motion_shows_the_final_state_with_a_note():
    """性质（需求 13.6）：设定了减少动态效果时不播放，直接显示结束状态，并附一段文字说明。"""
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert "Motion is off because your system asks for reduced motion." in HTML
    assert "prefers-reduced-motion" in JS


def test_focus_is_visible_and_theme_follows_the_system():
    """性质（需求 13.1、13.3）：键盘焦点有可见外框；深浅色跟随系统，没有切换按钮。"""
    assert ":focus-visible" in CSS
    assert "color-scheme: light dark" in CSS
    assert "@media (prefers-color-scheme: dark)" in CSS
    assert "theme" not in HTML.lower()


def test_the_page_loads_only_the_replay_data_files_it_ships():
    """性质（需求 12.2）：页面只读同目录 data/ 下的 JSON，被读的每个文件都存在。"""
    names = sorted(set(re.findall(r'"(?:data/)?(w-h-03|wb-h-03|g-01|vb-01)\.json"', JS)))
    assert names == ["g-01", "vb-01", "w-h-03", "wb-h-03"]
    for name in names:
        assert (SITE / "data" / f"{name}.json").is_file()


def test_no_local_paths_in_the_page_source():
    """性质（需求 8.2、9.1）：页面源码里没有本机路径。"""
    for text in (HTML, CSS, JS):
        assert "D:\\" not in text
        assert "/Users/" not in text
        assert "/home/" not in text


def test_forbidden_claims_are_absent():
    """性质（需求 11.2）：页面上没有 product.md '不说' 清单里的说法（英文版，逐条检查，不区分大小写）。"""
    lowered = HTML.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in lowered, phrase
