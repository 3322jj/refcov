"""端到端：合成视频 → detect → 登记 → 经 MCP 读全部镜头 → 检查达标；视频改了、清单改坏了、重新检测后会怎样
（镜头应用任务 4，需求 2、3、4、6.1）。要 ffmpeg，没有就跳过。
"""

import asyncio
import base64
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import shot_loader
from refcov import api
from refcov.sources import RegisterError, register
from refcov.store import Store
from shot_video import center_pixel, jpeg_width, make_video, needs_ffmpeg

pytestmark = needs_ffmpeg

cli = shot_loader.load_cli()
REPO = Path(__file__).resolve().parents[1]
IDS = ["shot-00-00-0", "shot-00-02-0", "shot-00-04-0"]


def state(store):
    return {p.relative_to(store.state_dir).as_posix(): p.read_bytes()
            for p in store.state_dir.rglob("*") if p.is_file()}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """临时仓库：适配器副本和配置、合成视频、检测、登记（用核心层的 register，等价于用户在终端运行登记命令）。"""
    shot_loader.install(tmp_path)
    make_video(tmp_path / "three.mp4")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["detect", "three.mp4"]) == 0
    store = Store(tmp_path)
    register(store, "three.shots.md", "vid", adapter="shot")
    return store


def mcp_call(root, calls):
    """经 stdio 子进程跑真正的 MCP 服务，依次调用 `calls`（[(工具, 参数)]），返回结果列表。
    子进程的当前目录是 pytest 的当前目录（不是被测仓库），适配器仍能找到仓库根目录。"""

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "refcov_mcp", "--root", str(root)],
                                       env=dict(os.environ, PYTHONPATH=str(REPO), PYTHONUNBUFFERED="1"),
                                       cwd=str(REPO))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return [await session.call_tool(name, args) for name, args in calls]

    return asyncio.run(asyncio.wait_for(run(), 120))


def test_register_gives_one_required_unit_per_shot(repo):
    entry = repo.read_sources()["sources"][0]
    assert entry["adapter"] == "shot" and [u["id"] for u in entry["units"]] == IDS
    assert all(u["kind"] == "shot" for u in entry["units"])
    res = api.check(repo)
    assert res["required"] == 3 and not res["pass"]
    assert len(repo.cache_dir.iterdir().__next__().read_bytes()) < 2000  # 缓存里只有那份小清单，没有视频


def test_read_all_shots_through_mcp_then_check_passes(repo):
    """经 MCP 读全部镜头：每次返回一段文字加一张 JPEG（文字最后一行是调用编号）；读取记录里图片张数之和等于镜头数；检查达标。"""
    results = mcp_call(repo.root, [("read_unit", {"source": "vid", "unit": u}) for u in IDS])
    for unit, res in zip(IDS, results):
        assert not res.isError, res.content
        assert [c.type for c in res.content] == ["text", "image"]
        assert res.content[0].text.startswith(f"{unit}: ") and "refcov-call: c-" in res.content[0].text.splitlines()[-1]
        jpeg = base64.b64decode(res.content[1].data)
        assert res.content[1].mimeType == "image/jpeg" and 0 < jpeg_width(jpeg) <= 960
    reads = [r for r in repo.records() if r["type"] == "read"]
    assert [r["unit"] for r in reads] == IDS and sum(r["images"] for r in reads) == 3
    assert all(r["text_units"] == 1 for r in reads)
    assert api.check(repo)["pass"] and repo.verify_chain().ok
    assert sum(b["images"] for b in api.report(repo, None)["by_session"]) == 3


def test_changed_video_is_refused_and_writes_nothing(repo):
    """需求 3.4：视频被换了，读取被拒绝，不返回内容，日志不变（经 MCP 和经 api 两条路）。"""
    api.read(repo, "vid", IDS[0])
    (repo.root / "three.mp4").write_bytes(b"a different file entirely" * 40)
    before = state(repo)
    with pytest.raises(api.ReadError, match="视频变了"):
        api.read(repo, "vid", IDS[1])
    res = mcp_call(repo.root, [("read_unit", {"source": "vid", "unit": IDS[2]})])[0]
    assert res.isError and "视频变了" in res.content[0].text and [c.type for c in res.content] == ["text"]
    assert state(repo) == before


