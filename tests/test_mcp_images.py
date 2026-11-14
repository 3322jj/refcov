"""MCP 的 read_unit 把图片一起送出去（镜头应用需求第二部分 C2，骨架需求 2.1、4.1）。

经 stdio 子进程、官方 SDK 客户端；服务用 tests/image_server_launcher.py 启动（假适配器返回一段文字加两张图）。
"""

import asyncio
import base64
import os
import shutil
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from refcov import api
from refcov.sources import register
from refcov.store import Store

SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"
LAUNCHER = Path(__file__).parent / "image_server_launcher.py"
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copyfile(SAMPLE, tmp_path / "docs" / "sample-hooks.md")
    register(Store(tmp_path), "docs/sample-hooks.md", "sample")
    return tmp_path


def call(repo, tool, args, error=False):
    async def run():
        extra = ["--error"] if error else []
        params = StdioServerParameters(command=sys.executable,
                                       args=[str(LAUNCHER), *extra, "--root", str(repo)],
                                       env=dict(os.environ, PYTHONPATH=str(REPO), PYTHONUNBUFFERED="1"))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool, args)

    return asyncio.run(asyncio.wait_for(run(), 60))


def test_read_unit_returns_text_then_images(repo):
    """文字块在前，其后是图片块（类型、MIME、字节原样）；`refcov-call:` 是文字块的最后一行；记录写 images=2。"""
    got = call(repo, "read_unit", {"source": "sample", "unit": "Hooks"})
    assert not got.isError and got.structuredContent is None
    assert [c.type for c in got.content] == ["text", "image", "image"]
    text = got.content[0].text
    assert text.startswith("镜头 Hooks\n") and text.splitlines()[-1] == "refcov-call: c-2"
    assert [c.mimeType for c in got.content[1:]] == ["image/png", "image/jpeg"]
    assert base64.b64decode(got.content[1].data) == b"\x89PNG\r\n\x1a\nfake-png-bytes\x00\xff"
    assert base64.b64decode(got.content[2].data) == b"\xff\xd8\xfffake-jpeg-bytes\x00"
    assert api.call_from_text(text) == "c-2"
    rec = Store(repo).records()[-1]
    assert rec["type"] == "read" and rec["call"] == "c-2" and rec["text_units"] == 1 and rec["images"] == 2
    assert Store(repo).verify_chain().ok


def test_adapter_error_is_a_tool_error_without_record(repo):
    """适配器的 read 抛异常：工具返回错误、没有图片、日志不多一行。"""
    before = Store(repo).log_path.read_bytes()
    got = call(repo, "read_unit", {"source": "sample", "unit": "Hooks"}, error=True)
    assert got.isError and [c.type for c in got.content] == ["text"]
    assert "视频变了" in got.content[0].text
    assert Store(repo).log_path.read_bytes() == before
