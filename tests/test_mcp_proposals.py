"""MCP 的提议和执行（设计第 3–4 节，需求 6.4）：stdio 子进程，官方 SDK 客户端，一次提议到执行的往返。

第二次执行同一份提议必须被拒（工具报错，清单不变）。不连外网。
"""

import asyncio
import os
import re
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from refcov import api
from refcov.sources import content_sha256
from refcov.store import Store

REPO = Path(__file__).resolve().parents[1]
GUIDE = "# Alpha\n\nbody one\n\n# Beta\n\nbody two\n"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text(GUIDE, encoding="utf-8")
    return tmp_path


def _env():
    return dict(os.environ, PYTHONPATH=str(REPO), PYTHONUNBUFFERED="1")


def test_propose_then_apply_over_stdio_and_the_second_apply_is_refused(repo):
    sha = content_sha256(GUIDE)
    files = [{"path": "docs/guide.md", "source_id": "guide"}]
    args = {"proposal": None, "files": [{"path": "docs/guide.md", "sha256": sha, "source_id": "guide"}]}

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "refcov_mcp", "--root", str(repo)],
                                       env=_env())
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                prop = await session.call_tool("propose_sources", {"files": files})
                pid = re.search(r"提议 (p-[0-9a-f]{8})", prop.content[0].text).group(1)
                args["proposal"] = pid
                applied = await session.call_tool("apply_proposal", args)
                again = await session.call_tool("apply_proposal", args)
                return tools, prop, applied, again

    tools, prop, applied, again = asyncio.run(asyncio.wait_for(run(), 60))
    assert {"propose_sources", "apply_proposal"} <= {t.name for t in tools.tools}
    assert not prop.isError and "apply_proposal" in prop.content[0].text
    assert api.call_from_text(prop.content[0].text) is None  # 提议不是读取，没有调用编号
    assert not applied.isError
    assert api.call_from_text(applied.content[0].text) is not None
    assert again.isError and "已经执行过" in again.content[0].text
    assert [s["id"] for s in Store(repo).read_sources()["sources"]] == ["guide"]