def test_missing_video_is_refused(repo):
    (repo.root / "three.mp4").unlink()
    before = state(repo)
    with pytest.raises(api.ReadError, match="视频不在清单记的位置"):
        api.read(repo, "vid", IDS[0])
    assert state(repo) == before


def test_hand_broken_list_is_refused_at_registration(repo):
    """清单被手改坏（有空隙）：登记被拒绝，什么都不写（骨架需求 1.5）。"""
    text = (repo.root / "three.shots.md").read_text(encoding="utf-8")
    broken = text.replace("start: 2.0", "start: 2.1").replace("## shot-00-02-0", "## shot-00-02-1")
    (repo.root / "bad.shots.md").write_text(broken, encoding="utf-8")
    before = state(repo)
    with pytest.raises(RegisterError, match="适配器 shot 拆分失败.*空隙或重叠"):
        register(repo, "bad.shots.md", "bad", adapter="shot")
    assert state(repo) == before


def test_redetect_and_reregister_invalidate_old_reads(repo, monkeypatch):
    """需求 3.1、4.7：视频换了，重新检测、重新登记，所有镜头的校验值都变，旧读取记录全部失效，要重新读。"""
    for u in IDS:
        api.read(repo, "vid", u)
    assert api.check(repo)["pass"]
    make_video(repo.root / "three.mp4", colors=("blue", "red", "lime"))
    assert cli.main(["detect", "three.mp4"]) == 0
    res = register(repo, "three.shots.md", "vid", adapter="shot")
    assert res.written and res.changed
    assert [u["read"] for u in api.list_units(repo, "vid")] == [False, False, False]
    assert not api.check(repo)["pass"]
    first = api.read(repo, "vid", IDS[0])  # 重新读之后达标，而且读到的是新视频的画面（第一个镜头现在是蓝色）
    assert center_pixel(first.images[0].data)[2] > 200 > center_pixel(first.images[0].data)[0]
    for u in IDS[1:]:
        api.read(repo, "vid", u)
    assert api.check(repo)["pass"]


def test_same_video_moved_keeps_old_reads_valid(repo, monkeypatch):
    """视频内容没变（只是复制到别处、修改时间变了）：重新检测得到相同的校验值，旧读取记录仍然有效。"""
    for u in IDS:
        api.read(repo, "vid", u)
    before = [u["sha256"] for u in repo.read_sources()["sources"][0]["units"]]
    os.utime(repo.root / "three.mp4", ns=(1, 2))
    assert cli.main(["detect", "three.mp4"]) == 0
    res = register(repo, "three.shots.md", "vid", adapter="shot")
    assert [u["sha256"] for u in res.entry["units"]] == before
    assert api.check(repo)["pass"]


def test_write_gate_blocks_until_all_shots_are_read(repo):
    """需求 6.1：写剪辑方案前要读完全部镜头，由骨架的写文件关卡完成（没有新增关卡逻辑）：读 2 个还拦、只列还差的那个，读完放行。"""
    res = api.check_write(repo, "edit-plan.md", "sess_a")
    assert not res["allow"] and all(f"vid/{u}" in res["reason"] for u in IDS)
    api.read(repo, "vid", IDS[0])
    api.read(repo, "vid", IDS[2])
    res = api.check_write(repo, "edit-plan.md", "sess_a")
    assert not res["allow"] and f"vid/{IDS[1]}" in res["reason"] and f"vid/{IDS[0]}" not in res["reason"]
    api.read(repo, "vid", IDS[1])
    assert api.check_write(repo, "edit-plan.md", "sess_a")["allow"]


def test_relax_can_shrink_the_required_shots(repo):
    """需求 6.3：必看范围太大时用骨架的放宽项缩小（应用自己不放宽）。"""
    (repo.root / "refcov.toml").write_text(
        '[adapters]\nshot = "apps/shot-coverage/adapter.py"\n[relax]\nunits = ["vid/shot-00-02-0", "vid/shot-00-04-0"]\n',
        encoding="utf-8")
    assert api.check(repo)["required"] == 1
