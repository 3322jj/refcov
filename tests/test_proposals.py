"""资料提议和执行（设计第 2–4、6 节，需求 1–3、5）：性质 P1–P6、手动删除 M1、固定例子。

临时目录当仓库根目录（有 `.git`）。Hypothesis 生成文件内容、参数和配置。性质写在各测试的 docstring 里。
"""

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from refcov import api, proposals
from refcov.proposals import ProposalError
from refcov.sources import register
from refcov.store import Store

TITLE = st.text(alphabet="abcXYZ0123中文 -[]", min_size=1, max_size=10).filter(lambda s: s.strip() and s.strip()[0] != "-")
BODY = st.text(alphabet="abc 中文.,\n", min_size=0, max_size=40)


def make_repo(root: Path) -> Store:
    (root / ".git").mkdir(exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    return Store(root)


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def doc(sections) -> str:
    """[(标题, 正文)] 变成 Markdown。标题里不含 #，正文里不含 #。"""
    return "".join(f"# {title}\n\n{body}\n\n" for title, body in sections)


def args_of(rec: dict) -> list[dict]:
    """执行时照抄提议的参数。"""
    return [{"path": it["path"], "sha256": it["sha256"], "source_id": it["source_id"]} for it in rec["items"]]


def state_files(store: Store) -> dict:
    """状态目录里所有文件的字节，包括提议目录（执行失败时一个字节都不该变）。"""
    state = store.state_dir
    if not state.exists():
        return {}
    return {p.relative_to(state).as_posix(): p.read_bytes() for p in state.rglob("*") if p.is_file()}


def manifest_bytes(store: Store) -> bytes:
    return store.sources_path.read_bytes() if store.sources_path.exists() else b""


# ---- 性质 ----


@settings(max_examples=20, deadline=None)
@given(prior=st.lists(st.tuples(TITLE, BODY), min_size=1, max_size=3, unique_by=lambda t: t[0]),
       new=st.lists(st.tuples(TITLE, BODY), min_size=1, max_size=2, unique_by=lambda t: t[0]))
def test_p1_apply_only_adds(prior, new):
    """性质 P1：执行只新增。执行前后，清单里已有的每一项都和以前相等；项数只增不减，增加的项数等于提议的文件数。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = make_repo(root)
        write(root, "docs/old.md", doc(prior))
        register(store, "docs/old.md", "old")
        for i, (title, body) in enumerate(new):
            write(root, f"docs/new{i}.md", doc([(title, body)]))
        before = store.read_sources()["sources"]
        rec = proposals.propose(store, [{"path": f"docs/new{i}.md"} for i in range(len(new))])
        proposals.apply(store, rec["id"], args_of(rec))
        after = store.read_sources()["sources"]
        assert after[:len(before)] == before
        assert len(after) == len(before) + len(new)


@settings(max_examples=30, deadline=None)
@given(mutation=st.sampled_from(["path", "sha256", "source_id", "drop", "extra"]),
       junk=st.text(alphabet="xyz", min_size=1, max_size=4))
def test_p2_mismatched_arguments_are_refused(mutation, junk):
    """性质 P2：参数和提议不一致必拒（路径、校验值、编号、项数任一改动），清单、缓存、日志都不变；
    用正确的参数再执行仍然成功。（顺序不算不一致：比较按路径进行。）"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = make_repo(root)
        write(root, "docs/a.md", doc([("Alpha", "one")]))
        write(root, "docs/b.md", doc([("Beta", "two")]))
        rec = proposals.propose(store, [{"path": "docs/a.md"}, {"path": "docs/b.md"}])
        good = args_of(rec)
        bad = [dict(x) for x in good]
        if mutation == "path":
            bad[0]["path"] = "docs/" + junk + ".md"
        elif mutation == "sha256":
            bad[0]["sha256"] = "1" * 64 if bad[0]["sha256"] != "1" * 64 else "2" * 64
        elif mutation == "source_id":
            bad[0]["source_id"] = bad[0]["source_id"] + junk
        elif mutation == "drop":
            bad = bad[:1]
        else:
            bad.append({"path": "docs/" + junk + ".md", "sha256": "0" * 64, "source_id": "extra-" + junk})
        before = state_files(store)
        with pytest.raises(ProposalError, match="不一致|缺|多了|没有登记"):
            proposals.apply(store, rec["id"], bad)
        assert state_files(store) == before
        text = proposals.apply(store, rec["id"], good)
        assert api.call_from_text(text) is not None


@settings(max_examples=25, deadline=None)
@given(extra=st.text(alphabet="xyz中", min_size=1, max_size=5), at=st.integers(0, 60))
def test_p3_changed_content_is_refused(extra, at):
    """性质 P3：提议后文件内容变了必拒，清单、缓存、日志都不变。只改换行不算内容变化（固定例子 CRLF/LF）。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = make_repo(root)
        original = doc([("Alpha", "one two"), ("Beta", "three")])
        write(root, "docs/a.md", original)
        rec = proposals.propose(store, [{"path": "docs/a.md"}])
        cut = min(at, len(original))
        write(root, "docs/a.md", original[:cut] + extra + original[cut:])
        before = state_files(store)
        with pytest.raises(ProposalError, match="改过了"):
            proposals.apply(store, rec["id"], args_of(rec))
        assert state_files(store) == before


@settings(max_examples=15, deadline=None)
@given(title=TITLE, body=BODY)
def test_p4_second_apply_is_refused(title, body):
    """性质 P4：同一份提议第一次成功，第二次必拒，清单不再变。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = make_repo(root)
        write(root, "docs/a.md", doc([(title, body)]))
        rec = proposals.propose(store, [{"path": "docs/a.md"}])
        proposals.apply(store, rec["id"], args_of(rec))
        after_first = manifest_bytes(store)
        with pytest.raises(ProposalError, match="已经执行过"):
            proposals.apply(store, rec["id"], args_of(rec))
        assert manifest_bytes(store) == after_first


@settings(max_examples=15, deadline=None)
@given(scope=st.sampled_from([["old"], []]), relax=st.sampled_from([[], ["section"]]), title=TITLE)
def test_p5_propose_changes_no_manifest_config_or_required_set(scope, relax, title):
    """性质 P5：提议不改清单、配置和必看集合。提议前后 sources.json 和 refcov.toml 的字节相同，
    必看集合相同，状态目录里除了提议文件以外的内容也相同。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = make_repo(root)
        write(root, "docs/old.md", doc([("Old", "x")]))
        register(store, "docs/old.md", "old")
        write(root, "refcov.toml", "\n".join([
            'mode = "strict"',
            "[[scope]]",
            'paths = ["docs/**"]',
            f"sources = {json.dumps(scope)}",
            "[relax]",
            f"kinds = {json.dumps(relax)}",
            "",
        ]))
        write(root, "docs/new.md", doc([(title, "y")]))
        config_before = (root / "refcov.toml").read_bytes()
        manifest_before = manifest_bytes(store)
        required_before = api.gather(store).required.units
        files_before = state_files(store)
        proposals.propose(store, [{"path": "docs/new.md"}])
        assert (root / "refcov.toml").read_bytes() == config_before
        assert manifest_bytes(store) == manifest_before
        assert api.gather(store).required.units == required_before
        files_after = state_files(store)
        extra = set(files_after) - set(files_before)
        assert extra and all(name.startswith("proposals/") for name in extra)
        assert {k: v for k, v in files_after.items() if k in files_before} == files_before


@settings(max_examples=15, deadline=None)
@given(bad=st.integers(0, 1), junk=st.text(alphabet="xyz", min_size=1, max_size=3))
def test_p6_failed_check_leaves_no_trace(bad, junk):
    """性质 P6：执行中任一文件核对失败，清单、缓存、日志和提议文件都不变（提议仍是待执行）。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = make_repo(root)
        write(root, "docs/a.md", doc([("Alpha", "one")]))
        write(root, "docs/b.md", doc([("Beta", "two")]))
        rec = proposals.propose(store, [{"path": "docs/a.md"}, {"path": "docs/b.md"}])
        victim = ["docs/a.md", "docs/b.md"][bad]
        write(root, victim, (root / victim).read_text(encoding="utf-8") + junk)
        before = state_files(store)
        with pytest.raises(ProposalError):
            proposals.apply(store, rec["id"], args_of(rec))
        assert state_files(store) == before


def test_m1_manual_deletion_keeps_report_check_status_and_list_working(tmp_path):
    """固定测试 M1（设计第 6.2 节）：手工从 sources.json 删掉一项以后，report、check（带路径和不带）、
    状态行和单元列表照常工作，不报错。这是第二层"没有删除命令、用户手动删"的前提。"""
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("Alpha", "one")]))
    write(tmp_path, "docs/b.md", doc([("Beta", "two")]))
    register(store, "docs/a.md", "a")
    register(store, "docs/b.md", "b")
    api.read(store, "a", "Alpha")
    manifest = json.loads(store.sources_path.read_text(encoding="utf-8"))
    manifest["sources"] = [s for s in manifest["sources"] if s["id"] != "b"]
    store.sources_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    rep = api.report(store, None)
    assert rep["sources"]
    assert api.check(store)["pass"] in (True, False)
    assert api.check(store, "docs/a.md")["path"] == "docs/a.md"
    line = api.status_line(store, None)
    assert "RefCov" in line
    assert all(u["source"] == "a" for u in api.list_units(store))


