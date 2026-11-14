"""与工具无关的核心层入口（设计 6）。接入层和 MCP 服务只调用这里，参数里没有任何 AI 工具的字段名。

现在有读单元（任务 5）和会话补记（任务 6）。`read` 是唯一追加 `read` 记录的函数（需求 4.8）。
"""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass

from refcov.sources import Image, content_sha256, file_name
from refcov.store import LockTimeout, Store, StoreError, path_matches

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
    images: list  # refcov.sources.Image，按适配器返回的顺序；文档适配器没有图片
    call: str  # "c-<seq>"
    record: dict

    def text(self) -> str:
        """返回给 AI 的整段文字：正文 → 提示 → `refcov-call: c-<seq>`。最后一行就是调用编号，后面没有换行。"""
        body = "\n\n".join(self.texts)
        if body and not body.endswith("\n"):
            body += "\n"
        return f"{body}\n{HINT}\n{CALL_PREFIX}{self.call}"


def _adapter(store: Store, name: str):
    """按清单里记的适配器名找适配器：`markdown` 内置，别的按配置的 `[adapters]` 加载（C4）。
    配置里没有这个名字时报错，不退回文档适配器。"""
    from refcov.adapters import loader

    try:
        return loader.load(store, name)
    except loader.AdapterError as e:
        raise ReadError(f"清单里的适配器 {name!r} 用不了：{e}") from e


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
    adapter = _adapter(store, entry.get("adapter", ""))
    try:
        found = next(u for u in adapter.split(data, file_name(entry["origin"], source)) if u.id == unit)
    except StopIteration:
        found = None
    if found is None or found.sha256 != listed["sha256"]:
        raise ReadError(f"按缓存重新拆出的单元 {source}/{unit} 和清单对不上。请用户在终端重新登记：refcov add {entry['origin']} --id {source}")
    # 内容由适配器的 `read` 给出（文字和图片）。放在拿锁、写记录之前：它抛任何异常（视频变了、取帧失败等）
    # 都不返回内容、不写记录（少算不多算，镜头应用需求 2.5、3.4）。
    try:
        parts = adapter.read(data, file_name(entry["origin"], source), unit)
    except Exception as e:
        raise ReadError(f"适配器读取 {source}/{unit} 失败，这次不返回内容，也不记读取：{e}") from e
    texts = [p for p in parts if isinstance(p, str)]
    images = [p for p in parts if isinstance(p, Image)]
    if len(texts) + len(images) != len(parts):
        raise ReadError(f"适配器读取 {source}/{unit} 返回了既不是文字也不是图片的内容，这次不返回内容，也不记读取")
    try:
        with store.locked():
            seq = store.next_seq_locked()
            rec = store.append_locked("read", None, call=f"c-{seq}", source=source, unit=unit,
                                      unit_sha256=found.sha256, text_units=len(texts), images=len(images))
    except LockTimeout as e:
        raise ReadError(f"拿不到日志锁，这次读取没有记下，也不返回内容，请稍后再读：{e}") from e
    except (StoreError, OSError) as e:
        raise ReadError(f"写读取记录失败，这次不返回内容：{e}") from e
    return ReadResult(source, unit, found.title, texts, images, rec["call"], rec)


# ---- 达标检查（任务 11，设计 7，需求 5、6、8、15）----
# 读文件（配置、清单、日志、需求文档）都在这里做，判断交给 coverage 里的纯函数。只读，不写任何文件。

_WALK_SKIP = {".git", ".refcov"}  # 找需求文档时不进的目录


class CheckError(Exception):
    """检查做不了（例如需求文档读不了）。消息就是原因。"""


