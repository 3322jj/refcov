"""打包的静态检查（设计第 3 节）：pyproject 的 include 和 package-data，接入层文件和 5 个模板都在，
cli 只导入中性的转交模块。完整的 wheel 内容检查在 test_clean_install.py（默认跳过，它要打包和安装）。
"""

import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _setuptools() -> dict:
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]


def test_pyproject_includes_the_integration_package_and_its_hook_templates():
    cfg = _setuptools()
    assert "integrations*" in cfg["packages"]["find"]["include"]
    assert cfg["package-data"]["integrations.kiro"] == ["hooks/*.json"]


def test_integration_files_exist():
    base = REPO / "integrations"
    for rel in ["__init__.py", "commands.py", "kiro/__init__.py", "kiro/init.py", "kiro/doctor.py",
                "kiro/setup.py", "kiro/hook.py"]:
        assert (base / rel).is_file(), rel


def test_five_hook_templates_exist():
    names = sorted(p.name for p in (REPO / "integrations" / "kiro" / "hooks").glob("refcov-*.json"))
    assert names == ["refcov-post-mcp.json", "refcov-pre-shell.json", "refcov-pre-write.json",
                     "refcov-pretask.json", "refcov-prompt.json"]


def test_cli_imports_only_the_neutral_module():
    """设计 4.1：cli 只导入 integrations/commands.py，源码里没有接入层的导入字符串。"""
    text = (REPO / "refcov" / "cli.py").read_text(encoding="utf-8")
    assert "from integrations import commands" in text
    assert "integrations.kiro" not in text
