"""MCP 服务（任务 5，设计 5）：stdio 子进程，官方 SDK 客户端；Kiro 的 server/discover 握手。不连外网。"""

import asyncio
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from refcov import api
from refcov.sources import register
from refcov.store import Store

SAMPLE = Path(__file__).parent / "data" / "sample-hooks.md"
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copyfile(SAMPLE, tmp_path / "docs" / "sample-hooks.md")
    register(Store(tmp_path), "docs/sample-hooks.md", "sample")
    return tmp_path


def _env():
    return dict(os.environ, PYTHONPATH=str(REPO), PYTHONUNBUFFERED="1")


def test_sdk_client_list_and_read_over_stdio(repo):
    """SDK 自带的客户端经 stdio 子进程跑通 list_units、read_unit；只回一个文字块，最后一行是调用编号。"""

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "refcov_mcp", "--root", str(repo)],
                                       env=_env())
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = await session.list_tools()
                listed = await session.call_tool("list_units", {"source": "sample"})
                got = await session.call_tool("read_unit", {"source": "sample", "unit": "匹配-工具名"})
                missing = await session.call_tool("read_unit", {"source": "sample", "unit": "退出"})
                rep_text = await session.call_tool("report", {})
                rep_json = await session.call_tool("report", {"format": "json"})
                return init, tools, listed, got, missing, rep_text, rep_json

    init, tools, listed, got, missing, rep_text, rep_json = asyncio.run(asyncio.wait_for(run(), 60))
    assert init.serverInfo.name == "refcov"
    assert {t.name for t in tools.tools} == {"list_units", "read_unit", "report"}
    # report：本会话一栏"不可用"，只有一个文字块，最后一行不是 refcov-call（钩子会静默跳过）
    assert not rep_text.isError and len(rep_text.content) == 1
    assert "本会话 不可用" in rep_text.content[0].text
    assert api.call_from_text(rep_text.content[0].text) is None
    body = json.loads(rep_json.content[0].text.rsplit("\n\n", 1)[0])
    assert body["session"] is None and body["session_available"] is False
    assert body["sources"][0]["read_session"] is None and body["sources"][0]["read_history"] == 1
    assert not listed.isError and len(listed.content) == 1
    assert "sample/匹配-工具名\t匹配 [工具名]\tsection\t没看过" in listed.content[0].text
    assert listed.content[0].text.endswith(api.HINT)

    assert not got.isError
    assert len(got.content) == 1 and got.content[0].type == "text"
    assert got.structuredContent is None
    text = got.content[0].text
    # 正文本身以空行结尾（下一个标题前的空行），后面再空一行接提示
    assert text == f"\n写精确工具名。\n\n\n{api.HINT}\nrefcov-call: c-2"

    assert missing.isError and "最接近的 3 个" in missing.content[0].text
    recs = Store(repo).records()
    assert [r["type"] for r in recs] == ["register", "read"]
    assert recs[-1]["call"] == "c-2" and recs[-1]["unit"] == "匹配-工具名"
    assert Store(repo).verify_chain().ok


class _Proc:
    """逐行收发 JSON-RPC 的子进程，用来模拟 Kiro 的握手顺序。"""

    def __init__(self, root):
        self.p = subprocess.Popen([sys.executable, "-m", "refcov_mcp", "--root", str(root)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=_env())
        self.lines = queue.Queue()
        self.raw_stdout = []
        self.stderr = []
        threading.Thread(target=self._pump, daemon=True).start()
        # stderr 也要有人读，否则 SDK 的长警告写满管道会把服务卡住
        threading.Thread(target=lambda: self.stderr.extend(self.p.stderr), daemon=True).start()

    def _pump(self):
        for line in self.p.stdout:
            self.raw_stdout.append(line)
            self.lines.put(line)

    def send(self, msg):
        self.p.stdin.write(json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n")
        self.p.stdin.flush()

    def recv(self, timeout=30):
        return json.loads(self.lines.get(timeout=timeout))

    def close(self):
        """关 stdin，等服务自己退出，返回退出码。"""
        self.p.stdin.close()
        try:
            return self.p.wait(timeout=30)
        finally:
            if self.p.poll() is None:
                self.p.kill()


def test_server_discover_then_initialize_on_same_connection(repo):
    """Kiro 1.4.121 先发 server/discover（验证结果第 6 项）：服务回 JSON-RPC 错误、不崩、不断开，之后照常 initialize。

    实测 SDK 1.28.1 回的是 -32602（Invalid request parameters），不是 -32601（方法不存在）。
    这里只要求是同一个 id 的错误响应；Kiro 认不认这个错误码，要在 Kiro 里实测。
    """
    s = _Proc(repo)
    try:
        s.send({"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}})
        err = s.recv()
        assert err["id"] == 1 and "result" not in err
        assert err["error"]["code"] in (-32601, -32602)
        s.send({"jsonrpc": "2.0", "id": 2, "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                           "clientInfo": {"name": "kiro", "version": "0.0.0"}}})
        init = s.recv()
        assert init["id"] == 2 and init["result"]["serverInfo"]["name"] == "refcov"
        s.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        s.send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "read_unit", "arguments": {"source": "sample", "unit": "Hooks"}}})
        call = s.recv()
        assert call["id"] == 3 and call["result"]["isError"] is False
        assert call["result"]["content"][0]["text"].splitlines()[-1] == "refcov-call: c-2"
    finally:
        code = s.close()
    assert code == 0


def test_stdout_carries_only_protocol_messages(repo):
    """stdout 只走协议消息：每一行都能按 JSON-RPC 解析。SDK 的警告（例如 server/discover 校验失败）在 stderr。"""
    s = _Proc(repo)
    try:
        s.send({"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}})
        s.send({"jsonrpc": "2.0", "id": 2, "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                           "clientInfo": {"name": "t", "version": "0"}}})
        s.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        s.send({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        assert sorted(s.recv()["id"] for _ in range(3)) == [1, 2, 3]
    finally:
        code = s.close()
    assert code == 0
    out = [json.loads(line) for line in s.raw_stdout if line.strip()]
    assert len(out) == 3 and all(m["jsonrpc"] == "2.0" for m in out)
    assert b"server/discover" in b"".join(s.stderr)


@pytest.mark.parametrize("make", ["missing", "no-git"])
def test_root_must_be_repo_root(tmp_path, make):
    """--root 下没有 .git：启动就报错退出，原因按 UTF-8 写 stderr（任何代码页下都是），stdout 为空。"""
    root = tmp_path / "x" if make == "missing" else tmp_path
    proc = subprocess.run([sys.executable, "-m", "refcov_mcp", "--root", str(root)], input=b"",
                          capture_output=True, env=_env(), timeout=60)
    assert proc.returncode == 1 and proc.stdout == b""
    assert "没有 .git" in proc.stderr.decode("utf-8")
