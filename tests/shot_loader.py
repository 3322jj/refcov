"""测试用：从文件路径加载镜头适配器（和核心层加载它的办法一样，目录名带连字符不能当包名导入）。"""

import importlib.util
import sys
from pathlib import Path

ADAPTER_PATH = Path(__file__).resolve().parents[1] / "apps" / "shot-coverage" / "adapter.py"
CLI_PATH = ADAPTER_PATH.with_name("cli.py")
MODULE = "shot_adapter_under_test"


def load():
    """加载（只加载一次）并返回适配器模块。"""
    if MODULE in sys.modules:
        return sys.modules[MODULE]
    spec = importlib.util.spec_from_file_location(MODULE, ADAPTER_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[MODULE] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(MODULE, None)
        raise
    return mod
