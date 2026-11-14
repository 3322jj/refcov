"""镜头清单的格式和纯函数（镜头应用任务 1，需求 1.2–1.6、3.1、7.5；设计 2、3.1、4）。不用 ffmpeg。"""

import dataclasses

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import shot_loader
from refcov.sources import validate_unit_id

adapter = shot_loader.load()
SHA = "a" * 64
HEADER = adapter.Header("reference.mp4", SHA, 941265067, 1731542400123456789, 4600, 0.25, 0.5)

durations = st.floats(min_value=0.1, max_value=7200, allow_nan=False)
cut_lists = st.lists(st.floats(min_value=-5, max_value=7300, allow_nan=False), max_size=60)
min_shots = st.sampled_from([0.1, 0.3, 0.5, 1.0, 2.5])


def header_for(shots, **kw):
    return dataclasses.replace(HEADER, duration_t=shots[-1][1], **kw)


@st.composite
def shot_lists(draw):
    duration = draw(durations)
    min_shot = draw(min_shots)
    return adapter.build_shots(draw(cut_lists), duration, min_shot), min_shot


@given(cut_lists, durations, min_shots)
def test_build_shots_tiles_the_video(cuts, duration, min_shot):
    """性质（需求 1.1）：镜头首尾相接、覆盖 [0, 时长]、没有空隙和重叠；每个镜头不短于最短时长（只有一个镜头时除外）；
    除 0 以外的起点都来自输入的切点。"""
    shots = adapter.build_shots(cuts, duration, min_shot)
    total = round(duration * 10)
    assert shots[0][0] == 0 and shots[-1][1] == total
    assert all(a[1] == b[0] for a, b in zip(shots, shots[1:]))
    assert all(s < e for s, e in shots)
    if len(shots) > 1:
        assert all(e - s >= round(min_shot * 10) for s, e in shots)
    given_cuts = {round(c * 10) for c in cuts}
    assert all(s in given_cuts for s, _ in shots[1:])


@given(cut_lists, durations, min_shots)
def test_build_shots_is_idempotent(cuts, duration, min_shot):
    """用结果里的切点再算一次，结果不变（并入过短镜头后不会再有过短的）。"""
    shots = adapter.build_shots(cuts, duration, min_shot)
    again = adapter.build_shots([s / 10 for s, _ in shots[1:]], duration, min_shot)
    assert again == shots


def test_build_shots_examples():
    """例子：过短的并入前一个；终点上的切点去掉；最后一个太短并入倒数第二个；整段比最短时长短时只有一个镜头。"""
    assert adapter.build_shots([2.0, 4.0], 6.0, 0.5) == [(0, 20), (20, 40), (40, 60)]
    assert adapter.build_shots([2.0, 2.2, 4.0], 6.0, 0.5) == [(0, 20), (20, 40), (40, 60)]
    assert adapter.build_shots([0.0, 6.0, 7.0], 6.0, 0.5) == [(0, 60)]
    assert adapter.build_shots([5.8], 6.0, 0.5) == [(0, 60)]
    assert adapter.build_shots([0.2], 0.3, 0.5) == [(0, 3)]
    with pytest.raises(ValueError):
        adapter.build_shots([], 0.0, 0.5)


@given(st.integers(min_value=0, max_value=10**6))
def test_shot_ids_are_valid_unit_ids(t):
    """性质（骨架需求 2.5）：镜头 ID 不含空白和方括号，且格式固定。"""
    sid = adapter.shot_id(t)
    validate_unit_id(sid)
    assert sid.startswith("shot-") and len(sid.split("-")) == 4


def test_shot_id_examples():
    assert adapter.shot_id(0) == "shot-00-00-0"
    assert adapter.shot_id(312) == "shot-00-31-2"
    assert adapter.shot_id(1740) == "shot-02-54-0"
    assert adapter.shot_id(36000) == "shot-60-00-0"  # 分钟超过两位时照常多写
    assert adapter.shot_id(61230) == "shot-102-03-0"


@given(shot_lists())
@settings(max_examples=60)
def test_list_round_trip(case):
    """性质：写出清单再读回，文件头和镜头都相同；拆出的单元数等于镜头数、ID 互不相同且合法；同一份清单拆两次结果相同。"""
    shots, min_shot = case
    h = header_for(shots, min_shot=min_shot)
    text = adapter.format_list(h, shots)
    assert adapter.parse_list(text) == (h, shots)
    units = adapter.split(text.encode("utf-8"), "x")
    assert len(units) == len(shots) and len({u.id for u in units}) == len(units)
    for u in units:
        validate_unit_id(u.id)
        assert u.kind == "shot" and u.title == u.id
    assert units == adapter.split(text.encode("utf-8"), "x")
    assert adapter.split(("\ufeff" + text.replace("\n", "\r\n")).encode("utf-8"), "x") == units  # BOM 和 CRLF 不影响


def test_scale_is_part_of_the_header_and_the_checksum():
    shots = [(0, 20), (20, 40)]
    plain = adapter.split(adapter.format_list(header_for(shots), shots).encode(), "x")
    scaled_h = header_for(shots, scale=360)
    scaled_text = adapter.format_list(scaled_h, shots)
    assert "detect_scale: 360" in scaled_text and adapter.parse_list(scaled_text)[0].scale == 360
    scaled = adapter.split(scaled_text.encode(), "x")
    assert [u.sha256 for u in plain] != [u.sha256 for u in scaled]


