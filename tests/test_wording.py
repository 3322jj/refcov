"""给 AI 看的说法（2026-11-17 第二层 install-test 的 F 项）：配置模板、保护提示和两个 MCP 工具的说明里，
不能再有"替用户登记"这类话。否则 AI 会照旧说法拒绝调用 apply_proposal。
"""

import ast
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OLD_WORDS = ("替用户登记", "替用户确认")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


init = _load("refcov_kiro_init_wording", REPO / "integrations" / "kiro" / "init.py")
hook = _load("refcov_kiro_hook_wording", REPO / "integrations" / "kiro" / "hook.py")
EXAMPLE = REPO / "integrations" / "kiro" / "refcov.example.toml"


def test_config_template_has_no_old_wording_and_describes_the_kiro_path():
    """性质：配置模板里没有"替用户登记"这类说法；[sources] 的注释写明在 Kiro 里说"登记成参考资料"时，
    AI 用 propose_sources 提议、apply_proposal 执行，执行前弹窗请用户批准，而且只新增。"""
    text = init.CONFIG_TEMPLATE
    for word in OLD_WORDS:
        assert word not in text, word
    for needle in ("把某个 Markdown 文件登记成参考资料", "propose_sources", "apply_proposal",
                   "弹窗请你批准", "只新增资料，不改已有的"):
        assert needle in text, needle
    assert "这个配置文件只能由用户手动修改" in text.splitlines()[0]


def test_watch_and_confirm_say_they_are_not_implemented():
    """性质（2026-11-17 核对）：配置模板和示例配置里，watch 和 confirm 两项上一行注释都是"暂未实现，填了不生效"。"""
    for text in (init.CONFIG_TEMPLATE, EXAMPLE.read_text(encoding="utf-8")):
        lines = text.splitlines()
        for key in ("watch = ", "confirm = "):
            idx = next(i for i, line in enumerate(lines) if line.startswith(key))
            assert lines[idx - 1] == "# 暂未实现，填了不生效", (key, lines[idx - 1])


def test_protect_text_has_no_old_wording_and_names_the_two_tools():
    """性质：保护提示（pre-write、pre-shell 拦下时 AI 看到的话）没有"替用户登记"这类说法，
    写明要登记资料用 propose_sources 和 apply_proposal，执行时用户在弹窗里批准。"""
    text = hook._PROTECT_TAIL
    for word in OLD_WORDS:
        assert word not in text, word
    for needle in ("propose_sources", "apply_proposal", "弹窗里批准"):
        assert needle in text, needle


def test_the_two_mcp_tool_descriptions_say_when_to_use_them_and_that_the_user_approves():
    """性质：propose_sources 和 apply_proposal 的说明（AI 读到的 docstring）都有"批准"，都没有旧说法；
    propose_sources 写明用户要求登记资料时用它；apply_proposal 写明只新增，并且弹窗里用户点批准就是授权。"""
    tree = ast.parse((REPO / "refcov_mcp" / "server.py").read_text(encoding="utf-8"))
    docs = {node.name: ast.get_docstring(node) or "" for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for name in ("propose_sources", "apply_proposal"):
        assert "批准" in docs[name], name
        for word in OLD_WORDS:
            assert word not in docs[name], (name, word)
    assert "用户要求登记" in docs["propose_sources"]
    assert "只新增" in docs["apply_proposal"] and "弹窗" in docs["apply_proposal"]


def test_init_next_step_mentions_the_kiro_sentence():
    """性质：init 打印的"下一步"里有"也可以在 Kiro 里说"把某个 Markdown 登记成参考资料""这一句。"""
    src = (REPO / "integrations" / "kiro" / "init.py").read_text(encoding="utf-8")
    assert "也可以在 Kiro 里说" in src
    assert "把某个 Markdown 登记成参考资料" in src
