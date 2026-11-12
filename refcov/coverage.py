"""纯计算（设计 7）：输入是清单里的参考源、日志记录、配置和出处解析结果，不读文件。

- 有效读取、覆盖率（任务 7）。
- 必看集合（设计 7 第 2 条，需求 5.1、5.3、15.2）：`required_set`。
- 按路径（设计 7 第 3 条，需求 8.1–8.3、6.5）：`scope_sources`、`required_for_path`、`is_exempt`、`is_spec_file`；
  配置写错的提示：`config_problems`。
"""

from __future__ import annotations

from dataclasses import dataclass

from refcov.store import path_matches  # 只是字符串匹配，不读文件

UNKNOWN = "unknown"

Unit = tuple[str, str]  # (参考源 ID, 单元 ID)


def unit_str(u: Unit) -> str:
    return f"{u[0]}/{u[1]}"


# ---- 必看集合（设计 7 第 2 条）----

@dataclass(frozen=True)
class Decl:
    """单元类型的声明，和 `refcov.sources.KindDecl` 同样的两个字段（只要有 strict、key 属性就行）。"""

    strict: bool
    key: bool = False


# 清单里的类型在适配器声明里找不到时：按严格必看、不是关键类型处理，宁可多要求（用户 2026-11-12 同意）
UNKNOWN_KIND = Decl(strict=True, key=False)


@dataclass(frozen=True)
class Required:
    units: frozenset  # 必看集合：(参考源, 单元)
    relaxed: frozenset  # 基础集合里被放宽项移走的单元（不含被引用、因而仍必看的）
    cited_but_relaxed: tuple  # 在放宽范围内、但被需求引用所以仍必看的单元，"参考源/单元"，按清单顺序


def _decl(decls: dict, adapter: str | None, kind: str | None):
    return (decls.get(adapter) or {}).get(kind) or UNKNOWN_KIND


def in_relax(source: str, unit: dict, relax: dict) -> bool:
    """这个单元在不在放宽范围里：参考源、单元类型或"参考源/单元"任一命中。"""
    return (source in (relax.get("sources") or ())
            or unit.get("kind") in (relax.get("kinds") or ())
            or f"{source}/{unit['id']}" in (relax.get("units") or ()))


def required_set(sources: list[dict], decls: dict, mode: str, relax: dict, cited) -> Required:
    """必看集合 = 基础集合 − 放宽项 + 被需求引用的单元（需求 5.1，两种模式同一条规则）。

    - `sources`：清单里的参考源（含 `adapter` 和 `units`，单元含 `kind`）。
    - `decls`：适配器名 → {单元类型 → 声明}。找不到的按 `UNKNOWN_KIND`。
    - `mode`：`strict` 取严格必看类型的单元；`light` 取关键类型的单元（需求 15.2）。
    - `relax`：配置的 `[relax]`，含 `sources`、`kinds`、`units`（"参考源/单元"）。只能缩小基础集合（需求 5.3）。
    - `cited`：需求文档里有效引用指向的 (参考源, 单元)。永远必看，放宽项移不掉；不在清单里的忽略。
    """
    if mode not in ("strict", "light"):
        raise ValueError(f"mode 只能是 strict 或 light，现在是 {mode!r}")
    cited = set(cited)
    base, relaxed, all_units, cited_relaxed = set(), set(), [], []
    for s in sources:
        for u in s.get("units", []):
            key = (s["id"], u["id"])
            all_units.append(key)
            d = _decl(decls, s.get("adapter"), u.get("kind"))
            if in_relax(s["id"], u, relax):
                if key in cited:
                    cited_relaxed.append(unit_str(key))
                elif d.strict if mode == "strict" else d.key:
                    relaxed.add(key)
                continue
            if d.strict if mode == "strict" else d.key:
                base.add(key)
    units = base | (cited & set(all_units))
    return Required(frozenset(units), frozenset(relaxed), tuple(cited_relaxed))


# ---- 按路径（设计 7 第 3 条，需求 8.1–8.4、6.5、6.7）----

def scope_sources(rel: str | None, scopes: list[dict], known=None) -> frozenset | None:
    """路径命中的 `[[scope]]` 的参考源并集；一条都不命中（或不给路径）时返回 None，表示全部参考源（需求 8.2）。

    `rel` 是相对仓库根目录的路径。匹配规则和配置里其他路径一样：转小写、`/` 分隔、`fnmatchcase`。
    `known` 是清单里的参考源 ID：给了时，命中的规则里只要有一个不存在的参考源，就按全部参考源处理
    （宁可多要求，不因写错变宽松；外部审阅 2026-11-12）。`sources = []` 保持原样（用户 2026-11-12 定）。
    """
    if rel is None:
        return None
    hit = [sc for sc in scopes if path_matches(rel, sc.get("paths") or ())]
    if not hit:
        return None
    srcs = frozenset(src for sc in hit for src in (sc.get("sources") or ()))
    if known is not None and not srcs <= set(known):
        return None
    return srcs


