"""资料提议和执行（易用性改造第二层，设计第 2–4 节）。只用标准库。

`propose()` 只读清单和配置，只在状态目录里存下一份提议。`apply()` 是唯一写入的一步：参数和提议逐项
一致、每个文件的校验值没变、同一份提议只能成功一次，然后用登记子命令同一段写入代码新增参考源，并追加
一条 `apply` 记录。接入层（权限规则、MCP 工具的注册）不在这里（tests/test_core_names.py）。
"""

from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path

from refcov import api, citations, coverage
from refcov.sources import SOURCE_ID, RegisterError, _is_url, _load_file, content_sha256, file_name, write_locked
from refcov.store import PROPOSALS_DIR, ConfigError, LockTimeout, Store, StoreError, now_iso

MAX_FILES = 20  # 一次提议最多几个文件（设计 4）
PROPOSAL_ID = re.compile(r"p-[0-9a-f]{8}")
_NOT_ID = re.compile(r"[^a-z0-9]+")

# 效果说明（设计 4.2）。单元数算得出时用 EFFECT，算不出时用 EFFECT_UPPER（写上限）。
EFFECT = (
    "登记后，没有命中任何 [[scope]] 的路径要先读完新资料的 {n} 个单元，写文件前关卡才放行。"
    "命中 [[scope]] 的路径只看配置里列出的参考源，这次登记不增加它们要读的单元。"
    "要让它们也读新资料，需要用户在 refcov.toml 的对应规则里加上编号 {ids}。"
    "（单元数按提议时的模式、配置和需求文档算。）"
)
EFFECT_UPPER = (
    "登记后，没有命中任何 [[scope]] 的路径要先读新资料，写文件前关卡才放行；最多要读 {n} 个单元。"
    "命中 [[scope]] 的路径只看配置里列出的参考源，这次登记不增加它们要读的单元。"
    "要让它们也读新资料，需要用户在 refcov.toml 的对应规则里加上编号 {ids}。"
    "（单元数没算准，按新增单元的总数写上限。）"
)


class ProposalError(Exception):
    """提议或执行做不了。消息就是给 AI 看的原因。

    抛出时：`propose` 没有存下提议；`apply` 没有写清单、缓存或日志。写入阶段的 I/O 错误是例外，
    见 `apply` 里的说明。
    """


def _markdown(store: Store):
    from refcov.adapters import loader

    try:
        return loader.load(store, "markdown")
    except loader.AdapterError as e:  # 内置的适配器，正常不会出现
        raise ProposalError(str(e)) from e


def _manifest(store: Store) -> dict:
    try:
        return store.read_sources()
    except (OSError, ValueError) as e:
        raise ProposalError(f"清单读不了：{store.sources_path}：{e}") from e


def _proposal_file(store: Store, pid) -> Path:
    if not isinstance(pid, str) or not PROPOSAL_ID.fullmatch(pid):
        raise ProposalError(f"提议编号格式不对：{pid!r}。要用 propose_sources 返回的编号（p- 加 8 位十六进制）。")
    return store.state_dir / PROPOSALS_DIR / f"{pid}.json"


def _read_proposal(store: Store, pid) -> dict:
    path = _proposal_file(store, pid)
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProposalError(f"没有提议 {pid}。要用 propose_sources 返回的编号。") from None
    except (OSError, ValueError) as e:
        raise ProposalError(f"提议 {pid} 读不了：{e}") from e
    if not isinstance(rec, dict) or not isinstance(rec.get("items"), list):
        raise ProposalError(f"提议 {pid} 的内容不完整，不能执行。请重新提议。")
    return rec