def _decls(store: Store, sources: list) -> dict:
    """适配器名 → {单元类型 → 声明}（需求 2.2）。只加载清单里用到的适配器。

    加载不了的适配器（配置里删了声明、文件坏了）不抛错，也不进结果：它的单元按"类型没声明"处理，
    即严格必看（coverage.UNKNOWN_KIND，宁可多要求）。读取时会因为同一个原因报错。
    """
    from refcov.adapters import loader

    out = {}
    for name in sorted({s.get("adapter") for s in sources} - {None}):
        try:
            out[name] = loader.load(store, name).kinds
        except loader.AdapterError:
            pass
    return out


def requirement_docs(store: Store, patterns) -> list[str]:
    """仓库里命中配置 `requirements` 模式的文件，相对仓库根目录、`/` 分隔，排好序。不进 .git 和状态目录。"""
    if not patterns:
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(store.root):
        dirnames[:] = sorted(d for d in dirnames if d not in _WALK_SKIP)
        for f in filenames:
            rel = store.rel(os.path.join(dirpath, f))
            if path_matches(rel, patterns):
                out.append(rel)
    return sorted(out)


@dataclass
class Inputs:
    """一次检查用到的全部数据：都来自配置、清单、日志和需求文档，不含 AI 的任何文字（性质 16.4）。"""

    cfg: dict
    sources: list
    records: list
    valid: set  # 有效读取过的 (参考源, 单元)，所有会话
    docs: list  # 需求文档，相对路径
    cited: set  # 有效引用指向的 (参考源, 单元)
    phantom: tuple  # (文档, 需求编号)
    invalid: tuple  # (文档, 需求编号, "参考源/单元")
    unconverted: tuple  # (文档, 需求编号)
    required: object  # coverage.Required
    empty_docs: tuple = ()  # 命中配置、但一条需求都没解析出来的需求文档


def gather(store: Store) -> Inputs:
    from refcov import citations, coverage

    cfg = store.load_config()
    sources = _manifest(store)
    records = store.records()
    current = coverage.current_units(sources)
    valid = {(r.get("source"), r.get("unit")) for r in records
             if r.get("type") == "read" and coverage.is_valid(r, current)}
    known = set(current)
    docs = requirement_docs(store, cfg["requirements"])
    cited, phantom, invalid, unconverted, empty = set(), [], [], [], []
    for d in docs:
        try:
            text = (store.root / d).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as e:
            raise CheckError(f"需求文档读不了：{d}：{e}") from e
        res = citations.check_requirements(text, known)
        if not res.requirements:
            empty.append(d)
        cited.update(tuple(ref.split("/", 1)) for ref in res.cited)
        phantom.extend((d, n) for n in res.phantom)
        invalid.extend((d, n, ref) for n, ref in res.invalid)
        unconverted.extend((d, n) for n in res.unconverted)
    required = coverage.required_set(sources, _decls(store, sources), cfg["mode"], cfg["relax"], cited)
    return Inputs(cfg, sources, records, valid, docs, cited, tuple(phantom), tuple(invalid), tuple(unconverted),
                  required, tuple(empty))


def _titles(sources: list) -> dict:
    return {(s["id"], u["id"]): u.get("title", u["id"]) for s in sources for u in s.get("units", [])}


def _verdict(inp: Inputs, rel: str | None):
    """返回 (判断结果, 按路径的必看集合)。"""
    from refcov import coverage

    cfg = inp.cfg
    path_req = coverage.required_for_path(inp.required, inp.cited, rel, cfg["scope"] or [],
                                          {s["id"] for s in inp.sources})
    v = coverage.judge(inp.sources, path_req, inp.valid, cfg["mode"], inp.phantom, inp.invalid,
                       empty_docs=inp.empty_docs, spec_file=coverage.is_spec_file(rel, cfg["spec_files"]),
                       exempt=coverage.is_exempt(rel, cfg["exempt"]))
    return v, path_req


def _phantom_json(items) -> list:
    return [{"doc": d, "requirement": n} for d, n in items]


def _invalid_json(items) -> list:
    return [{"doc": d, "requirement": n, "ref": ref} for d, n, ref in items]