def required_for_path(required: Required, cited, rel: str | None, scopes: list[dict], known=None) -> frozenset:
    """按路径的必看集合：必看集合限定在命中的 scope 参考源内，再并上全部被引用的单元（需求 6.5，不论在哪个参考源）。"""
    srcs = scope_sources(rel, scopes, known)
    if srcs is None:
        return required.units
    return frozenset(u for u in required.units if u[0] in srcs) | (frozenset(cited) & required.units)


def config_problems(sources: list[dict], scopes: list[dict], relax: dict) -> tuple:
    """配置里 scope 和 relax 写了清单里没有的东西（外部审阅 2026-11-12）。每项 {where, value, note}，按配置顺序。

    scope 写错按全部参考源处理（见 `scope_sources`）；relax 写错本来不会变宽松，只提示，不改判断。
    """
    ids = {s["id"] for s in sources}
    units = {f"{s['id']}/{u['id']}" for s in sources for u in s.get("units", [])}
    kinds = {u.get("kind") for s in sources for u in s.get("units", [])}
    out = []
    for i, sc in enumerate(scopes or [], start=1):
        where = f"scope 第 {i} 条 sources"
        srcs = list(sc.get("sources") or [])
        for src in srcs:
            if src not in ids:
                out.append({"where": where, "value": src, "note": "清单里没有这个参考源，这条规则按全部参考源处理"})
        if not srcs:
            out.append({"where": where, "value": "[]", "note": "sources 为空，这条规则只要求被引用的单元"})
    relax = relax or {}
    for key, known, what in (("sources", ids, "参考源"), ("kinds", kinds, "单元类型"), ("units", units, "单元")):
        for v in relax.get(key) or []:
            if v not in known:
                out.append({"where": f"relax.{key}", "value": str(v), "note": f"清单里没有这个{what}，只提示，不改判断"})
    return tuple(out)


def is_exempt(rel: str | None, exempt) -> bool:
    """写这个文件不检查是否达标（需求 8.3）。不给路径时不豁免。"""
    return rel is not None and path_matches(rel, exempt or ())


def is_spec_file(rel: str | None, spec_files) -> bool:
    """目标是不是规格文件（需求 6.7）：是的话跳过严格模式的出处检查，其余照常。"""
    return rel is not None and path_matches(rel, spec_files or ())


def call_sessions(records: list[dict]) -> dict[str, str]:
    """调用编号 → 会话：取每个调用编号的第一条 session 补记（需求 4.5）。"""
    out: dict[str, str] = {}
    for r in records:
        if r.get("type") == "session" and r.get("call") and r.get("session"):
            out.setdefault(r["call"], r["session"])
    return out


def read_session(rec: dict, by_call: dict[str, str]) -> str | None:
    """一条 read 记录属于哪个会话：本行的 session；为 null 时按调用编号对上的补记；都没有为 None。"""
    return rec.get("session") or by_call.get(rec.get("call"))


def current_units(sources: list[dict]) -> dict[tuple[str, str], str]:
    """(参考源, 单元) → 清单里当前的校验值。"""
    return {(s["id"], u["id"]): u["sha256"] for s in sources for u in s.get("units", [])}


def is_valid(rec: dict, current: dict[tuple[str, str], str]) -> bool:
    """有效读取：read 记录的 unit_sha256 等于清单里该单元当前的校验值（需求 1.4）。"""
    return current.get((rec.get("source"), rec.get("unit"))) == rec.get("unit_sha256")


def summarize(sources: list[dict], records: list[dict], session: str | None, required=None) -> dict:
    """算报告 JSON 里的 sources、missing、unknown_session_calls、by_session（设计 3.5）。

    `session` 为 None 时（MCP、命令行没给 --session）各 read_session 字段为 None。
    `required` 是必看集合（不按路径）；不给时必看 = 全部单元。`missing` 是必看但没有有效读取的单元。
    """
    current = current_units(sources)
    by_call = call_sessions(records)
    reads = [r for r in records if r.get("type") == "read"]

    seen_history: set[tuple[str, str]] = set()
    seen_session: set[tuple[str, str]] = set()
    per_session: dict[str, dict] = {}
    unknown_calls = 0
    for r in reads:
        sess = read_session(r, by_call)
        if sess is None:
            unknown_calls += 1
        key = sess or UNKNOWN
        row = per_session.setdefault(key, {"session": key, "first": r.get("time"), "units": set(),
                                           "blocks": 0, "text_units": 0, "images": 0})
        row["text_units"] += int(r.get("text_units") or 0)
        row["images"] += int(r.get("images") or 0)
        if is_valid(r, current):
            unit = (r["source"], r["unit"])
            seen_history.add(unit)
            row["units"].add(unit)
            if session is not None and sess == session:
                seen_session.add(unit)
    for r in records:
        if r.get("type") == "block":
            key = r.get("session") or UNKNOWN
            if key in per_session:
                per_session[key]["blocks"] += 1

    out_sources, missing = [], []
    for s in sources:
        units = [(s["id"], u["id"]) for u in s.get("units", [])]
        req = units if required is None else [u for u in units if u in required]
        hist = sum(u in seen_history for u in units)
        sess_n = None if session is None else sum(u in seen_session for u in units)
        out_sources.append({"id": s["id"], "units": len(units), "read_history": hist, "read_session": sess_n,
                            "required": len(req), "required_read_history": sum(u in seen_history for u in req),
                            "required_read_session": None if session is None else
                            sum(u in seen_session for u in req)})
        for u in s.get("units", []):
            key = (s["id"], u["id"])
            if key not in seen_history and (required is None or key in required):
                missing.append({"source": s["id"], "unit": u["id"], "title": u["title"]})

    known = [r for k, r in per_session.items() if k != UNKNOWN]
    known.sort(key=lambda r: r["first"] or "")
    by_session = [{"session": r["session"], "first": r["first"], "units_read": len(r["units"]),
                   "blocks": r["blocks"], "text_units": r["text_units"], "images": r["images"]} for r in known]
    u = per_session.get(UNKNOWN)
    by_session.append({"session": UNKNOWN, "units_read": len(u["units"]) if u else 0,
                       "blocks": u["blocks"] if u else 0, "text_units": u["text_units"] if u else 0,
                       "images": u["images"] if u else 0})
    return {"sources": out_sources, "missing": missing, "unknown_session_calls": unknown_calls,
            "by_session": by_session}


