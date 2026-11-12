"""命令行 `refcov`：`add`（任务 4）、`report`（任务 7）、`check-spec`（任务 10）、`check`（任务 11）。

仓库根目录取当前目录，要在仓库根目录下运行：当前目录下没有 `.git` 时报错，什么都不写。
"""

import argparse
import json
import sys
from pathlib import Path

from refcov import __version__, api, citations

# 只能由用户在终端跑的子命令（设计 6）：会往日志追加记录、写配置、建立或清空日志的子命令都放进来。
# 接入层的保护检查不能 import 核心层，integrations/kiro/hook.py 里抄了一份，tests/test_protect.py 检查两份一致。
USER_ONLY = ("add", "confirm")
from refcov.sources import RegisterError, register
from refcov.store import Store, StoreError


def _match_console_encoding() -> None:
    """Windows 上输出被捕获或重定向时，改用控制台代码页编码，编不出的字符转义。

    pwsh 按控制台代码页（例如 936）解读程序输出；Python 在 UTF-8 模式下往管道写 UTF-8，
    中文会乱码。直接输出到控制台时 Python 走宽字符接口，本来就不乱码，不动。
    """
    if sys.platform != "win32":
        return
    import ctypes

    cp = ctypes.windll.kernel32.GetConsoleOutputCP()
    for stream, original in ((sys.stdout, sys.__stdout__), (sys.stderr, sys.__stderr__)):
        if cp and stream is original and stream is not None and not stream.isatty():
            stream.reconfigure(encoding=f"cp{cp}", errors="backslashreplace")


def _repo_root() -> Path | None:
    """当前目录下有 `.git`（目录，或 worktree 里的文件）时返回当前目录，否则返回 None。

    不往上找：在子目录里跑时报错，免得悄悄在子目录里建一个 `.refcov/`。
    """
    cwd = Path.cwd()
    return cwd if (cwd / ".git").exists() else None


def _report(args) -> int:
    root = _repo_root()
    if root is None:
        print(f"报告失败：请在仓库根目录运行 refcov（{Path.cwd()} 下没有 .git）", file=sys.stderr)
        return 1
    try:
        rep = api.report(Store(root), args.session)
    except (StoreError, OSError, ValueError, api.ReadError, api.CheckError) as e:
        print(f"报告失败：{e}", file=sys.stderr)
        return 1
    print(json.dumps(rep, ensure_ascii=False, indent=2) if args.json else api.report_text(rep))
    return 0


def _add(args) -> int:
    root = _repo_root()
    if root is None:
        print(f"登记失败：请在仓库根目录运行 refcov（{Path.cwd()} 下没有 .git）", file=sys.stderr)
        return 1
    try:
        result = register(Store(root), args.origin, args.source_id)
    except (RegisterError, StoreError, OSError) as e:
        print(f"登记失败：{e}", file=sys.stderr)
        return 1
    entry = result.entry
    if not result.written:
        print(f"内容没变，未改动：{entry['id']}（{entry['origin']}）")
        return 0
    if not result.changed:
        print(f"已更新 {entry['id']} 的来源：{entry['origin']}。内容没变，单元不变")
        return 0
    print(f"已登记 {entry['id']}：{len(entry['units'])} 个单元（{entry['origin']}）")
    for u in entry["units"]:
        title = "" if u["title"] == u["id"] else f"  标题：{u['title']}"
        print(f"  {u['id']}  {u['chars']} 字{title}")
    return 0


def _check(args) -> int:
    """退出码：达标 0，不达标 1，出错 2（用户 2026-11-12 定）。豁免路径算达标。"""
    root = _repo_root()
    if root is None:
        print(f"检查失败：请在仓库根目录运行 refcov（{Path.cwd()} 下没有 .git）", file=sys.stderr)
        return 2
    try:
        res = api.check(Store(root), args.path)
    except (StoreError, OSError, ValueError, api.ReadError, api.CheckError) as e:
        print(f"检查失败：{e}", file=sys.stderr)
        return 2
    print(api.check_text(res))
    return 0 if res["pass"] else 1


def _check_spec(args) -> int:
    root = _repo_root()
    if root is None:
        print(f"检查失败：请在仓库根目录运行 refcov（{Path.cwd()} 下没有 .git）", file=sys.stderr)
        return 1
    try:
        text = (root / args.doc).read_text(encoding="utf-8-sig")
        result = citations.check_requirements(text, citations.known_units(Store(root).read_sources()))
    except (StoreError, OSError, UnicodeDecodeError, ValueError) as e:
        print(f"检查失败：{e}", file=sys.stderr)
        return 1
    print(f"出处检查：{args.doc}，{len(result.requirements)} 条需求")
    print(f"幻影需求 {len(result.phantom)} 条：{'、'.join(result.phantom) or '无'}")
    print(f"无效引用 {len(result.invalid)} 条" + ("：" if result.invalid else "：无"))
    for req, ref in result.invalid:
        print(f"  需求 {req}：{ref}")
    print(f"未转换 {len(result.unconverted)} 条：{'、'.join(result.unconverted) or '无'}")
    print(f"被引用的单元 {len(result.cited)} 个" + ("：" if result.cited else "：无"))
    for ref in result.cited:
        print(f"  {ref}")
    return 0


def main(argv=None) -> int:
    _match_console_encoding()
    parser = argparse.ArgumentParser(prog="refcov", description="Coverage for reference material.")
    parser.add_argument("--version", action="version", version=f"refcov {__version__}")
    sub = parser.add_subparsers(dest="command")
    add = sub.add_parser("add", help="登记或重新登记一个参考源（本地 Markdown 文件或网址）。只能由用户运行")
    add.add_argument("origin", help="本地文件路径（相对当前目录，要在仓库里）或网址")
    add.add_argument("--id", required=True, dest="source_id", help="参考源 ID：小写字母、数字、短横线")
    rep = sub.add_parser("report", help="覆盖率报告（只读，不写任何文件）")
    rep.add_argument("--json", action="store_true", help="输出 JSON")
    rep.add_argument("--session", help="会话 ID；不给时本会话一栏为“不可用”")
    ck = sub.add_parser("check", help="是否达标：还差的必看单元、幻影需求和无效引用（只读）。退出码 0 达标、1 不达标、2 出错")
    ck.add_argument("path", nargs="?", help="目标路径（相对仓库根目录）；不给时按全部参考源")
    chk = sub.add_parser("check-spec", help="出处检查：列出幻影需求、无效引用、未转换、被引用的单元（只读）")
    chk.add_argument("doc", help="需求文档路径（相对仓库根目录）")
    args = parser.parse_args(argv)
    if args.command == "add":
        return _add(args)
    if args.command == "report":
        return _report(args)
    if args.command == "check":
        return _check(args)
    if args.command == "check-spec":
        return _check_spec(args)
    parser.print_help()
    return 0