def check(store: Store, path=None) -> dict:
    """是否达标（设计 7 第 3–5 条）。`path` 是目标路径（相对仓库根目录或绝对路径）；不给时按全部参考源。

    达标不分会话（需求 5.7），只看有效读取、配置和需求文档。`enforce = false` 时照样给出判断，
    放不放行由关卡决定（任务 15）。
    """
    inp = gather(store)
    rel = None if path is None else store.rel(path)
    v, path_req = _verdict(inp, rel)
    titles = _titles(inp.sources)
    return {"path": rel, "mode": inp.cfg["mode"], "enforce": inp.cfg["enforce"], "pass": v.passed,
            "exempt": v.exempt, "spec_file": v.spec_file, "citations_checked": v.citations_checked,
            "required": len(path_req),
            "missing": [{"source": s, "unit": u, "title": titles.get((s, u), u)} for s, u in v.missing],
            "phantom_requirements": _phantom_json(v.phantom), "invalid_refs": _invalid_json(v.invalid),
            "requirement_docs": inp.docs, "requirement_patterns": list(inp.cfg["requirements"] or []),
            "empty_requirement_docs": list(v.empty_docs), "config_problems": _config_problems(inp)}


def _config_problems(inp: Inputs) -> list:
    from refcov import coverage

    return list(coverage.config_problems(inp.sources, inp.cfg["scope"] or [], inp.cfg["relax"],
                                         inp.cfg.get("string_lists") or ()))


def _config_problems_text(problems) -> str:
    """一段文字：配置有几处写错，逐处写位置、值和后果。"""
    items = "；".join(f"{p['where']} 的 {p['value']}：{p['note']}" for p in problems)
    return f"配置有 {len(problems)} 处写错（{items}）"


def _empty_docs_text(docs) -> str:
    return f"{'、'.join(docs)} 没解析出任何需求（标题格式不对？）"


def _no_docs_text(rep: dict) -> str:
    """没有找到需求文档时的提示：配置了模式但没匹配到文件，和根本没配置，分开写。不影响达标。"""
    if rep["requirement_patterns"]:
        return f"出处检查：配置了 {'、'.join(rep['requirement_patterns'])}，但没找到文件（不影响达标）。"
    return "出处检查：未配置需求文档（不影响达标）。"


def _cited_problems(rep: dict) -> str:
    """严格模式下让出处检查不通过的东西，一段文字；没有时为空。"""
    parts = []
    if rep["empty_requirement_docs"]:
        parts.append(_empty_docs_text(rep["empty_requirement_docs"]))
    if rep["phantom_requirements"]:
        parts.append(f"幻影需求 {len(rep['phantom_requirements'])} 条")
    if rep["invalid_refs"]:
        parts.append(f"无效引用 {len(rep['invalid_refs'])} 条")
    return "、".join(parts)


def check_text(res: dict, limit: int | None = None) -> str:
    """`check` 结果的文字版（命令行和 MCP 工具共用）。`limit` 给了就只列前几个还差的单元，另写总数。"""
    target = res["path"] or "全部参考源"
    mode = MODE_NAMES.get(res["mode"], res["mode"])
    if res["exempt"]:
        head = f"{target}：豁免路径，写这个文件不检查是否达标"
    else:
        head = f"{target}：{'达标' if res['pass'] else '未达标'}"
    lines = [f"RefCov {mode} {head}" + ("（关卡已关闭，只作参考）" if not res["enforce"] else "")]
    miss = res["missing"]
    if miss:
        shown = miss if limit is None else miss[:limit]
        more = f"（只列前 {len(shown)} 个）" if len(shown) < len(miss) else ""
        lines.append(f"必看 {res['required']} 个，还差 {len(miss)} 个{more}：")
        lines.extend(f"  {m['source']}/{m['unit']}  {m['title']}" for m in shown)
    else:
        lines.append(f"必看 {res['required']} 个，都看过了。")
    if not res["requirement_docs"]:
        lines.append(_no_docs_text(res))
    else:
        note = ("算进达标" if res["citations_checked"] else
                "规格文件，不因此不达标" if res["spec_file"] else "轻量模式，只列出")
        lines.append(f"出处检查（{note}）：幻影需求 {len(res['phantom_requirements'])} 条，"
                     f"无效引用 {len(res['invalid_refs'])} 条")
        if res["empty_requirement_docs"]:
            lines.append(f"  {_empty_docs_text(res['empty_requirement_docs'])}")
        lines.extend(f"  幻影需求：{p['doc']} 需求 {p['requirement']}" for p in res["phantom_requirements"])
        lines.extend(f"  无效引用：{i['doc']} 需求 {i['requirement']}：{i['ref']}" for i in res["invalid_refs"])
    if res["config_problems"]:
        lines.append(_config_problems_text(res["config_problems"]) + "。")
    lines.append(HINT)
    return "\n".join(lines)