# ---- 固定例子 ----


def test_non_markdown_is_refused(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.txt", "hello")
    with pytest.raises(ProposalError, match="不支持该格式"):
        proposals.propose(store, [{"path": "docs/a.txt"}])


def test_outside_repository_is_refused(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    store = make_repo(repo)
    write(tmp_path, "outside.md", doc([("X", "y")]))
    with pytest.raises(ProposalError, match="仓库里"):
        proposals.propose(store, [{"path": str(tmp_path / "outside.md")}])


def test_symlink_pointing_outside_is_refused(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    store = make_repo(repo)
    write(tmp_path, "outside.md", doc([("X", "y")]))
    try:
        (repo / "docs" / "link.md").symlink_to(tmp_path / "outside.md")
    except OSError:
        pytest.skip("这台机器不能建符号链接（Windows 需要开发者模式或权限）")
    with pytest.raises(ProposalError, match="仓库里"):
        proposals.propose(store, [{"path": "docs/link.md"}])


def test_url_is_refused(tmp_path):
    store = make_repo(tmp_path)
    with pytest.raises(ProposalError, match="网址不收"):
        proposals.propose(store, [{"path": "https://example.com/a.md"}])


def test_f_prefix_is_refused(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("A", "x")]))
    with pytest.raises(ProposalError, match="不能以 f- 开头"):
        proposals.propose(store, [{"path": "docs/a.md", "source_id": "f-x-123456"}])


def test_already_registered_path_is_refused(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("A", "x")]))
    register(store, "docs/a.md", "a")
    with pytest.raises(ProposalError, match="已经登记为参考源 a"):
        proposals.propose(store, [{"path": "docs/a.md", "source_id": "other"}])


