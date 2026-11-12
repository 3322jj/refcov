"""RefCov 的 MCP 服务（设计 5，任务 5）：官方 SDK 的 FastMCP，stdio。只调用 `refcov.api`。

启动：`python -m refcov_mcp --root <仓库根目录>`。Kiro 起服务时工作目录不一定是仓库根目录
（docs/验证结果.md 第 6 项），所以根目录必须由参数给出。stdout 只走协议消息，其他输出都写 stderr。
现在有 list_units、read_unit、report 三个工具；check、request_token 在后面的任务里加。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from refcov import api
from refcov.store import Store

NAME = "refcov"  # Kiro 里的工具名是 mcp_refcov_<工具名>，接入层钩子按 ^mcp_refcov_ 匹配


def build(root: Path) -> FastMCP:
    store = Store(root)
    mcp = FastMCP(NAME, log_level="WARNING")

    # structured_output=False：只回一个文字块，不另附 structuredContent（任务 6 的钩子只看这段文字）
    @mcp.tool(structured_output=False)
    def list_units(source: str | None = None) -> str:
        """列出已登记参考源的单元：参考源/单元 ID、标题、类型、历史上是否看过。source 不填时列出全部参考源。"""
        try:
            units = api.list_units(store, source)
        except api.ReadError as e:
            raise ToolError(str(e)) from e
        lines = [f"{u['source']}/{u['id']}\t{u['title']}\t{u['kind']}\t{'看过' if u['read'] else '没看过'}"
                 for u in units]
        body = "\n".join(lines) if lines else "还没有登记任何参考源。"
        return f"{body}\n\n{api.HINT}"

    @mcp.tool(structured_output=False)
    def read_unit(source: str, unit: str) -> str:
        """读一个单元（source 是参考源 ID，unit 是单元 ID）。只有经这个工具读到的单元才算看过。"""
        try:
            return api.read(store, source, unit).text()
        except api.ReadError as e:
            raise ToolError(str(e)) from e

    @mcp.tool(structured_output=False)
    def report(format: str = "text") -> str:
        """覆盖率报告。format 为 text（默认）或 json。MCP 拿不到会话 ID，所以本会话一栏是"不可用"。"""
        if format not in ("text", "json"):
            raise ToolError("format 只能是 text 或 json")
        try:
            rep = api.report(store, None)
        except Exception as e:  # 配置文件坏了、清单读不了等
            raise ToolError(f"报告生成失败：{e}") from e
        if format == "json":
            return json.dumps(rep, ensure_ascii=False, indent=2) + f"\n\n{api.HINT}"
        return api.report_text(rep)

    return mcp


def main(argv=None) -> int:
    # stderr 强制 UTF-8：Windows 英文系统上默认代码页（如 cp1252）会把中文写成 \uXXXX（任务 8，Windows CI）。
    # 原地改同一个对象，argparse 的报错和 SDK 的日志（创建时绑定 sys.stderr）也跟着走 UTF-8。
    # stdout 不动：它走 MCP 协议，由 SDK 管。
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="refcov_mcp", description="RefCov MCP server (stdio).")
    parser.add_argument("--root", required=True, help="仓库根目录的路径（下面要有 .git）")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not (root / ".git").exists():
        print(f"refcov_mcp 启动失败：--root 要指向仓库根目录，{root} 下没有 .git", file=sys.stderr)
        return 1
    build(root).run("stdio")
    return 0