# ---- 达标（设计 7 第 4、5 条，需求 5.6、6.5–6.7、8.3）----

@dataclass(frozen=True)
class Verdict:
    passed: bool
    missing: tuple  # 按路径的必看集合里没有有效读取的单元，(参考源, 单元)，按清单顺序
    phantom: tuple  # 幻影需求，(需求文档, 需求编号)；两种模式都列出
    invalid: tuple  # 无效引用，(需求文档, 需求编号, "参考源/单元")；两种模式都列出
    citations_checked: bool  # 第 4 步有没有算进达标：严格模式且目标不是规格文件
    citations_fail: bool  # 第 4 步不通过（只在 citations_checked 时可能为真）
    exempt: bool  # 目标在豁免路径里：不检查是否达标，passed 一律为真
    spec_file: bool
    empty_docs: tuple = ()  # 命中配置、但一条需求都没解析出来的需求文档；两种模式都列出


def _ordered(sources: list[dict], units) -> tuple:
    units = set(units)
    return tuple((s["id"], u["id"]) for s in sources for u in s.get("units", []) if (s["id"], u["id"]) in units)


def judge(sources: list[dict], required_path, valid, mode: str, phantom=(), invalid=(), *,
          empty_docs=(), spec_file: bool = False, exempt: bool = False) -> Verdict:
    """达标 = 按路径的必看集合 ⊆ 有效读取，且出处检查通过（设计 7 第 5 条）。不分会话（需求 5.7）。

    - `required_path`：`required_for_path` 的结果。被引用的单元都在里面，所以引用了没读的单元一定不达标（需求 6.5）。
    - `valid`：有效读取过的单元（历史上，所有会话）。
    - 出处检查（第 4 条，需求 6.6、6.7）：严格模式下有幻影需求或无效引用就不达标；轻量模式只列出；
      目标是规格文件时不因此不达标。"未转换"不在这里，它从不影响达标。
    - `empty_docs`：命中配置、但一条需求都没解析出来的需求文档（标题格式不对时会这样）。和幻影需求同样处理：
      严格模式不达标，轻量模式只列出，规格文件不因此不达标。这条比需求 6.6 原文多（偏离需求原文）。
    - 豁免路径（需求 8.3）：不检查是否达标，`passed` 为真；还差的单元照样列出，只作参考。
    只看单元、记录和配置，不看任何文字（需求 8.5、性质 16.4）。
    """
    if mode not in ("strict", "light"):
        raise ValueError(f"mode 只能是 strict 或 light，现在是 {mode!r}")
    missing = _ordered(sources, set(required_path) - set(valid))
    phantom, invalid, empty_docs = tuple(phantom), tuple(invalid), tuple(empty_docs)
    checked = mode == "strict" and not spec_file
    cit_fail = checked and bool(phantom or invalid or empty_docs)
    passed = exempt or (not missing and not cit_fail)
    return Verdict(passed, missing, phantom, invalid, checked, cit_fail, exempt, spec_file, empty_docs)


@dataclass(frozen=True)
class UnitLists:
    ghost: tuple  # 幽灵单元：必看但从没有效读取过（需求 6.3）
    ignored: tuple  # 被忽略单元：有效读取过、但没被任何需求引用（需求 6.3）
    not_required: tuple  # 本模式未要求的单元：不在必看集合里


def unit_lists(sources: list[dict], required: Required, valid, cited) -> UnitLists:
    """按全部参考源（不按路径）列出三类单元，都是"参考源/单元"字符串，按清单顺序。"""
    req, valid, cited = set(required.units), set(valid), set(cited)
    every = _ordered(sources, {(s["id"], u["id"]) for s in sources for u in s.get("units", [])})
    return UnitLists(
        tuple(unit_str(u) for u in every if u in req and u not in valid),
        tuple(unit_str(u) for u in every if u in valid and u not in cited),
        tuple(unit_str(u) for u in every if u not in req),
    )