# ---- 写文件关卡（任务 15，需求 9.1、11.2、17.1）----

GATE_FIRST = 20  # 拦截原因里列出还差的前几个单元


def _gate_reason(res: dict, count: int, recorded: bool) -> str:
    """拦截原因：还差的单元（前 20 个和总数）、严格模式下的出处问题、配置写错的地方；第 2 次起要求停下。"""
    miss = res["missing"]
    parts = [f"RefCov 写文件关卡：写 {res['path']} 之前要看完 {res['required']} 个必看单元"]
    if miss:
        shown = miss[:GATE_FIRST]
        more = f"（只列前 {len(shown)} 个）" if len(shown) < len(miss) else ""
        parts.append(f"，还差 {len(miss)} 个{more}：" + "、".join(f"{m['source']}/{m['unit']}" for m in shown) + "。")
    else:
        parts.append("，单元都看过了。")
    if res["citations_checked"]:
        cites = []
        if res["phantom_requirements"]:
            cites.append("幻影需求：" + "、".join(f"{p['doc']} 需求 {p['requirement']}"
                                              for p in res["phantom_requirements"]))
        if res["invalid_refs"]:
            cites.append("无效引用：" + "、".join(f"{i['doc']} 需求 {i['requirement']}：{i['ref']}"
                                              for i in res["invalid_refs"]))
        if res["empty_requirement_docs"]:
            cites.append(_empty_docs_text(res["empty_requirement_docs"]))
        if cites:
            parts.append("严格模式下出处检查不通过（" + "；".join(cites) + "）。")
    if res["config_problems"]:
        parts.append(_config_problems_text(res["config_problems"]) + "。")
    parts.append("用 RefCov 的 MCP 工具 read_unit 读完还差的单元再写；不要换别的工具或 shell 绕过。")
    if count >= 2:
        parts.append(f"这是本会话第 {count} 次在这个文件上被拦：停下来，向用户说明情况。")
    if not recorded:
        parts.append("（这次拦截没能记进日志。）")
    return "".join(parts)


def check_write(store: Store, path, session: str | None) -> dict:
    """写文件关卡（需求 9.1）：只按目标路径判断（需求 8.5），没有正文参数。

    放行：`enforce = false`（需求 17.1）、豁免路径、达标。放行时什么都不写。
    拦截：追加一条 `block` 记录（gate、target、count、missing），返回原因。`count` 是同一会话在同一目标上
    第几次被拦（路径不分大小写比较），第 2 次起原因里要求停下来向用户说明（需求 11.2）。
    拿不到日志锁时照样拦，只是不记录。
    """
    res = check(store, path)
    out = {"allow": True, "reason": None, "count": 0, "enforce": res["enforce"], "path": res["path"]}
    if not res["enforce"] or res["pass"]:
        return out
    target = res["path"]
    missing = [f"{m['source']}/{m['unit']}" for m in res["missing"]]

    def earlier(records) -> int:
        return sum(1 for r in records if r.get("type") == "block" and r.get("gate") == "write"
                   and r.get("session") == session and str(r.get("target", "")).lower() == target.lower())

    count, recorded = _record_block(store, earlier, session, gate="write", target=target, missing=missing)
    out.update(allow=False, count=count, reason=_gate_reason(res, count, recorded))
    return out


