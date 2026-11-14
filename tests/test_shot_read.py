"""镜头适配器的 `read`：找视频、核对视频没变、取关键帧（镜头应用任务 2，需求 2.1–2.6、3.2–3.4；设计 3.2）。

前一半用假视频（普通字节）测核对分支，不用 ffmpeg；后一半用 ffmpeg 合成的视频，没有 ffmpeg 就跳过。
"""

import dataclasses
import hashlib
import os

import pytest

import shot_loader
from refcov.sources import Image
from shot_video import center_pixel, jpeg_width, make_video, needs_ffmpeg

SHOTS = [(0, 20), (20, 40), (40, 60)]


def build_list(adapter, video_file, root, shots=SHOTS, **kw):
    """为 `video_file`（在 root 下）写一份清单文字，文件头的大小、修改时间、SHA-256 都取自这个文件；
    `kw` 覆盖文件头的字段（例如 `video="..."`）。"""
    st = video_file.stat()
    h = adapter.Header(video_file.relative_to(root).as_posix(), hashlib.sha256(video_file.read_bytes()).hexdigest(),
                       st.st_size, st.st_mtime_ns, shots[-1][1], 0.25, 0.5)
    return adapter.format_list(dataclasses.replace(h, **kw), shots).encode("utf-8")


@pytest.fixture
def repo(tmp_path):
    adapter = shot_loader.install(tmp_path)
    video = tmp_path / "reference.mp4"
    video.write_bytes(b"not a real video" * 100)
    return tmp_path, adapter, video


@pytest.fixture
def frames(monkeypatch):
    """换掉取帧：返回固定的假 JPEG，并记下被取的时间点。"""
    calls = []

    def fake(adapter):
        monkeypatch.setattr(adapter, "extract_frame", lambda path, seconds: (calls.append((path, seconds)),
                                                                            b"\xff\xd8fake-jpeg")[1])
        return calls

    return fake


def no_hash(monkeypatch, adapter):
    def boom(path):
        raise AssertionError("不该重算 SHA-256")

    monkeypatch.setattr(adapter, "sha256_file", boom)


def test_read_returns_text_and_one_keyframe_from_the_middle(repo, frames):
    """需求 2.1、2.2：返回一段文字和一张关键帧；取的是镜头中点；文字只写事实，不描述画面。"""
    root, adapter, video = repo
    calls = frames(adapter)
    parts = adapter.read(build_list(adapter, video, root), "reference", "shot-00-02-0")
    assert len(parts) == 2 and isinstance(parts[0], str) and isinstance(parts[1], Image)
    assert parts[1].mime == "image/jpeg" and parts[1].data == b"\xff\xd8fake-jpeg"
    assert calls == [(video, 3.0)]
    text = parts[0]
    assert text.startswith("shot-00-02-0: 2.0–4.0 s (2.0 s), shot 2 of 3.")
    assert "middle of the shot (3.0 s)" in text and "does not show text or motion" in text


def test_unchanged_size_and_mtime_pass_without_hashing(repo, frames, monkeypatch):
    """需求 3.4：大小和修改时间都和文件头一致，通过，不算 SHA-256。"""
    root, adapter, video = repo
    frames(adapter)
    data = build_list(adapter, video, root)
    no_hash(monkeypatch, adapter)
    assert adapter.read(data, "reference", "shot-00-00-0")


def test_content_changed_is_refused(repo, frames):
    """视频内容变了（大小也变）：重算 SHA-256，对不上，拒绝，提示重新检测和登记。"""
    root, adapter, video = repo
    frames(adapter)
    data = build_list(adapter, video, root)
    video.write_bytes(b"another video" * 50)
    with pytest.raises(adapter.ShotError, match="视频变了.*重新检测并登记"):
        adapter.read(data, "reference", "shot-00-00-0")


