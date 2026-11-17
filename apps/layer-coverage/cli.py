"""命令行（设计第 8 节）：列出字段单元，显示一个单元的正文。只读清单。

用法：
    python apps/layer-coverage/cli.py fields            列出字段单元：每个一行，ID 制表符 标题
    python apps/layer-coverage/cli.py show <单元 ID>    打印这个单元的正文
    加 --manifest <文件> 可以指定别的清单（默认是 bayside.fields.md）

不 import refcov，不写任何记录（读取记录只由 MCP 工具写）。切法和 adapter.split 一样，
tests/test_layer_cli.py 核对两者的结果相同。
退出码：0 成功；1 找不到单元、读不了清单或清单格式不对；2 命令行写错。
"""

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "bayside.fields.md"
TITLES = {"crs": "坐标系", "extent": "范围和数据来源"}
KINDS = ("field", "crs", "extent")


class ManifestError(Exception):
    """清单的格式不对。"""


def parse(text: str) -> list:
    """返回 [{id, kind, title, body}]，顺序和清单里一样。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sections = []
    for line in text.split("\n"):
        m = re.match(r"^## (.+)$", line)
        if m:
            sections.append((m.group(1).strip(), []))
        elif sections:
            sections[-1][1].append(line)
    units = []
    for unit_id, lines in sections:
        body = "\n".join(lines).strip("\n")
        m = re.match(r"^kind: (\w+)$", body.split("\n", 1)[0])
        if not m or m.group(1) not in KINDS:
            raise ManifestError(f"单元 {unit_id} 的第一行不是 kind 行")
        kind = m.group(1)
        if kind in TITLES:
            title = TITLES[kind]
        else:
            name = re.search(r"字典名：([^；\n]+)", body)
            title = f"{unit_id}（字典名 {name.group(1).strip()}）" if name else unit_id
        units.append({"id": unit_id, "kind": kind, "title": title, "body": body})
    return units


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="查看字段清单（只读）")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="清单文件")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fields", help="列出字段单元")
    show = sub.add_parser("show", help="显示一个单元的正文")
    show.add_argument("unit_id")
    args = parser.parse_args(argv)

    try:
        units = parse(Path(args.manifest).read_text(encoding="utf-8"))
    except OSError as e:
        print(f"错误：读不了清单：{e}", file=sys.stderr)
        return 1
    except (UnicodeDecodeError, ManifestError) as e:
        print(f"错误：清单格式不对：{e}", file=sys.stderr)
        return 1

    if args.command == "fields":
        for unit in units:
            if unit["kind"] == "field":
                print(f"{unit['id']}\t{unit['title']}")
        return 0
    for unit in units:
        if unit["id"] == args.unit_id:
            print(unit["body"])
            return 0
    print(f"错误：没有单元 {args.unit_id}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