def _record_block(store: Store, earlier, session: str | None, gate: str, target: str,
                  missing: list) -> tuple[int, bool]:
    """结论已经是不达标时追加 block 记录，返回 (第几次被拦, 记没记上)。

    这一步出任何异常都照样拦，只是原因里写"没能记进日志"（外部审计 2026-11-12：会话 ID 含孤立代理字符时
    UTF-8 编码失败，原先这个异常逃出去，被钩子当成关卡出错放行）。降级时再数一次次数，也数不出就按第 1 次算。
    """
    count = None
    try:
        with store.locked():
            count = earlier(store.records()) + 1
            store.append_locked("block", session, gate=gate, target=target, count=count, missing=missing)
        return count, True
    except Exception:
        pass
    if count is None:
        try:
            count = earlier(store.records()) + 1
        except Exception:
            count = 1
    return count, False


# ---- 任务开工关卡（任务 16，需求 9.6、9.7，设计 7 第 6 条）----

@dataclass
class TaskNeeds:
    """一个任务要读什么（只读解析，不写任何记录）。"""

    tasks_file: str  # 相对仓库根目录
    task: object  # citations.Task；找不到任务时为 None
    refs: list  # 要读的 (参考源, 单元)：任务自己的引用 + 所列需求块里的引用
    unknown_requirements: list  # 任务列了、但需求文档里找不到的需求编号
    requirement_doc: str | None  # 用到的需求文档；没有可用的为 None
    requirement_doc_note: str | None  # 为什么没有可用的需求文档


def task_needs(store: Store, tasks_file, task_name: str, inp: Inputs | None = None) -> TaskNeeds:
    """找任务、算它要读的单元（设计 7 第 6 条）。只读，不追加记录。

    - tasks.md 必须在仓库里、文件名是 tasks.md（不分大小写），否则抛 CheckError（不算找不到任务）。
    - 需求块只从同一文件夹的 requirements.md 找，而且它必须命中配置的 `requirements`（偏离设计原文，补充）。
      找不到可用的需求文档时，任务列的需求编号全算"找不到"。
    - tasks.md、requirements.md 读不了都抛 CheckError。
    """
    import posixpath

    from refcov import citations

    rel = store.rel(tasks_file)
    if rel == ".." or rel.startswith("../") or os.path.isabs(rel) or re.match(r"^[A-Za-z]:", rel):
        raise CheckError(f"tasks.md 不在仓库里：{tasks_file}")
    if posixpath.basename(rel).lower() != "tasks.md":
        raise CheckError(f"不是 tasks.md：{rel}")
    try:
        text = (store.root / rel).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise CheckError(f"tasks.md 读不了：{rel}：{e}") from e
    task = citations.find_task(citations.parse_tasks(text), task_name)
    if task is None:
        return TaskNeeds(rel, None, [], [], None, None)
    inp = inp or gather(store)
    req_rel = posixpath.join(posixpath.dirname(rel), "requirements.md")
    reqs, doc, note = [], None, None
    if not (store.root / req_rel).is_file():
        note = f"同一文件夹里没有 {req_rel}"
    elif req_rel.lower() not in {d.lower() for d in inp.docs}:
        note = f"{req_rel} 不在配置的 requirements 里"
    else:
        try:
            reqs = citations.parse_requirements((store.root / req_rel).read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError) as e:
            raise CheckError(f"需求文档读不了：{req_rel}：{e}") from e
        doc = req_rel
    refs, unknown = citations.task_refs(task, reqs)
    return TaskNeeds(rel, task, refs, unknown, doc, note)


