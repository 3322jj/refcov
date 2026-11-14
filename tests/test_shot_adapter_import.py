"""导入镜头适配器时不做任何耗时的事（镜头应用设计 3.1.1，需求 1.10）。

写文件关卡的每次检查都会经 `api._decls` 加载适配器；加载就是导入这个文件。
"""

import ast
import hashlib
import importlib.util
import shutil
import subprocess
import sys
import time

import pytest

import shot_loader

# 顶层赋值右边允许的调用：都是廉价的构造
CHEAP_CALLS = {"KindDecl", "compile", "dataclass", "frozenset", "dict", "set", "tuple", "field"}


def top_level_calls(tree):
    """模块顶层（不含函数体和类体里的方法）出现的函数调用名。"""
    found = []

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node):  # 只看默认值和装饰器，不看函数体
            for d in node.decorator_list + node.args.defaults + [d for d in node.args.kw_defaults if d]:
                self.visit(d)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            for d in node.decorator_list + node.bases:
                self.visit(d)
            for stmt in node.body:
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.visit(stmt)
                else:
                    self.visit_FunctionDef(stmt)

        def visit_Call(self, node):
            f = node.func
            found.append(f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else "?")
            self.generic_visit(node)

    V().visit(tree)
    return found


def test_top_level_statements_are_only_cheap():
    """静态检查：顶层只有 import、赋值、函数和类定义、文档字符串；顶层的函数调用只能是廉价的构造。"""
    tree = ast.parse(shot_loader.ADAPTER_PATH.read_text(encoding="utf-8"))
    allowed = (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.FunctionDef, ast.AsyncFunctionDef,
               ast.ClassDef)
    for node in tree.body:
        is_doc = isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        assert isinstance(node, allowed) or is_doc, f"第 {node.lineno} 行：顶层不该有 {type(node).__name__}"
    calls = top_level_calls(tree)
    assert set(calls) <= CHEAP_CALLS, f"顶层调用了不在白名单里的函数：{sorted(set(calls) - CHEAP_CALLS)}"


def test_import_triggers_no_subprocess_no_hashing_no_lookup(monkeypatch):
    """用"一调用就失败"的替身换掉子进程、查 PATH 和哈希，经核心层的加载器导入：必须成功、不触发替身、不超过 0.5 秒。"""
    from refcov.adapters import loader
    from refcov.store import Store

    def boom(*a, **k):
        raise AssertionError("导入适配器时不该做这件事")

    for obj, attr in ((subprocess, "run"), (subprocess, "Popen"), (subprocess, "check_output"),
                      (subprocess, "call"), (shutil, "which"), (hashlib, "sha256"), (hashlib, "file_digest"),
                      (hashlib, "new")):
        if hasattr(obj, attr):
            monkeypatch.setattr(obj, attr, boom)
    import refcov.store

    monkeypatch.setattr(refcov.store, "sha256_file", boom)
    # 经加载器加载：临时仓库里放一份适配器副本，配置里按路径声明
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".git").mkdir()
        target = root / "apps" / "shot-coverage"
        target.mkdir(parents=True)
        (target / "adapter.py").write_bytes(shot_loader.ADAPTER_PATH.read_bytes())
        (root / "refcov.toml").write_text('[adapters]\nshot = "apps/shot-coverage/adapter.py"\n', encoding="utf-8")
        t0 = time.monotonic()
        mod = loader.load(Store(root), "shot")
        elapsed = time.monotonic() - t0
    assert mod.name == "shot" and elapsed < 0.5, elapsed
    sys.modules.pop("refcov_adapter_shot", None)