def test_file_matched_by_sources_is_refused(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("A", "x")]))
    write(tmp_path, "refcov.toml", '[sources]\nfiles = ["docs/*.md"]\n')
    with pytest.raises(ProposalError, match="通配符匹配"):
        proposals.propose(store, [{"path": "docs/a.md"}])


def test_duplicate_id_and_duplicate_path_are_refused(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("A", "x")]))
    write(tmp_path, "docs/b.md", doc([("B", "y")]))
    register(store, "docs/a.md", "a")
    with pytest.raises(ProposalError, match="已经用过"):
        proposals.propose(store, [{"path": "docs/b.md", "source_id": "a"}])
    with pytest.raises(ProposalError, match="路径重复"):
        proposals.propose(store, [{"path": "docs/b.md"}, {"path": "docs/b.md", "source_id": "bb"}])


def test_default_id_comes_from_the_file_name(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/My Guide (v2).md", doc([("A", "x")]))
    rec = proposals.propose(store, [{"path": "docs/My Guide (v2).md"}])
    assert rec["items"][0]["source_id"] == "my-guide-v2"


def test_crlf_and_lf_have_the_same_checksum(tmp_path):
    store = make_repo(tmp_path)
    text = doc([("Alpha", "one"), ("Beta", "two")])
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "lf.md").write_bytes(text.encode("utf-8"))
    (tmp_path / "docs" / "crlf.md").write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    rec = proposals.propose(store, [{"path": "docs/lf.md", "source_id": "lf"},
                                    {"path": "docs/crlf.md", "source_id": "crlf"}])
    assert rec["items"][0]["sha256"] == rec["items"][1]["sha256"]


