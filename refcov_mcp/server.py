"""RefCov 的 MCP 服务（设计 5，任务 5）：官方 SDK 的 FastMCP，stdio。只调用 `refcov.api`。

启动：`python -m refcov_mcp --root <仓库根目录>`。Kiro 起服务时工作目录不一定是仓库根目录
（docs/验证结果.md 第 6 项），所以根目录必须由参数给出。stdout 只走协议消息，其他输出都写 stderr。
现在有 list_units、read_unit、check、report 四个工具；request_token 在任务 19（可选）里加。
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ImageContent, TextContent

from refcov import api
from refcov.store import Store

NAME = "refcov"
CHECK_FIRST = 20  # check 只列前 20 个还差的单元，另写总数（设计 5）


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
    def read_unit(source: str, unit: str) -> str | list[TextContent | ImageContent]:
        """读一个单元（source 是参考源 ID，unit 是单元 ID）。只有经这个工具读到的单元才算看过。
        有图片的单元（例如视频镜头的关键帧）会在文字后面附上图片。"""
        try:
            res = api.read(store, source, unit)
        except api.ReadError as e:
            raise ToolError(str(e)) from e
        if not res.images:
            return res.text()  # 没有图片：和以前逐字相同，只有一个文字块
        # 文字块在前，`refcov-call:` 是它的最后一行（钩子只认这一行，设计 5）；图片块在后
        blocks: list[TextContent | ImageContent] = [TextContent(type="text", text=res.text())]
        blocks.extend(ImageContent(type="image", data=base64.b64encode(im.data).decode("ascii"),
                                   mimeType=im.mime) for im in res.images)
        return blocks

    @mcp.tool(structured_output=False)
    def check(path: str | None = None) -> str:
        """是否达标：还差的必看单元（前 20 个和总数），以及幻影需求和无效引用。path 是目标文件路径
        （相对仓库根目录），不填时按全部参考源。达标不分会话，按历史上所有有效读取算。"""
        try:
            res = api.check(store, path)
        except Exception as e:  # 配置文件坏了、需求文档读不了等
            raise ToolError(f"检查失败：{e}") from e
        return api.check_text(res, limit=CHECK_FIRST)

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