def test_same_size_but_new_mtime_and_new_content_is_refused(repo, frames):
    """内容变了、大小没变、修改时间变了：不一致就重算，对不上，拒绝。"""
    root, adapter, video = repo
    frames(adapter)
    data = build_list(adapter, video, root)
    size = video.stat().st_size
    video.write_bytes(b"x" * size)
    os.utime(video, ns=(1, 2))
    with pytest.raises(adapter.ShotError, match="视频变了"):
        adapter.read(data, "reference", "shot-00-00-0")


def test_only_mtime_changed_passes_after_rehash_and_is_remembered(repo, frames, monkeypatch):
    """只是修改时间变了（例如复制过）：重算 SHA-256，一致，放行；同一个进程里下一次读取不再重算。"""
    root, adapter, video = repo
    frames(adapter)
    data = build_list(adapter, video, root)
    os.utime(video, ns=(1, 2))
    assert adapter.read(data, "reference", "shot-00-00-0")
    no_hash(monkeypatch, adapter)
    assert adapter.read(data, "reference", "shot-00-02-0")


def test_known_limitation_same_size_same_mtime_new_content_is_not_noticed(repo, frames):
    """已知局限（README 写明）：大小和修改时间都没变但内容变了的视频，核对不出来。"""
    root, adapter, video = repo
    frames(adapter)
    data = build_list(adapter, video, root)
    st = video.stat()
    video.write_bytes(b"y" * st.st_size)
    os.utime(video, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert adapter.read(data, "reference", "shot-00-00-0")


def test_missing_or_non_file_video_is_refused(repo, frames):
    root, adapter, video = repo
    frames(adapter)
    data = build_list(adapter, video, root)
    video.unlink()
    with pytest.raises(adapter.ShotError, match="视频不在清单记的位置.*重新检测并登记"):
        adapter.read(data, "reference", "shot-00-00-0")
    video.mkdir()  # 同名目录不是文件
    with pytest.raises(adapter.ShotError, match="视频不在清单记的位置"):
        adapter.read(data, "reference", "shot-00-00-0")


def test_url_like_video_path_is_refused(repo, frames):
    """不接受网址或 ffmpeg 的特殊输入：只认存在的普通文件（设计 6）。"""
    root, adapter, video = repo
    frames(adapter)
    for odd in ("http://example.com/x.mp4", "concat:a.mp4|b.mp4", "pipe:0"):
        data = build_list(adapter, video, root, video=odd)
        with pytest.raises(adapter.ShotError, match="视频不在清单记的位置"):
            adapter.read(data, "reference", "shot-00-00-0")


def test_absolute_video_path_outside_the_repo_is_allowed(repo, frames, tmp_path_factory):
    """视频在仓库外时清单里写绝对路径（需求 1.2）。"""
    root, adapter, video = repo
    calls = frames(adapter)
    outside = tmp_path_factory.mktemp("outside") / "far.mp4"
    outside.write_bytes(b"far away video")
    st = outside.stat()
    h = adapter.Header(outside.as_posix(), hashlib.sha256(outside.read_bytes()).hexdigest(), st.st_size,
                       st.st_mtime_ns, 60, 0.25, 0.5)
    assert adapter.read(adapter.format_list(h, SHOTS).encode(), "far", "shot-00-04-0")
    assert calls[-1][0] == outside


def test_unknown_unit_raises_key_error(repo, frames):
    root, adapter, video = repo
    frames(adapter)
    with pytest.raises(KeyError):
        adapter.read(build_list(adapter, video, root), "reference", "shot-09-09-9")


def test_repo_root_is_found_from_the_adapter_file_not_the_current_directory(repo, tmp_path_factory, monkeypatch):
    """适配器从自己的文件位置往上找含 .git 的目录；当前目录在别处也不影响（MCP 服务的当前目录不一定是仓库根目录）。"""
    root, adapter, video = repo
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))
    assert adapter.repo_root() == root.resolve()


def test_missing_ffmpeg_is_reported(repo, monkeypatch):
    root, adapter, video = repo
    monkeypatch.setattr(adapter.shutil, "which", lambda name: None)
    with pytest.raises(adapter.ShotError, match="找不到 ffmpeg"):
        adapter.extract_frame(video, 1.0)


