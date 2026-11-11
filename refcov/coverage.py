"""纯计算（设计 7）：输入是清单里的参考源和日志记录，不读文件。

任务 7 这一步只算有效读取和覆盖率：必看 = 全部单元，还不算必看集合（放宽项、引用在任务 10）。
"""

from __future__ import annotations

UNKNOWN = "unknown"


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


def summarize(sources: list[dict], records: list[dict], session: str | None) -> dict:
    """算报告 JSON 里的 sources、missing、unknown_session_calls、by_session（设计 3.5）。

    `session` 为 None 时（MCP、命令行没给 --session）各 read_session 字段为 None。
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
        hist = sum(u in seen_history for u in units)
        sess_n = None if session is None else sum(u in seen_session for u in units)
        out_sources.append({"id": s["id"], "units": len(units), "read_history": hist, "read_session": sess_n,
                            "required": len(units), "required_read_history": hist,
                            "required_read_session": sess_n})
        for u in s.get("units", []):
            if (s["id"], u["id"]) not in seen_history:
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
