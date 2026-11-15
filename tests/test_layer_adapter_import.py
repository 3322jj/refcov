"""适配器的导入守卫（设计第 3.1.1 节、第 11 节）。

导入 `apps/layer-coverage/adapter.py` 时不调用子进程、网络、文件哈希，用时不超过 0.5 秒；
顶层语句只能是 import、常量、`KindDecl(...)` 赋值、函数和类定义，以及文档字符串。
"""

import ast
import hashlib
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

import refcov.store
from refcov.adapters import loader
from refcov.store import Store

ADAPTER_PATH = Path(__file__).resolve().parents[1] / "apps" / "layer-coverage" / "adapter.py"
CONFIG = '[adapters]\nlayer = "apps/layer-coverage/adapter.py"\n'


def _workspace(tmp_path):
    root = tmp_path / "ws"
    (root / "apps" / "layer-coverage").mkdir(parents=True)
    (root / "apps" / "layer-coverage" / "adapter.py").write_bytes(ADAPTER_PATH.read_bytes())
    (root / "refcov.toml").write_text(CONFIG, encoding="utf-8")
    return root


def test_import_calls_no_subprocess_network_or_hashing(tmp_path, monkeypatch):
    """导入守卫（设计 3.1.1）：经核心层加载器导入适配器时，子进程、网络、文件哈希一次都不调用。"""

    def boom(*args, **kwargs):
        raise AssertionError("导入适配器时不许调用这个函数")

    for mod, attr in [
        (subprocess, "run"), (subprocess, "call"), (subprocess, "Popen"),
        (socket, "socket"), (urllib.request, "urlopen"),
        (hashlib, "sha256"), (hashlib, "new"),
    ]:
        monkeypatch.setattr(mod, attr, boom)
    monkeypatch.setattr(refcov.store, "sha256_file", boom)
    mod = loader.load(Store(_workspace(tmp_path)), "layer")
    assert mod.name == "layer"


def test_import_takes_at_most_half_a_second(tmp_path):
    """导入守卫（设计 3.1.1）：导入适配器的用时不超过 0.5 秒。"""
    root = _workspace(tmp_path)
    start = time.perf_counter()
    loader.load(Store(root), "layer")
    assert time.perf_counter() - start <= 0.5


def _cheap(node) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_cheap(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and _cheap(k) for k in node.keys) and all(_cheap(v) for v in node.values)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "KindDecl":
        return all(_cheap(a) for a in node.args) and all(_cheap(k.value) for k in node.keywords)
    return False


def test_top_level_statements_are_only_the_cheap_kinds():
    """导入守卫（设计 3.1.1）：顶层语句只能是 import、函数和类定义、文档字符串，以及右边是常量、字典、KindDecl(...) 的赋值。"""
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.Assign) and _cheap(node.value):
            continue
        pytest.fail(f"顶层语句不便宜（第 {node.lineno} 行）")
