"""应用只用标准库（需求 6.3，设计第 11 节）：apps/layer-coverage 的 Python 文件只 import 标准库和同目录的脚本；
只有 adapter.py 可以 import refcov.sources。检查程序自己也要能找到违规的 import（和 test_core_names.py 一样放进去试）。
"""

import ast
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "apps" / "layer-coverage"
FORBIDDEN = {
    "geopandas", "pyproj", "shapely", "fiona", "numpy", "pandas",
    "osgeo", "rasterio", "pyogrio", "ffmpeg", "PIL", "cv2",
}
SIBLINGS = {"stats", "adapter", "build", "fetch", "cli"}


def _imported_modules(source: str) -> list:
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            out.append("." * node.level + (node.module or ""))
    return out


def violations(file_name: str, source: str) -> list:
    bad = []
    for mod in _imported_modules(source):
        top = mod.split(".")[0]
        if file_name == "adapter.py" and mod == "refcov.sources":
            continue
        if mod.startswith(".") or top in FORBIDDEN:
            bad.append(mod)
        elif top in sys.stdlib_module_names:
            continue
        elif top in SIBLINGS and "." not in mod:
            continue
        else:
            bad.append(mod)
    return bad


@pytest.mark.parametrize("path", sorted(APP.glob("*.py")), ids=lambda p: p.name)
def test_app_files_import_only_the_standard_library(path):
    """需求 6.3：应用的每个 Python 文件只 import 标准库和同目录的脚本；adapter.py 可以 import refcov.sources。"""
    assert violations(path.name, path.read_text(encoding="utf-8")) == []


def test_checker_finds_planted_violations():
    """检查程序自己（设计第 11 节）：放进去的违规 import 必须被找到；adapter.py 的 refcov.sources 必须放行。"""
    for planted in ["import geopandas\n", "from pyproj import Transformer\n", "import numpy as np\n",
                    "from refcov.store import Store\n", "from . import stats\n"]:
        assert violations("build.py", planted), planted
    assert violations("adapter.py", "from refcov.sources import Unit\n") == []