def check_task(store: Store, tasks_file, task_name: str, session: str | None) -> dict:
    """任务开工前判断（需求 9.6、9.7，设计 7 第 6 条）：任务要读的单元都要有效读取过；严格模式下出处检查要通过，
    任务列的需求编号也都要在需求文档里找得到（需求 6.4、6.6 同一处理）。不分会话（需求 5.7）。

    - 找不到任务：放行，追加 `task_not_found`（需求 9.7），报告的 tasks_not_found 里列出。
    - `enforce = false`：放行（需求 17.1）。
    - 不达标：追加 `block`（gate 是 task，target 是 "<tasks.md>#<任务标题>"）。
    - 只读 tasks.md 和需求文档，不改它们。路径不对、文件读不了时抛 CheckError（钩子放行并记 errors.log）。
    """
    from refcov import citations

    inp = gather(store)
    needs = task_needs(store, tasks_file, task_name, inp)
    task, rel = needs.task, needs.tasks_file
    out = {"allow": True, "found": task is not None, "reason": None, "missing": [], "count": 0,
           "tasks_file": rel, "task": task.title if task else task_name,
           "unknown_requirements": list(needs.unknown_requirements), "requirement_doc": needs.requirement_doc}
    if task is None:
        try:
            store.append("task_not_found", session, tasks_file=rel, task=str(task_name)[:300])
        except (LockTimeout, StoreError, OSError):
            pass
        return out
    out["missing"] = [citations.ref_str(r) for r in needs.refs if r not in inp.valid]
    cites = []
    if inp.cfg["mode"] == "strict":
        if needs.unknown_requirements:
            where = needs.requirement_doc or needs.requirement_doc_note
            cites.append("、".join(f"任务列了需求 {n}，需求文档里没有" for n in needs.unknown_requirements)
                         + f"（{where}）")
        if inp.phantom:
            cites.append("幻影需求：" + "、".join(f"{d} 需求 {n}" for d, n in inp.phantom))
        if inp.invalid:
            cites.append("无效引用：" + "、".join(f"{d} 需求 {n}：{ref}" for d, n, ref in inp.invalid))
        if inp.empty_docs:
            cites.append(_empty_docs_text(inp.empty_docs))
    if not inp.cfg["enforce"] or (not out["missing"] and not cites):
        return out
    target = f"{rel}#{task.title}"

    def earlier(records) -> int:
        return sum(1 for r in records if r.get("type") == "block" and r.get("gate") == "task"
                   and r.get("session") == session and r.get("target") == target)

    count, recorded = _record_block(store, earlier, session, gate="task", target=target, missing=out["missing"])
    parts = [f"RefCov 任务开工关卡：任务“{task.title}”还不能开工。"]
    if out["missing"]:
        shown = out["missing"][:GATE_FIRST]
        more = f"（只列前 {len(shown)} 个）" if len(shown) < len(out["missing"]) else ""
        parts.append(f"要读的单元还差 {len(out['missing'])} 个{more}：" + "、".join(shown) + "。")
    if cites:
        parts.append("严格模式下出处检查不通过（" + "；".join(cites) + "）。")
    parts.append("用 RefCov 的 MCP 工具 read_unit 读完再开工。这个任务会停在“进行中”（[~]），"
                 "读完再点 Start task 前，可能要用户手动把它改回 [ ]。RefCov 不改 tasks.md。")
    if count >= 2:
        parts.append(f"这是本会话第 {count} 次在这个任务上被拦：停下来，向用户说明情况。")
    if not recorded:
        parts.append("（这次拦截没能记进日志。）")
    out.update(allow=False, count=count, reason="".join(parts))
    return out


# ---- 报告（任务 7、11，设计 3.5，需求 9.8、12.1–12.4）----
# 报告和状态行都只读：不拿锁、不写任何文件、不写日志记录。

MODE_NAMES = {"strict": "严格模式", "light": "轻量模式"}
STATUS_FIRST = 5  # 状态行列出还差的前几个


