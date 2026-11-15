"""命令行的测试（设计第 8 节）：列出字段单元，显示单元正文，错误的退出码，只读，不 import refcov，
和适配器的切法一致。"""

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "layer-coverage"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclass 解析注解时要从 sys.modules 找回模块
    spec.loader.exec_module(mod)
    return mod


cli = _load("layer_cli", APP / "cli.py")
adapter = _load("layer_adapter", APP / "adapter.py")

MANIFEST = """# 纽约建筑轮廓：Bayside 子集，字段清单

由 build.py 生成，手改会被覆盖。

## crs
kind: crs
几何类型：MultiPolygon 2 个。

## extent
kind: extent
经度：最小 -73.785002，最大 -73.765003。
纬度：最小 40.754998，最大 40.769992。
条数：2。

## feature_code
kind: field
字典名：FEATURE_CODE；形状文件名：FEAT_CODE；字典类型：number。
字典说明：Type of Building. 建筑类型。
数据：非空 2 条；不同取值 2 个；值为 0 的条数 0。
取值分布（前 5 个，按条数从多到少，同数按文字排序）：
- 2100：1
- 5110：1

## name
kind: field
字典名：NAME；形状文件名：NAME；字典类型：text。
字典说明：Building name.
数据：非空 0 条；不同取值 0 个；值为 0 的条数 0。
数据里的类型：（全部为空）。
取值分布（前 5 个，按条数从多到少，同数按文字排序）：
（没有非空值）
"""


@pytest.fixture
def manifest(tmp_path):
    path = tmp_path / "bayside.fields.md"
    path.write_text(MANIFEST, encoding="utf-8")
    return path


def test_fields_lists_only_field_units_with_titles(manifest, capsys):
    """列出字段单元（需求 6.1）：只列 kind 为 field 的单元，每个一行，ID 制表符 标题。"""
    assert cli.main(["--manifest", str(manifest), "fields"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "feature_code\tfeature_code（字典名 FEATURE_CODE）",
        "name\tname（字典名 NAME）",
    ]


def test_show_prints_the_body_of_one_unit(manifest, capsys):
    """显示单元（需求 6.1）：show 打印这一单元的正文，不含标题行。"""
    assert cli.main(["--manifest", str(manifest), "show", "extent"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("kind: extent\n经度：最小 -73.785002")
    assert "## extent" not in out


def test_show_of_a_missing_unit_is_exit_1(manifest, capsys):
    """显示单元：找不到的 ID 退出码 1，错误写到标准错误。"""
    assert cli.main(["--manifest", str(manifest), "show", "no-such-unit"]) == 1
    assert "没有单元 no-such-unit" in capsys.readouterr().err


def test_a_missing_manifest_is_exit_1(tmp_path, capsys):
    """读清单：文件不存在时退出码 1。"""
    assert cli.main(["--manifest", str(tmp_path / "none.md"), "fields"]) == 1
    assert "读不了清单" in capsys.readouterr().err


def test_a_manifest_section_without_a_kind_line_is_exit_1(tmp_path, capsys):
    """读清单：节的第一行不是 kind 行，退出码 1，不假装有单元。"""
    path = tmp_path / "bad.md"
    path.write_text("## feature_code\n字典名：X\n", encoding="utf-8")
    assert cli.main(["--manifest", str(path), "fields"]) == 1
    assert "清单格式不对" in capsys.readouterr().err


def test_cli_and_adapter_split_the_manifest_the_same_way():
    """一致（设计第 8 节）：命令行的切法和适配器的 split 得到相同的单元：ID、kind、标题和正文。"""
    data = MANIFEST.encode("utf-8")
    from_cli = [(u["id"], u["kind"], u["title"], u["body"]) for u in cli.parse(MANIFEST)]
    from_adapter = [(u.id, u.kind, u.title, u.text) for u in adapter.split(data, "bayside.fields.md")]
    assert from_cli == from_adapter


def test_running_the_cli_writes_nothing(manifest, capsys, tmp_path):
    """只读（设计第 8 节）：运行 fields 和 show 之后，清单的字节和目录里的文件都不变。"""
    before = (hashlib.sha256(manifest.read_bytes()).hexdigest(), sorted(p.name for p in tmp_path.iterdir()))
    assert cli.main(["--manifest", str(manifest), "fields"]) == 0
    assert cli.main(["--manifest", str(manifest), "show", "name"]) == 0
    after = (hashlib.sha256(manifest.read_bytes()).hexdigest(), sorted(p.name for p in tmp_path.iterdir()))
    assert before == after


def test_cli_does_not_import_refcov():
    """只读（设计第 8 节）：cli.py 不 import refcov，也不 import 适配器。"""
    tree = ast.parse((APP / "cli.py").read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.split(".")[0] in ("refcov", "adapter", "layer_adapter")]