class FakeRun:
    """代替 subprocess.run：记下命令和参数，返回自己（带 returncode、stdout、stderr）。"""

    def __init__(self, returncode=1, stdout=b"", stderr=b""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    def __call__(self, cmd, **kw):
        self.cmd, self.kw = cmd, kw
        return self


def test_extract_frame_command_and_failures(repo, monkeypatch):
    """取帧命令：`-nostdin`、标准输入接空、有超时；失败时错误里带 stderr 的前 300 个字符，输出不是 JPEG 也算失败。"""
    root, adapter, video = repo
    monkeypatch.setattr(adapter.shutil, "which", lambda name: "ffmpeg")
    fake = FakeRun(returncode=0, stdout=b"\xff\xd8jpeg-bytes")
    monkeypatch.setattr(adapter.subprocess, "run", fake)
    assert adapter.extract_frame(video, 3.0) == b"\xff\xd8jpeg-bytes"
    assert "-nostdin" in fake.cmd and fake.cmd.index("-ss") < fake.cmd.index("-i")
    assert fake.kw["stdin"] is adapter.subprocess.DEVNULL and fake.kw["timeout"] == adapter.FRAME_TIMEOUT
    assert fake.kw["capture_output"] is True
    monkeypatch.setattr(adapter.subprocess, "run", FakeRun(returncode=1, stderr=("坏" * 1000).encode("utf-8")))
    with pytest.raises(adapter.ShotError) as e:
        adapter.extract_frame(video, 3.0)
    assert "退出码 1" in str(e.value) and len(str(e.value)) < 400
    monkeypatch.setattr(adapter.subprocess, "run", FakeRun(returncode=0, stdout=b"not a jpeg"))
    with pytest.raises(adapter.ShotError, match="取帧失败"):
        adapter.extract_frame(video, 3.0)


def test_extract_frame_timeout_is_reported(repo, monkeypatch):
    root, adapter, video = repo
    monkeypatch.setattr(adapter.shutil, "which", lambda name: "ffmpeg")

    def slow(cmd, **kw):
        raise adapter.subprocess.TimeoutExpired(cmd, kw["timeout"])

    monkeypatch.setattr(adapter.subprocess, "run", slow)
    with pytest.raises(adapter.ShotError, match="超时"):
        adapter.extract_frame(video, 3.0)


# ---- 合成视频（要 ffmpeg）----

@pytest.fixture
def synthetic(tmp_path):
    adapter = shot_loader.install(tmp_path)
    video = make_video(tmp_path / "three.mp4", seconds=2, size="1280x720")
    return tmp_path, adapter, video


@needs_ffmpeg
def test_real_frames_come_from_the_middle_of_each_shot(synthetic):
    """合成的红、绿、蓝各 2 秒：三个镜头各读一张，是 JPEG、宽度不超过 960，正中间像素的颜色和镜头一致。"""
    root, adapter, video = synthetic
    data = build_list(adapter, video, root)
    for sid, color in (("shot-00-00-0", (255, 0, 0)), ("shot-00-02-0", (0, 255, 0)), ("shot-00-04-0", (0, 0, 255))):
        text, image = adapter.read(data, "three", sid)
        assert image.mime == "image/jpeg" and image.data.startswith(b"\xff\xd8") and image.data.endswith(b"\xff\xd9")
        assert 0 < jpeg_width(image.data) <= 960
        px = center_pixel(image.data)
        assert all(abs(a - b) < 40 for a, b in zip(px, color)), (sid, px)


@needs_ffmpeg
def test_small_video_is_not_scaled_up(tmp_path):
    adapter = shot_loader.install(tmp_path)
    video = make_video(tmp_path / "small.mp4", seconds=2, size="320x240")
    assert jpeg_width(adapter.extract_frame(video, 1.0)) == 320


@needs_ffmpeg
def test_extraction_failure_on_a_broken_file_is_reported(tmp_path):
    adapter = shot_loader.install(tmp_path)
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"this is not a video file at all" * 10)
    with pytest.raises(adapter.ShotError, match="取帧失败"):
        adapter.extract_frame(broken, 1.0)