def report(store: Store, session: str | None = None) -> dict:
    """报告 JSON（设计 3.5）。`pass` 按全部参考源算（同 `check(store)`）。还没有的部分：
    tokens（任务 19）、blocks、writes、tasks_not_found、protected（任务 14–17）、files（任务 18）。

    `session` 为 None（MCP 拿不到会话、命令行没给 --session）时 session_available 为 false，
    各 read_session 字段为 null。另加 `requirement_docs`：找到的需求文档，为空时文字版写"未配置需求文档"。
    """
    from refcov import coverage
    from refcov.store import now_iso

    inp = gather(store)
    cfg = inp.cfg
    v, _ = _verdict(inp, None)
    data = coverage.summarize(inp.sources, inp.records, session, inp.required.units)
    lists = coverage.unit_lists(inp.sources, inp.required, inp.valid, inp.cited)
    chain_result = store.verify_chain()
    chain = {"ok": chain_result.ok, "lines": chain_result.lines}
    if not chain_result.ok:
        chain["broken_at"] = chain_result.broken_at  # 文字版要写"第 N 行起断开"（设计 3.2）
    if store.log_tail_partial():
        chain["partial_tail"] = True  # 末尾有别的进程正在写的半行，这次没算
    relax = cfg["relax"]
    return {"version": 1, "generated": now_iso(), "session": session, "session_available": session is not None,
            "mode": cfg["mode"], "enforce": cfg["enforce"], "pass": v.passed, **data,
            "ghost_units": list(lists.ghost), "not_required_units": list(lists.not_required),
            "ignored_units": list(lists.ignored),
            "phantom_requirements": _phantom_json(inp.phantom), "invalid_refs": _invalid_json(inp.invalid),
            "unconverted_requirements": _phantom_json(inp.unconverted),
            "relaxed": {"sources": list(relax.get("sources") or []), "kinds": list(relax.get("kinds") or []),
                        "units": list(relax.get("units") or []),
                        "cited_but_relaxed": list(inp.required.cited_but_relaxed)},
            "exempt": list(cfg["exempt"] or []), "config_mtime": store.config_mtime(),
            "requirement_docs": inp.docs, "requirement_patterns": list(cfg["requirements"] or []),
            "empty_requirement_docs": list(inp.empty_docs), "config_problems": _config_problems(inp),
            "tasks_not_found": [{"seq": r.get("seq"), "time": r.get("time"), "session": r.get("session"),
                                 "tasks_file": r.get("tasks_file"), "task": r.get("task")}
                                for r in inp.records if r.get("type") == "task_not_found"],
            "chain": chain}


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


def _head(rep: dict) -> str:
    """第一行开头（需求 17.2）：enforce = false 时写"关卡已关闭"，否则写模式和是否达标。"""
    if not rep["enforce"]:
        return f"RefCov 关卡已关闭（{_mode_name(rep)}，{'达标' if rep['pass'] else '未达标'}，只作参考）"
    return f"RefCov {_mode_name(rep)} {'达标' if rep['pass'] else '未达标'}"


def _join(items, limit=None) -> str:
    items = list(items)
    shown = items if limit is None else items[:limit]
    return "、".join(shown) + ("、…" if len(shown) < len(items) else "")


