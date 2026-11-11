"""与工具无关的核心层入口（设计 6）。接入层和 MCP 服务只调用这里，参数里没有任何 AI 工具的字段名。

现在有读单元（任务 5）和会话补记（任务 6）。`read` 是唯一追加 `read` 记录的函数（需求 4.8）。
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from refcov.sources import content_sha256, file_name
from refcov.store import LockTimeout, Store, StoreError

# 需求 9.9、设计 5：每个工具的返回都带这一句
HINT = "参考材料要用 RefCov 的 MCP 工具读，直接读文件不算看过。"
CALL_PREFIX = "refcov-call: "


_CALL_LINE = re.compile(r"refcov-call: (c-\d+)")


class ReadError(Exception):
    """读不了这个单元。消息就是给 AI 看的原因。抛出时没有写 read 记录。"""


class AttachError(Exception):
    """会话补记不能写（调用编号对不上 read 记录、参数对不上、已记成别的会话）。抛出时没有写记录。"""


def call_from_text(text: str) -> str | None:
    """工具返回文字的最后一行完全是 `refcov-call: c-<数字>` 时返回调用编号，否则返回 None（设计 5）。

    只去掉末尾的换行，不去其他空白。list_units 和出错的 read_unit 没有这一行，返回 None。
    """
    lines = text.rstrip("\r\n").split("\n")
    m = _CALL_LINE.fullmatch(lines[-1].rstrip("\r"))
    return m.group(1) if m else None


def attach_session(store: Store, call: str, session: str,
                   source: str | None = None, unit: str | None = None) -> bool:
    """会话补记（需求 4.5）：给调用编号 `call` 对应的 read 记录追加一条 `session` 记录，不改原记录。

    - `call` 必须对应一条已有的 read 记录；给了 `source`、`unit` 时还要和那条记录一致。
    - 同一个调用编号已经补记成同一个会话：不写，返回 False。
    - 已经补记成别的会话：不写，抛 AttachError。
    写入时返回 True。2 秒拿不到锁时抛 LockTimeout，什么都不写。检查和追加都在锁里做，
    并行读取时几个钩子同时补记也不会重复。
    """
    if not session:
        raise AttachError(f"{call}：会话 ID 为空")
    with store.locked():
        records = store.records()
        read_rec = next((r for r in records if r.get("type") == "read" and r.get("call") == call), None)
        if read_rec is None:
            raise AttachError(f"{call}：日志里没有这个调用编号的 read 记录")
        for field, given in (("source", source), ("unit", unit)):
            if given is not None and read_rec.get(field) != given:
                raise AttachError(f"{call}：工具参数 {field}={given!r} 和 read 记录里的 {read_rec.get(field)!r} 不一致")
        done = [r.get("session") for r in records if r.get("type") == "session" and r.get("call") == call]
        if session in done:
            return False
        if done:
            raise AttachError(f"{call}：已经补记成会话 {done[0]!r}，这次是 {session!r}")
        store.append_locked("session", session, call=call)
    return True


@dataclass(frozen=True)
class ReadResult:
    source: str
    unit: str
    title: str
    texts: list[str]
    images: list  # refcov.sources.Image；文档适配器没有图片
    call: str  # "c-<seq>"
    record: dict

    def text(self) -> str:
        """返回给 AI 的整段文字：正文 → 提示 → `refcov-call: c-<seq>`。最后一行就是调用编号，后面没有换行。"""
        body = "\n\n".join(self.texts)
        if body and not body.endswith("\n"):
            body += "\n"
        return f"{body}\n{HINT}\n{CALL_PREFIX}{self.call}"


def _adapter(name: str):
    if name == "markdown":
        from refcov.adapters import markdown

        return markdown
    raise ReadError(f"清单里的适配器 {name!r} 不认识")


def _nearest(word: str, choices: list[str]) -> str:
    near = difflib.get_close_matches(word, choices, n=3, cutoff=0)
    return "、".join(near) if near else "（没有）"


def _manifest(store: Store) -> list[dict]:
    try:
        return store.read_sources().get("sources", [])
    except (OSError, ValueError) as e:
        raise ReadError(f"清单读不了：{store.sources_path}：{e}") from e


def _find_source(store: Store, source: str) -> dict:
    sources = _manifest(store)
    for s in sources:
        if s.get("id") == source:
            return s
    raise ReadError(f"没有参考源 {source!r}。最接近的：{_nearest(source, [s['id'] for s in sources])}")


def valid_reads(store: Store) -> set[tuple[str, str]]:
    """有效读取过的 (参考源, 单元)：`read` 记录里的 `unit_sha256` 等于清单里该单元当前的校验值（需求 1.4）。"""
    current = {(s["id"], u["id"]): u["sha256"] for s in _manifest(store) for u in s.get("units", [])}
    return {
        (r.get("source"), r.get("unit"))
        for r in store.records()
        if r.get("type") == "read" and current.get((r.get("source"), r.get("unit"))) == r.get("unit_sha256")
    }


def list_units(store: Store, source: str | None = None) -> list[dict]:
    """每个单元的参考源、ID、标题、类型、历史上是否看过（有效读取）。"""
    sources = [_find_source(store, source)] if source else _manifest(store)
    seen = valid_reads(store)
    return [
        {"source": s["id"], "id": u["id"], "title": u["title"], "kind": u["kind"],
         "read": (s["id"], u["id"]) in seen}
        for s in sources
        for u in s.get("units", [])
    ]


def read(store: Store, source: str, unit: str) -> ReadResult:
    """读一个单元并追加一条 `read` 记录（需求 4.1、4.6）。会话先记 null，由接入层按调用编号补记（需求 4.5）。

    按清单里的 sha256 去缓存找原文、拆分、按单元 ID 取正文。缓存没有、缓存内容和清单对不上、
    单元不存在、2 秒拿不到日志锁时抛 ReadError：不返回内容，也不写记录（少算不多算）。
    """
    entry = _find_source(store, source)
    ids = [u["id"] for u in entry.get("units", [])]
    listed = next((u for u in entry.get("units", []) if u["id"] == unit), None)
    if listed is None:
        raise ReadError(f"参考源 {source} 里没有单元 {unit!r}。最接近的 3 个：{_nearest(unit, ids)}")
    cache = store.cache_dir / entry["sha256"]
    try:
        data = cache.read_bytes()
    except FileNotFoundError:
        raise ReadError(
            f"缓存里没有 {source} 的原文（新克隆的仓库没有缓存）。"
            f"请用户在终端重新登记：refcov add {entry['origin']} --id {source}"
        ) from None
    except OSError as e:
        raise ReadError(f"缓存读不了：{cache}：{e}") from e
    try:
        ok = content_sha256(data.decode("utf-8-sig")) == entry["sha256"]
    except UnicodeDecodeError:
        ok = False
    if not ok:
        raise ReadError(f"缓存里 {source} 的原文和清单的校验值对不上。请用户在终端重新登记：refcov add {entry['origin']} --id {source}")
    adapter = _adapter(entry.get("adapter", ""))
    try:
        found = next(u for u in adapter.split(data, file_name(entry["origin"], source)) if u.id == unit)
    except StopIteration:
        found = None
    if found is None or found.sha256 != listed["sha256"]:
        raise ReadError(f"按缓存重新拆出的单元 {source}/{unit} 和清单对不上。请用户在终端重新登记：refcov add {entry['origin']} --id {source}")
    texts = [found.text]
    try:
        with store.locked():
            seq = store.next_seq_locked()
            rec = store.append_locked("read", None, call=f"c-{seq}", source=source, unit=unit,
                                      unit_sha256=found.sha256, text_units=len(texts), images=0)
    except LockTimeout as e:
        raise ReadError(f"拿不到日志锁，这次读取没有记下，也不返回内容，请稍后再读：{e}") from e
    except (StoreError, OSError) as e:
        raise ReadError(f"写读取记录失败，这次不返回内容：{e}") from e
    return ReadResult(source, unit, found.title, texts, [], rec["call"], rec)


# ---- 报告（任务 7，设计 3.5，需求 9.8、12.1–12.4）----
# 报告和状态行都只读：不拿锁、不写任何文件、不写日志记录。

MODE_NAMES = {"strict": "严格模式", "light": "轻量模式"}
STATUS_FIRST = 5  # 状态行列出还差的前几个


def report(store: Store, session: str | None = None) -> dict:
    """报告 JSON（设计 3.5）。这一步只填 sources、missing、unknown_session_calls、by_session、chain，
    外加头部的 version、generated、session、session_available、mode。必看 = 全部单元。

    `session` 为 None（MCP 拿不到会话、命令行没给 --session）时 session_available 为 false，
    各 read_session 字段为 null。mode 取自配置文件。
    """
    from refcov import coverage
    from refcov.store import now_iso

    cfg = store.load_config()
    sources = _manifest(store)
    data = coverage.summarize(sources, store.records(), session)
    chain_result = store.verify_chain()
    chain = {"ok": chain_result.ok, "lines": chain_result.lines}
    if not chain_result.ok:
        chain["broken_at"] = chain_result.broken_at  # 文字版要写"第 N 行起断开"（设计 3.2）
    if store.log_tail_partial():
        chain["partial_tail"] = True  # 末尾有别的进程正在写的半行，这次没算
    return {"version": 1, "generated": now_iso(), "session": session, "session_available": session is not None,
            "mode": cfg["mode"], **data, "chain": chain}


def _mode_name(rep: dict) -> str:
    return MODE_NAMES.get(rep.get("mode"), str(rep.get("mode")))


def _chain_text(chain: dict) -> str:
    text = (f"链完整（{chain['lines']} 行）" if chain["ok"]
            else f"第 {chain.get('broken_at')} 行起断开（共 {chain['lines']} 行）")
    if chain.get("partial_tail"):
        text += "；日志末尾有一行还没写完，这次没算"
    return text


def _totals(rep: dict) -> tuple[int, int, int | None]:
    total = sum(s["required"] for s in rep["sources"])
    hist = sum(s["required_read_history"] for s in rep["sources"])
    sess = None if not rep["session_available"] else sum(s["required_read_session"] for s in rep["sources"])
    return total, hist, sess


def report_text(rep: dict) -> str:
    """文字版报告，只从 JSON 生成（需求 12.3）。"""
    lines = [f"RefCov {_mode_name(rep)}（这一步必看 = 全部单元，还不算必看集合）"]
    if not rep["sources"]:
        lines.append("还没有登记任何参考源。")
    for s in rep["sources"]:
        sess = "不可用" if s["read_session"] is None else f"{s['read_session']}/{s['units']}"
        lines.append(f"{s['id']}：单元 本会话 {sess}，历史 {s['read_history']}/{s['units']}")
    if rep["missing"]:
        lines.append(f"还差 {len(rep['missing'])} 个：" +
                     "、".join(f"{m['source']}/{m['unit']}" for m in rep["missing"]))
    else:
        lines.append("没有还差的单元。")
    lines.append(f"会话未知的读取：{rep['unknown_session_calls']} 次")
    known = [b for b in rep["by_session"] if b["session"] != "unknown"][-5:]
    unknown = [b for b in rep["by_session"] if b["session"] == "unknown"]
    lines.append("按会话（最近 5 个）：")
    for b in known + unknown:
        lines.append(f"  {b['session']}：看过 {b['units_read']} 个单元，被拦 {b['blocks']} 次，"
                     f"送出文字 {b['text_units']} 段、图片 {b['images']} 张")
    lines.append(f"哈希链：{_chain_text(rep['chain'])}")
    lines.append(HINT)
    return "\n".join(lines)


def status_line(store: Store, session: str | None) -> str:
    """一行简短报告（需求 9.8、12.4），由报告 JSON 生成。这一步还没有达标判断，不写达标。"""
    rep = report(store, session)
    head = f"RefCov {_mode_name(rep)}："
    if not rep["sources"]:
        return f"{head}还没有登记参考源。{HINT}"
    total, hist, sess = _totals(rep)
    sess_text = "不可用" if sess is None else f"{sess}/{total}"
    text = f"{head}单元 本会话 {sess_text}，历史 {hist}/{total}；"
    missing = rep["missing"]
    if missing:
        first = "、".join(f"{m['source']}/{m['unit']}" for m in missing[:STATUS_FIRST])
        more = "、…" if len(missing) > STATUS_FIRST else ""
        text += f"还差 {len(missing)} 个：{first}{more}。"
    else:
        text += "没有还差的单元。"
    if not rep["chain"]["ok"]:
        text += f"日志哈希链{_chain_text(rep['chain'])}。"
    return text + HINT