@given(shot_lists(), shot_lists())
@settings(max_examples=60)
def test_unit_checksum_follows_the_inputs(case_a, case_b):
    """性质（需求 3.1）：单元校验值只由视频 SHA-256、起止时间、阈值和最短镜头时长决定。
    两份清单里起止时间相同的镜头校验值相同，不同的校验值不同；视频 SHA-256、阈值、最短镜头时长任一个变了，所有单元的校验值都变。"""
    (shots_a, min_a), (shots_b, min_b) = case_a, case_b
    a = adapter.split(adapter.format_list(header_for(shots_a, min_shot=min_a), shots_a).encode(), "x")
    b = adapter.split(adapter.format_list(header_for(shots_b, min_shot=min_a), shots_b).encode(), "x")
    by_a = {(s, e): u.sha256 for (s, e), u in zip(shots_a, a)}
    for (s, e), u in zip(shots_b, b):
        if (s, e) in by_a:
            assert u.sha256 == by_a[(s, e)]
        else:
            assert u.sha256 not in by_a.values()
    for change in ({"sha256": "b" * 64}, {"threshold": 0.3}, {"min_shot": min_a + 1.0}):
        c = adapter.split(adapter.format_list(header_for(shots_a, **{"min_shot": min_a, **change}),
                                              shots_a).encode(), "x")
        assert not {u.sha256 for u in a} & {u.sha256 for u in c}


def test_size_mtime_and_video_path_do_not_change_unit_checksums():
    """视频换了位置（路径、修改时间变）但内容没变，旧读取记录仍然有效：校验值不含路径、大小、修改时间（需求 3.4 的"只是修改时间变了就放行"）。"""
    shots = [(0, 20), (20, 40)]
    a = adapter.split(adapter.format_list(header_for(shots), shots).encode(), "x")
    moved = header_for(shots, video="/elsewhere/copy.mp4", size=1, mtime_ns=7)
    b = adapter.split(adapter.format_list(moved, shots).encode(), "x")
    assert [u.sha256 for u in a] == [u.sha256 for u in b]


GOOD = adapter.format_list(HEADER, [(0, 20), (20, 40), (40, 4600)])


def mutate(text, old, new):
    assert old in text
    return text.replace(old, new, 1)


BAD = {
    "gap": mutate(GOOD, "## shot-00-04-0\nstart: 4.0", "## shot-00-04-1\nstart: 4.1"),
    "overlap": mutate(GOOD, "## shot-00-04-0\nstart: 4.0", "## shot-00-03-0\nstart: 3.0"),
    "id-not-matching-start": mutate(GOOD, "## shot-00-02-0", "## shot-00-02-1"),
    "wrong-count": mutate(GOOD, "shots: 3", "shots: 4"),
    "first-not-zero": mutate(mutate(GOOD, "## shot-00-00-0\nstart: 0.0", "## shot-00-00-5\nstart: 0.5"),
                             "shots: 3", "shots: 3"),
    "last-end-not-duration": mutate(GOOD, "end: 460.0", "end: 459.9"),
    "end-not-after-start": mutate(GOOD, "end: 2.0", "end: 0.0"),
    "missing-key": mutate(GOOD, "size: 941265067\n", ""),
    "unknown-key": mutate(GOOD, "shots: 3", "shots: 3\ncolour: red"),
    "duplicate-key": mutate(GOOD, "shots: 3", "shots: 3\nshots: 3"),
    "bad-sha": mutate(GOOD, SHA, "xyz"),
    "bad-number": mutate(GOOD, "size: 941265067", "size: many"),
    "negative-size": mutate(GOOD, "size: 941265067", "size: -1"),
    "bad-threshold": mutate(GOOD, "threshold: 0.25", "threshold: 3"),
    "two-decimals": mutate(GOOD, "end: 2.0", "end: 2.05"),
    "missing-end": mutate(GOOD, "end: 2.0\n", ""),
    "extra-line-in-section": mutate(GOOD, "end: 2.0", "end: 2.0\nnote: hi"),
    "no-sections": GOOD[: GOOD.index("## ")],
    "garbage-in-header": mutate(GOOD, "shots: 3", "shots: 3\nthis is not a key"),
}


@pytest.mark.parametrize("kind", sorted(BAD))
def test_bad_lists_are_rejected(kind):
    """清单被手改坏（空隙、重叠、ID 对不上起点、镜头数不对、缺键等）：`split` 抛 ValueError，登记因此被拒绝。"""
    with pytest.raises(ValueError):
        adapter.split(BAD[kind].encode("utf-8"), "x")


def test_good_list_is_accepted_and_facts():
    units = adapter.split(GOOD.encode(), "reference")
    assert [u.id for u in units] == ["shot-00-00-0", "shot-00-02-0", "shot-00-04-0"]
    f = adapter.facts(GOOD.encode(), "reference", "shot-00-02-0")
    assert f == {"index": 2, "of": 3, "start": 2.0, "end": 4.0, "duration": 2.0, "video_sha256": SHA}
    with pytest.raises(KeyError):
        adapter.facts(GOOD.encode(), "reference", "shot-09-09-9")


def test_adapter_interface_and_declaration():
    """骨架需求 2.1–2.4：名字、类型声明（严格必看、不是关键类型）、三个函数。"""
    assert adapter.name == "shot"
    decl = adapter.kinds["shot"]
    assert decl.strict is True and decl.key is False
    assert all(callable(getattr(adapter, f)) for f in ("split", "read", "facts"))