def test_apply_writes_an_apply_record_and_the_result_ends_with_the_call(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("Alpha", "one")]))
    rec = proposals.propose(store, [{"path": "docs/a.md", "source_id": "guide"}])
    text = proposals.apply(store, rec["id"], args_of(rec))
    call = api.call_from_text(text)
    assert call and call.startswith("c-")
    assert text.endswith(f"refcov-call: {call}")
    records = store.records()
    (apply_rec,) = [r for r in records if r["type"] == "apply"]
    assert apply_rec["call"] == call
    assert apply_rec["proposal"] == rec["id"]
    assert apply_rec["sources"] == ["guide"]
    assert apply_rec["items"] == [{"source": "guide", "path": "docs/a.md", "sha256": rec["items"][0]["sha256"]}]
    assert any(r["type"] == "register" and r["source"] == "guide" for r in records)
    saved = json.loads((store.state_dir / "proposals" / f"{rec['id']}.json").read_text(encoding="utf-8"))
    assert saved["status"] == "applied" and saved["applied_seq"] == apply_rec["seq"]


def test_session_can_be_attached_to_an_apply_record(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("Alpha", "one")]))
    rec = proposals.propose(store, [{"path": "docs/a.md"}])
    call = api.call_from_text(proposals.apply(store, rec["id"], args_of(rec)))
    assert api.attach_session(store, call, "sess_x") is True
    assert [r["session"] for r in store.records() if r["type"] == "session" and r["call"] == call] == ["sess_x"]


def test_effect_counts_new_units_and_respects_relax(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("Alpha", "one"), ("Beta", "two")]))
    rec = proposals.propose(store, [{"path": "docs/a.md"}])
    assert "2 个单元" in rec["effect"] and "编号 a" in rec["effect"]
    write(tmp_path, "refcov.toml", 'mode = "strict"\n[relax]\nkinds = ["section"]\n')
    store2 = Store(tmp_path)
    rec2 = proposals.propose(store2, [{"path": "docs/a.md", "source_id": "b"}])
    assert "0 个单元" in rec2["effect"]


def test_post_mcp_hook_attaches_the_session_to_an_apply_record(tmp_path, monkeypatch):
    """端到端（设计第 3.4 节）：执行结果的最后一行是调用编号，post-mcp 钩子据此把会话补记到 apply 记录上。"""
    import sys
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from integrations.kiro import hook

    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("Alpha", "one")]))
    rec = proposals.propose(store, [{"path": "docs/a.md"}])
    text = proposals.apply(store, rec["id"], args_of(rec))
    call = api.call_from_text(text)
    monkeypatch.setattr(hook, "ROOT", tmp_path)
    hook.post_mcp({"hook_event_name": "PostToolUse", "tool_name": "mcp_refcov_apply_proposal",
                   "tool_response": text, "session_id": "sess_hook",
                   "tool_input": {"proposal": rec["id"], "files": []}})
    attached = [r["session"] for r in store.records() if r["type"] == "session" and r.get("call") == call]
    assert attached == ["sess_hook"]


def test_apply_refuses_a_changed_checksum_and_a_taken_id(tmp_path):
    store = make_repo(tmp_path)
    write(tmp_path, "docs/a.md", doc([("Alpha", "one")]))
    write(tmp_path, "docs/b.md", doc([("Beta", "two")]))
    rec = proposals.propose(store, [{"path": "docs/a.md", "source_id": "same"}])
    register(store, "docs/b.md", "same")  # 另一条途径先登记了同一个编号，提议还是待执行
    with pytest.raises(ProposalError, match="已经在清单里"):
        proposals.apply(store, rec["id"], args_of(rec))