def _write_proposal(store: Store, rec: dict) -> None:
    """整份写入：先写临时文件再替换，写一半出错不留坏文件（设计 2）。"""
    path = _proposal_file(store, rec["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _new_id(store: Store) -> str:
    folder = store.state_dir / PROPOSALS_DIR
    for _ in range(100):
        pid = "p-" + secrets.token_hex(4)
        if not (folder / f"{pid}.json").exists():
            return pid
    raise ProposalError("提议编号用完了（不太可能），请再提议一次。")


def default_source_id(rel: str) -> str:
    """没给编号时由文件名生成：不带扩展名，转小写，非字母数字换成 `-`，去掉首尾的 `-`（设计 4 第 3 条）。"""
    return _NOT_ID.sub("-", file_name(rel, "").lower()).strip("-")


def _required_new_units(store: Store, sources: list, new_entries: list) -> int:
    """登记以后，新资料里要读的单元数（设计 4.1）：用核心层的必看集合算。

    "登记以后"的清单 = 现在的清单 + 新条目。需求文档里的引用按"登记以后"的已知单元重新对一遍，
    所以原来悬空的引用到这里会变成有效。模式和 [relax] 用配置里的。
    """
    inp = api.gather(store)
    after = list(sources) + list(new_entries)
    known = citations.known_units({"sources": after})
    cited = set()
    for doc in inp.docs:
        text = (store.root / doc).read_text(encoding="utf-8-sig")
        cited.update(tuple(ref.split("/", 1)) for ref in citations.check_requirements(text, known).cited)
    inactive = api._inactive_auto(store, sources, inp.records, inp.cfg)
    required = coverage.required_set([s for s in after if s["id"] not in inactive],
                                     api._decls(store, after), inp.cfg["mode"], inp.cfg["relax"], cited)
    new_ids = {e["id"] for e in new_entries}
    return sum(1 for src, _unit in required.units if src in new_ids)


def _effect(store: Store, sources: list, new_entries: list) -> str:
    ids = "、".join(e["id"] for e in new_entries)
    total = sum(len(e["units"]) for e in new_entries)
    try:
        n = _required_new_units(store, sources, new_entries)
    except Exception:  # 算不准（需求文档读不了、配置坏了等）：写上限，不假装算出来了
        return EFFECT_UPPER.format(n=total, ids=ids)
    return EFFECT.format(n=n, ids=ids)


def propose(store: Store, items) -> dict:
    """提议（设计第 4 节）：检查每个文件，算效果说明，存下一份提议，返回提议记录。只读清单和配置。

    `items` 是列表，每项 `{"path": 仓库里的 Markdown 路径, "source_id": 可选的编号}`。
    任一项不通过，整份提议都不存，抛 ProposalError 说明是哪一项。
    """
    if not isinstance(items, list) or not items:
        raise ProposalError("没有要提议的文件。items 要是列表，每项有 path（仓库里的 Markdown 路径），可选 source_id。")
    if len(items) > MAX_FILES:
        raise ProposalError(f"一次最多提议 {MAX_FILES} 个文件，这次有 {len(items)} 个。请分几次提议。")
    try:
        cfg = store.load_config()
    except ConfigError as e:
        raise ProposalError(f"配置写错了，先修好再提议：{e}") from e
    manifest = _manifest(store)
    sources = manifest.get("sources", [])
    by_origin = {s.get("origin"): s.get("id") for s in sources}
    taken = {s.get("id") for s in sources}
    try:
        matched, _empty = api._spec_matches(store, cfg)
    except (OSError, StoreError, ValueError) as e:
        raise ProposalError(f"查 [sources] 匹配的文件时出错：{e}") from e
    md = _markdown(store)
    new_items, new_entries, seen_paths, seen_ids = [], [], set(), set()
    for raw in items:
        if not isinstance(raw, dict) or not isinstance(raw.get("path"), str) or not raw["path"].strip():
            raise ProposalError("items 的每一项都要有 path（仓库里 Markdown 文件的路径）。")
        path = raw["path"].strip()
        if _is_url(path):
            raise ProposalError(f"网址不收，第一版只收仓库里的 Markdown：{path}")
        try:
            data, rel = _load_file(store, path)
        except RegisterError as e:
            raise ProposalError(str(e)) from e
        if rel in by_origin:
            raise ProposalError(f"{rel} 已经登记为参考源 {by_origin[rel]}。要更新它，由用户在终端运行同步或登记子命令。")
        if rel in matched:
            raise ProposalError(f"{rel} 已被 [sources] 的通配符匹配，它由 refcov sync 登记（由用户在终端运行）。")
        if rel in seen_paths:
            raise ProposalError(f"同一份提议里路径重复：{rel}")
        sid = raw.get("source_id")
        if sid is None or sid == "":
            sid = default_source_id(rel)
            if not sid:
                raise ProposalError(f"{rel} 的文件名生成不了编号，请给一个 source_id。")
        if not isinstance(sid, str) or not SOURCE_ID.fullmatch(sid) or sid.startswith("f-"):
            raise ProposalError(f"参考源编号不合规则：{sid!r}。只能用小写字母、数字和短横线，不能以 f- 开头。")
        if sid in taken or sid in seen_ids:
            raise ProposalError(f"参考源编号 {sid} 已经用过（清单里或这份提议里）。请换一个编号。")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise ProposalError(f"不是 UTF-8 编码：{rel}：{e}") from e
        sha = content_sha256(text)
        try:
            units = md.split(data, file_name(rel, sid))
        except Exception as e:  # 适配器拆分失败：这一个文件不能提议
            raise ProposalError(f"{rel} 拆分失败：{type(e).__name__}: {e}") from e
        new_items.append({"path": rel, "sha256": sha, "source_id": sid, "adapter": "markdown",
                          "units": len(units), "titles": [u.title for u in units]})
        new_entries.append({"id": sid, "origin": rel, "sha256": sha, "adapter": "markdown",
                            "units": [u.manifest_entry() for u in units]})
        seen_paths.add(rel)
        seen_ids.add(sid)
    rec = {"id": _new_id(store), "created": now_iso(), "status": "pending", "items": new_items,
           "effect": _effect(store, sources, new_entries), "applied_seq": None}
    _write_proposal(store, rec)
    return rec


def propose_text(rec: dict) -> str:
    """提议给 AI 看的文字（MCP 的返回）。最后一行是 HINT，不是调用编号：提议不是读取。"""
    from refcov.api import HINT

    lines = [f"提议 {rec['id']}：还没有登记。要登记，用 apply_proposal 执行，并在 Kiro 的权限弹窗里批准。"]
    for it in rec["items"]:
        titles = "、".join(it["titles"][:8]) + ("、…" if len(it["titles"]) > 8 else "")
        lines.append(f"- {it['path']} → 参考源 {it['source_id']}，{it['units']} 个单元：{titles}")
        lines.append(f"  sha256 {it['sha256']}")
    lines.append("")
    lines.append(rec["effect"])
    lines.append("")
    lines.append(f"执行时，proposal 填 {rec['id']}，files 里每一项照抄上面的 path、sha256 和参考源编号（source_id）。"
                 "参数必须和这份提议逐项相同，否则不会执行。")
    lines.append(HINT)
    return "\n".join(lines)


def _args(items) -> dict:
    """执行的参数（设计 3.2 第 2 步）：路径 → (校验值, 参考源编号)。格式不对、路径重复就拒绝。"""
    if not isinstance(items, list) or not items:
        raise ProposalError("files 要是列表，每项有 path、sha256、source_id（和提议里的一样）。")
    out = {}
    for raw in items:
        if not isinstance(raw, dict) or not all(isinstance(raw.get(k), str) for k in ("path", "sha256", "source_id")):
            raise ProposalError("files 的每一项都要有 path、sha256、source_id 三个字符串。")
        if raw["path"] in out:
            raise ProposalError(f"files 里路径重复：{raw['path']}。")
        out[raw["path"]] = (raw["sha256"], raw["source_id"])
    return out


def _mismatches(want: dict, got: dict) -> list[str]:
    out = []
    for path, (sha, sid) in want.items():
        if path not in got:
            out.append(f"缺 {path}")
            continue
        got_sha, got_sid = got[path]
        if got_sha != sha:
            out.append(f"{path} 的 sha256 和提议不同")
        if got_sid != sid:
            out.append(f"{path} 的参考源编号和提议不同（提议里是 {sid}）")
    out.extend(f"多了 {path}" for path in got if path not in want)
    return out


def apply(store: Store, proposal, items) -> str:
    """执行（设计第 3 节）：唯一写入的一步。成功返回执行结果的文字，最后一行是 `refcov-call: c-<编号>`。

    核对阶段（参数、路径、校验值、单元数）不通过：什么都不写。核对通过以后，清单、缓存、日志在日志锁里
    写入。写入阶段的 I/O 错误只能部分完成（日志里可能已有登记记录，清单可能未变）；这种情况报错，
    请用户检查，不自动回滚（和登记子命令的顺序一样，日志排在清单前面）。
    """
    rec = _read_proposal(store, proposal)
    if rec.get("status") == "applied":
        raise ProposalError(f"提议 {rec.get('id')} 已经执行过（执行记录序号 {rec.get('applied_seq')}），不能再执行。"
                            "要登记别的文件，请重新提议。")
    if rec.get("status") != "pending":
        raise ProposalError(f"提议 {rec.get('id')} 的状态不对，不能执行。请重新提议。")
    want = {it["path"]: (it["sha256"], it["source_id"]) for it in rec["items"]}
    diffs = _mismatches(want, _args(items))
    if diffs:
        raise ProposalError("参数和提议不一致，已拒绝，没有登记任何东西：" + "；".join(diffs) +
                            "。请照抄提议里的内容，或重新提议。")
    md = _markdown(store)
    prepared = []
    for it in rec["items"]:  # 读一次：核对和登记用同一份字节（设计 3.2 第 3 步）
        try:
            data, rel = _load_file(store, it["path"])
        except RegisterError as e:
            raise ProposalError(f"{it['path']} 现在不能登记：{e}。请重新提议。") from e
        if rel != it["path"]:
            raise ProposalError(f"{it['path']} 的位置变了（现在是 {rel}）。请重新提议。")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise ProposalError(f"{rel} 不再是 UTF-8 编码，已拒绝。请重新提议。") from e
        if content_sha256(text) != it["sha256"]:
            raise ProposalError(f"{rel} 在提议后改过了（校验值不同），已拒绝，没有登记任何东西。请重新提议。")
        try:
            units = md.split(data, file_name(rel, it["source_id"]))
        except Exception as e:
            raise ProposalError(f"{rel} 拆分失败：{type(e).__name__}: {e}。请重新提议。") from e
        if len(units) != it["units"]:
            raise ProposalError(f"{rel} 拆出的单元数变了（{len(units)} 个，提议时是 {it['units']} 个）。请重新提议。")
        prepared.append((it, data, units))
    try:
        with store.locked():  # 锁里再确认一次（设计 3.2 第 4 步）
            current = _manifest(store)
            fresh = _read_proposal(store, rec["id"])
            if fresh.get("status") != "pending":
                raise ProposalError(f"提议 {rec['id']} 已经被执行过了，不能再执行。")
            sources = current.setdefault("sources", [])
            taken = {s.get("id") for s in sources}
            origins = {s.get("origin") for s in sources}
            for it in rec["items"]:
                if it["source_id"] in taken or it["path"] in origins:
                    raise ProposalError(f"编号 {it['source_id']} 或路径 {it['path']} 已经在清单里了"
                                        "（被别的途径登记过）。已拒绝，请重新提议。")
            for it, data, units in prepared:
                write_locked(store, current, it["source_id"], it["path"], data, it["sha256"], "markdown", units, None)
            seq = store.next_seq_locked()
            apply_rec = store.append_locked(
                "apply", None, call=f"c-{seq}", proposal=rec["id"],
                sources=[it["source_id"] for it in rec["items"]],
                items=[{"source": it["source_id"], "path": it["path"], "sha256": it["sha256"]}
                       for it in rec["items"]])
            store.write_sources(current)
            fresh["status"] = "applied"
            fresh["applied_seq"] = apply_rec["seq"]
            _write_proposal(store, fresh)
    except LockTimeout as e:
        raise ProposalError(f"拿不到日志锁，没有登记任何东西：{e}。请稍后再执行。") from e
    except (StoreError, OSError) as e:
        raise ProposalError(f"写入时出错：{e}。清单可能没有完全写完，日志里可能已有登记记录，"
                            "请告诉用户用 refcov report 检查。") from e
    names = "；".join(f"{it['source_id']}（{it['units']} 个单元，{it['path']}）" for it in rec["items"])
    return (f"已登记 {len(rec['items'])} 个参考源：{names}。\n"
            f"{rec['effect']}\n"
            f"{api.HINT}\n"
            f"{api.CALL_PREFIX}c-{seq}")
