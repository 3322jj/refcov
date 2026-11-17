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
    """性质（需求 9.4、12.1、15.1）：页面只加载同目录的 style.css 和 app.js，没有第三方资源；HTTPS 地址只出现在 a 的 href 里，或在 code 里作为要复制的安装命令（只能是安装地址）。"""
    assert re.findall(r"<script[^>]*>", HTML) == ['<script src="app.js" defer>']
    assert re.findall(r"<link[^>]*>", HTML) == ['<link rel="stylesheet" href="style.css">']
    assert not re.search(r"<(img|iframe|source|video|audio|object|embed)\b", HTML)
    code_urls = [
        url
        for part in re.findall(r"<code>(.*?)</code>", HTML, re.S)
        for url in re.findall(r"https?://[^\s\"'<>)]+", part)
    ]
    assert code_urls == ["https://github.com/3322jj/refcov"]
    outside_code = re.sub(r"<code>.*?</code>", "", HTML, flags=re.S)
    all_urls = re.findall(r"https?://[^\s\"'<>)]+", outside_code)
    href_urls = re.findall(r'href="(https?://[^"]+)"', HTML)
    assert sorted(all_urls) == sorted(href_urls)
    assert "@import" not in CSS
    assert "url(" not in CSS
    assert not re.search(r"https?://", JS)


def test_section_seven_gives_the_four_install_steps():
    """性质（需求 7.3、7.4）：第 7 段按顺序写四步：用 uv 装包；在项目根目录运行 init 和 doctor；在 Kiro 里打开项目并信任工作区；在 [sources] 里列出材料并运行 sync；链接到 README 的 Setup 一节。不提 setup.py 和 pip install。"""
    start = HTML.index('<section id="s7"')
    section = HTML[start : HTML.index("</section>", start)]
    steps = re.findall(r"<li>(.*?)</li>", section, re.S)
    assert len(steps) == 4
    assert "<code>uv tool install git+https://github.com/3322jj/refcov</code>" in steps[0]
    assert "<code>refcov init</code>" in steps[1] and "<code>refcov doctor</code>" in steps[1]
    assert "trust the workspace" in steps[2] and "Kiro" in steps[2]
    assert "<code>[sources]</code>" in steps[3] and "<code>refcov sync</code>" in steps[3]
    assert 'href="https://github.com/3322jj/refcov#setup"' in section
    assert "setup.py" not in section
    assert "pip install" not in section


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


def test_gate_message_is_named_once_in_the_gate_box():
    """性质（需求 4.1）：拦截框里的 "gate message, translated" 只出现一次（标签）；回放里的注释由 app.js 写出。"""
    assert HTML.lower().count("gate message, translated") == 1
    assert "(gate message, translated)" in JS


def test_section_six_says_sub_agent_reads_pass_the_gate():
    """性质（product.md 新增的一条）：第 6 段照实写：子代理替读的单元，关卡照样放行，Kiro 自己报告了这件事。"""
    section = HTML[HTML.index('<section id="s6"'): HTML.index('<section id="s7"')]
    assert (
        "RefCov records that a unit was read in this workspace, not which agent read it. "
        "While this page was being built, Kiro had sub-agents read 174 guide units for it, "
        "and the gate let the next write through. Kiro reported this itself."
    ) in section


def test_long_article_note_names_all_three_javascript_uses():
    """性质（前端扩展试验第 4 节）：长文页那行写出三处都用了 JavaScript：进度条、页眉、吸顶标题。"""
    section = HTML[HTML.index('<section id="s2"'): HTML.index('<section id="s3"')]
    assert (
        "After reading, one run used JavaScript for the progress bar, the header and the sticky headings "
        "(a conservative choice)."
    ) in section


def test_replay_pause_resume_and_replay_are_all_labelled():
    """性质（WCAG 2.2.2，g-motion 指南）：自动播放的回放有可见的暂停、继续、重播控件；按钮文字会变，所以不用 aria-pressed。"""
    for label in ("Pause", "Play", "Replay"):
        assert f'"{label}"' in JS, label
    assert "aria-pressed" not in JS
    assert "aria-pressed" not in HTML


def test_blocked_step_flash_starts_when_revealed_and_animates_opacity():
    """性质（g-motion 指南：动效用 opacity；闪动不超过每秒三次）：被拦的一步在显示时才开始闪，闪动只改 opacity，共两次。"""
    assert '"revealed"' in JS
    assert ".steps li.blocked.revealed::after" in CSS
    assert "animation: flash 1.2s ease-in-out 2;" in CSS
    assert "outline: 2px solid transparent" not in CSS


def test_press_feedback_differs_from_hover():
    """性质（g-natural-interactions 指南：每个控件有悬停、按下、焦点三种可见反馈）：按下状态有自己的样式。"""
    assert ".replay-button:hover" in CSS
    assert ".replay-button:active" in CSS


def test_scrollable_table_regions_are_keyboard_reachable_and_named():
    """性质（g-sortable-table 指南：可横向滚动的表格外层能用键盘聚焦，并有名字）：四个表格外层都是 role=region、tabindex=0，aria-labelledby 指向存在的表题。"""
    wrappers = re.findall(r'<div class="table-wrap" role="region" tabindex="0" aria-labelledby="([^"]+)">', HTML)
    assert len(wrappers) == 4
    for caption_id in wrappers:
        assert f'<caption id="{caption_id}">' in HTML, caption_id
    assert ".table-wrap > table { min-inline-size: 36rem; }" in CSS


def test_ledger_is_folded_in_a_details_element():
    """性质（用户要求）：第 5 段施工账表默认折叠（details），折叠前只有一句摘要。"""
    assert "<details>" in HTML and "<summary>" in HTML
    details = HTML[HTML.index("<details>"): HTML.index("</details>")]
    assert 'class="ledger responsive"' in details


def test_footer_names_the_sources_and_licenses():
    """性质（用户要求，需求 9.2、9.5）：页脚写明数据、字典、指南标题的来源和许可，并声明与纽约市政府没有关联。"""
    footer = HTML[HTML.index("<footer>"): HTML.index("</footer>")]
    assert (
        "Sources and licenses: NYC Building Footprints from NYC Open Data (no use restrictions; "
        "not affiliated with the City of New York); field names and section titles from "
        "CityOfNewYork/nyc-geo-metadata (Apache-2.0); guide titles from Chrome's modern web guidance "
        "(Apache-2.0)."
    ) in footer