def report_text(rep: dict) -> str:
    """文字版报告，只从 JSON 生成（需求 12.3）。"""
    lines = [_head(rep)]
    if not rep["sources"]:
        lines.append("还没有登记任何参考源。")
    for s in rep["sources"]:
        sess = "不可用" if s["required_read_session"] is None else f"{s['required_read_session']}/{s['required']}"
        lines.append(f"{s['id']}：必看 本会话 {sess}，历史 {s['required_read_history']}/{s['required']}"
                     f"（共 {s['units']} 个单元，历史看过 {s['read_history']} 个）")
    if rep["missing"]:
        lines.append(f"还差 {len(rep['missing'])} 个（幽灵单元：必看但没看过）：" +
                     _join(f"{m['source']}/{m['unit']}" for m in rep["missing"]))
    else:
        lines.append("没有还差的单元。")
    lines.append(f"被忽略单元（看过但没被需求引用）{len(rep['ignored_units'])} 个" +
                 (f"：{_join(rep['ignored_units'])}" if rep["ignored_units"] else ""))
    lines.append(f"本模式未要求的单元 {len(rep['not_required_units'])} 个")
    if not rep["requirement_docs"]:
        lines.append(_no_docs_text(rep))
    else:
        effect = "算进达标" if rep["mode"] == "strict" else "轻量模式，只列出"
        lines.append(f"出处检查（{effect}）：{'、'.join(rep['requirement_docs'])}")
        if rep["empty_requirement_docs"]:
            lines.append(f"  {_empty_docs_text(rep['empty_requirement_docs'])}")
        lines.append(f"  幻影需求 {len(rep['phantom_requirements'])} 条" + (
            "：" + _join(f"{p['doc']} 需求 {p['requirement']}" for p in rep["phantom_requirements"])
            if rep["phantom_requirements"] else ""))
        lines.append(f"  无效引用 {len(rep['invalid_refs'])} 条" + (
            "：" + _join(f"{i['doc']} 需求 {i['requirement']}：{i['ref']}" for i in rep["invalid_refs"])
            if rep["invalid_refs"] else ""))
        lines.append(f"  未转换（文字出处，不算幻影需求）{len(rep['unconverted_requirements'])} 条")
    rx = rep["relaxed"]
    relaxed = [*(f"参考源 {x}" for x in rx["sources"]), *(f"类型 {x}" for x in rx["kinds"]), *rx["units"]]
    lines.append(f"放宽项：{_join(relaxed) if relaxed else '无'}")
    if rx["cited_but_relaxed"]:
        lines.append(f"  在放宽范围内但被需求引用、仍然必看：{_join(rx['cited_but_relaxed'])}")
    lines.append(f"豁免：{_join(rep['exempt']) if rep['exempt'] else '无'}")
    if rep["config_problems"]:
        lines.append(_config_problems_text(rep["config_problems"]) + "。")
    lines.append(f"配置文件：{'没有 refcov.toml，用默认值' if rep['config_mtime'] is None else '修改于 ' + rep['config_mtime']}")
    tnf = rep["tasks_not_found"]
    lines.append(f"任务未找到，未检查：{len(tnf)} 次" +
                 ("：" + _join(f"{t['tasks_file']} 的“{t['task']}”" for t in tnf[-5:]) if tnf else ""))
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
    """一行简短报告（需求 9.8、12.4），由报告 JSON 生成。达标按全部参考源算，不分会话（需求 5.7）。"""
    rep = report(store, session)
    if not rep["sources"]:
        return f"RefCov {_mode_name(rep)}：还没有登记参考源。{HINT}"
    head = f"{_head(rep)}："
    total, hist, sess = _totals(rep)
    sess_text = "不可用" if sess is None else f"{sess}/{total}"
    text = f"{head}必看单元 本会话 {sess_text}，历史 {hist}/{total}；"
    missing = rep["missing"]
    if missing:
        first = "、".join(f"{m['source']}/{m['unit']}" for m in missing[:STATUS_FIRST])
        more = "、…" if len(missing) > STATUS_FIRST else ""
        text += f"还差 {len(missing)} 个：{first}{more}。"
    else:
        text += "没有还差的单元。"
    problems = _cited_problems(rep)
    if problems:
        text += f"{problems}（{'算进达标' if rep['mode'] == 'strict' else '轻量模式，只列出'}）。"
    if rep["config_problems"]:
        text += _config_problems_text(rep["config_problems"]) + "。"
    if not rep["chain"]["ok"]:
        text += f"日志哈希链{_chain_text(rep['chain'])}。"
    return text + HINT
