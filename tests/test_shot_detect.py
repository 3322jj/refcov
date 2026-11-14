"""`detect` 命令（镜头应用任务 3，需求 1.1、1.2、1.5、1.7、4.4–4.6；设计 4）。"""

import hashlib

import pytest

import shot_loader
from shot_video import make_video, needs_ffmpeg

cli = shot_loader.load_cli()
adapter = shot_loader.load()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def parse(path):
    return adapter.parse_list(path.read_text(encoding="utf-8"))


@needs_ffmpeg
def test_detect_three_colour_video(repo, capsys):
    """合成的红、绿、蓝各 2 秒：检测出 2 个切点、3 个镜头 [0,2]、[2,4]、[4,6]；清单在视频旁边，文件头取自视频文件。"""
    video = make_video(repo / "three.mp4")
    assert cli.main(["detect", "three.mp4"]) == 0
    out = repo / "three.shots.md"
    header, shots = parse(out)
    assert shots == [(0, 20), (20, 40), (40, 60)]
    st = video.stat()
    assert header.video == "three.mp4" and header.size == st.st_size and header.mtime_ns == st.st_mtime_ns
    assert header.sha256 == hashlib.sha256(video.read_bytes()).hexdigest()
    assert header.duration_t == 60 and header.threshold == 0.25 and header.min_shot == 0.5 and header.scale is None
    text = capsys.readouterr().out
    assert "3 个镜头" in text and "three.shots.md" in text and "--adapter shot" in text
    assert "不太正常" not in text
    assert not list(repo.glob("*.tmp"))


@needs_ffmpeg
def test_detect_out_subdirectory_and_video_path_override(repo):
    """`--out` 指定清单位置（要在仓库里）；`--video-path` 只改写进清单的路径，文件头的大小、修改时间、SHA-256 仍取自真实视频。"""
    video = make_video(repo / "three.mp4")
    assert cli.main(["detect", "three.mp4", "--out", "lists/a.shots.md", "--video-path", "reference.mp4"]) == 0
    header, shots = parse(repo / "lists" / "a.shots.md")
    assert header.video == "reference.mp4" and len(shots) == 3
    assert header.sha256 == hashlib.sha256(video.read_bytes()).hexdigest()


@needs_ffmpeg
def test_detect_video_outside_the_repo_writes_absolute_path_and_list_at_root(repo, tmp_path_factory):
    """需求 1.2、设计 4 第 6 步：视频在仓库外时，清单放在仓库根目录，视频路径写绝对路径。"""
    outside = make_video(tmp_path_factory.mktemp("elsewhere") / "far.mp4")
    assert cli.main(["detect", str(outside)]) == 0
    header, shots = parse(repo / "far.shots.md")
    assert header.video == outside.resolve().as_posix() and len(shots) == 3


@needs_ffmpeg
def test_detect_in_a_subfolder_puts_the_list_next_to_the_video(repo):
    (repo / "media").mkdir()
    make_video(repo / "media" / "clip.mp4")
    assert cli.main(["detect", "media/clip.mp4"]) == 0
    header, _ = parse(repo / "media" / "clip.shots.md")
    assert header.video == "media/clip.mp4"


@needs_ffmpeg
def test_detect_single_colour_video_warns_about_shot_count(repo, capsys):
    """需求 1.7：镜头数少于 2 时仍然生成清单，但提示。"""
    make_video(repo / "flat.mp4", colors=("red",), seconds=3)
    assert cli.main(["detect", "flat.mp4"]) == 0
    assert "不太正常" in capsys.readouterr().out
    assert parse(repo / "flat.shots.md")[1] == [(0, 30)]


@needs_ffmpeg
def test_detect_scale_option_is_written_to_the_header(repo):
    make_video(repo / "three.mp4")
    assert cli.main(["detect", "three.mp4", "--scale", "120"]) == 0
    header, shots = parse(repo / "three.shots.md")
    assert header.scale == 120 and len(shots) == 3


@needs_ffmpeg
def test_detect_list_registers_with_the_core(repo):
    """生成的清单能被核心层按配置登记：单元数等于镜头数，ID 对得上。"""
    from refcov.sources import register
    from refcov.store import Store

    make_video(repo / "three.mp4")
    assert cli.main(["detect", "three.mp4"]) == 0
    shot_loader.install(repo)
    res = register(Store(repo), "three.shots.md", "vid", adapter="shot")
    assert [u["id"] for u in res.entry["units"]] == ["shot-00-00-0", "shot-00-02-0", "shot-00-04-0"]
    assert res.entry["adapter"] == "shot"


def test_detect_without_ffmpeg_fails_and_writes_nothing(repo, monkeypatch, capsys):
    """需求 4.4：ffmpeg 或 ffprobe 不在 PATH 上：失败，消息写明缺哪个、怎么装，不生成清单。"""
    (repo / "fake.mp4").write_bytes(b"not a video")
    monkeypatch.setenv("PATH", "")
    assert cli.main(["detect", "fake.mp4"]) == 1
    err = capsys.readouterr().err
    assert "找不到 ffmpeg" in err and "安装" in err
    assert not list(repo.glob("*.md")) and not list(repo.glob("*.tmp"))


def test_detect_outside_a_repo_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "v.mp4").write_bytes(b"x")
    assert cli.main(["detect", "v.mp4"]) == 1
    assert "没有 .git" in capsys.readouterr().err
    assert not list(tmp_path.glob("*.md"))


def test_detect_missing_video_fails(repo, capsys):
    assert cli.main(["detect", "nope.mp4"]) == 1
    assert "找不到视频文件" in capsys.readouterr().err


@needs_ffmpeg
def test_detect_refuses_a_list_path_outside_the_repo(repo, tmp_path_factory, capsys):
    """清单必须在仓库里，否则登记会被拒绝：`--out` 指到仓库外时失败，不写文件。"""
    make_video(repo / "three.mp4")
    target = tmp_path_factory.mktemp("elsewhere") / "x.shots.md"
    assert cli.main(["detect", "three.mp4", "--out", str(target)]) == 1
    assert "清单要放在仓库里" in capsys.readouterr().err
    assert not target.exists()


def test_detect_broken_video_fails_cleanly(repo, capsys):
    """不是视频的文件：失败，不留清单。"""
    (repo / "junk.mp4").write_bytes(b"this is definitely not a video" * 20)
    if shot_loader.load().shutil.which("ffprobe") is None:
        pytest.skip("没有 ffprobe")
    assert cli.main(["detect", "junk.mp4"]) == 1
    assert "检测失败" in capsys.readouterr().err
    assert not list(repo.glob("*.shots.md")) and not list(repo.glob("*.tmp"))
