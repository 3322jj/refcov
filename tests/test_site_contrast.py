"""Tests that the colours in site/style.css meet the WCAG contrast ratios.

Text needs at least 4.5:1. Graphics that carry state (cell borders and symbols, the shot
strip, focus rings, the blocked marker) need at least 3:1. Both palettes are checked: the
light values in the first :root block and the dark values in the prefers-color-scheme block.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "site" / "style.css").read_text(encoding="utf-8")

TEXT_PAIRS = [
    ("fg", "bg"),
    ("muted", "bg"),
    ("accent", "bg"),
    ("fg", "code-bg"),
    ("bg", "fg"),
    ("blocked", "bg"),
]

NON_TEXT_PAIRS = [
    ("cell-off-border", "bg"),
    ("cell-on", "bg"),
    ("cell-on-mark", "cell-on"),
    ("shot-off", "bg"),
    ("focus", "bg"),
    ("blocked", "bg"),
]


def _palette(block: str) -> dict[str, str]:
    return {name: value.lower() for name, value in re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6});", block)}


LIGHT = _palette(re.search(r":root\s*\{([^}]*)\}", CSS).group(1))
DARK = _palette(
    re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([^}]*)\}", CSS).group(1)
)


def _linear(channel: int) -> float:
    value = channel / 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    red, green, blue = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _linear(red) + 0.7152 * _linear(green) + 0.0722 * _linear(blue)


def contrast(first: str, second: str) -> float:
    """WCAG 2.x contrast ratio of two colours written as #rrggbb."""
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_both_palettes_define_every_colour_the_checks_use():
    """性质（设计第 5 节）：浅色和深色两组变量都定义了对比度检查用到的全部颜色。"""
    needed = {name for pair in TEXT_PAIRS + NON_TEXT_PAIRS for name in pair}
    assert needed <= set(LIGHT)
    assert needed <= set(DARK)


def test_text_contrast_is_at_least_4_5_in_both_palettes():
    """性质（需求 13.4）：正文、次要文字、链接和被拦文字在浅色和深色下对比度都不低于 4.5:1。"""
    for label, palette in (("light", LIGHT), ("dark", DARK)):
        for foreground, background in TEXT_PAIRS:
            ratio = contrast(palette[foreground], palette[background])
            assert ratio >= 4.5, (label, foreground, background, round(ratio, 2))


def test_graphics_contrast_is_at_least_3_in_both_palettes():
    """性质（需求 13.4，WCAG 1.4.11）：格子边框和符号、镜头条、焦点外框、被拦标记在两组颜色下都不低于 3:1。"""
    for label, palette in (("light", LIGHT), ("dark", DARK)):
        for foreground, background in NON_TEXT_PAIRS:
            ratio = contrast(palette[foreground], palette[background])
            assert ratio >= 3.0, (label, foreground, background, round(ratio, 2))
