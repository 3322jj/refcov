"""需求 16 的属性测试（任务 12，设计 9）。

- 16.1、16.2、16.3、16.5、16.6：Hypothesis 直接生成设计 7 纯函数的输入（参考源、类型声明、读取记录、需求文档、
  配置），判断用产品自己的 `api._verdict`（和 `api.check` 同一个），不经过文件。
- 16.4：每个例子在函数里自己建临时仓库（tempfile，不用 pytest 的 tmp_path，免得触发 Hypothesis 的健康检查），
  走 `api.check` / `api.check_write` 的完整读文件路径。

单元 ID 的 3 条性质在任务 3 已经写了（tests/test_sources.py 的 test_prop_*），这里不重写。
所有测试 deadline=None（Windows 的 CI 慢，时限只会让 CI 偶尔无故变红）；不固定随机种子。
"""

import json
import tempfile
from pathlib import Path

from hypothesis import event, given, settings, strategies as st

from refcov import api, citations, coverage
from refcov.sources import KindDecl, assign_ids
from refcov.store import Store

KINDS = ("section", "shot", "crs", "extent", "fields", "validity", "sample")  # 设计 9
ADAPTERS = ("markdown", "video", "gis")
SESSIONS = ("sess_a", "sess_b", "sess_c")
DOC = ".kiro/specs/x/requirements.md"
# 目标路径都不在豁免模式（只从 docs/ 下生成）里；None 表示按全部参考源（16.3 要排除豁免路径）
TARGETS = ("src/code.py", "integrations/kiro/hook.py", ".kiro/specs/x/tasks.md", None)
SCOPE_PATHS = ("src/**", "integrations/kiro/**", ".kiro/specs/**", "**")
EXEMPT_PATHS = ("docs/**", "docs/*.md", "docs/decisions/**", "docs/DEVLOG.md")

# 标题：中文、各种空白、方括号、@、emoji、重名、本身以 -2 结尾（testing.md、设计 9）
_TITLE_CHARS = st.one_of(st.sampled_from(list("退出码钩子 \t\u3000[]@-2aA😀")), st.characters(codec="utf-8"))
titles = st.one_of(st.text(_TITLE_CHARS, max_size=10),
                   st.sampled_from(["退出码", "退出码-2", "图层 [坐标系]", "a@b", "a"]))
source_ids = st.from_regex(r"[a-z0-9][a-z0-9-]{0,5}", fullmatch=True)
ai_texts = st.text(st.characters(codec="utf-8"), max_size=60)  # 合法 UTF-8 的任意文字


def _sha(i: int) -> str:
    return f"{i:064x}"


@st.composite
def worlds(draw, kinds=KINDS, adapters=ADAPTERS):
    """一份完整输入：参考源和单元、类型声明、读取记录、需求文档文本、配置、目标路径。

    第一个参考源至少 1 个单元，需求文档至少引用一个存在的单元，16.3 才总有被引用的单元可选。
    """
    ids = draw(st.lists(source_ids, min_size=1, max_size=4, unique=True))
    sources, n = [], 0
    for i, sid in enumerate(ids):
        ts = draw(st.lists(titles, min_size=1 if i == 0 else 0, max_size=20))
        units = []
        for t, uid in zip(ts, assign_ids(ts)):  # 单元 ID 用产品的函数生成（设计 4）
            n += 1
            units.append({"id": uid, "title": t, "kind": draw(st.sampled_from(kinds)), "sha256": _sha(n)})
        sources.append({"id": sid, "adapter": draw(st.sampled_from(adapters)), "units": units})
    every = [(s["id"], u["id"]) for s in sources for u in s["units"]]
    sha = {(s["id"], u["id"]): u["sha256"] for s in sources for u in s["units"]}

    # 类型声明：随机严格必看；关键类型只从严格必看里抽（需求 2.4）；有的类型故意不声明（按 UNKNOWN_KIND）
    decls = {}
    for a in adapters:
        decls[a] = {}
        for k in kinds:
            if draw(st.booleans()) or len(kinds) == 1:
                strict = draw(st.booleans())
                decls[a][k] = KindDecl(strict=strict, key=strict and draw(st.booleans()))

    # 读取记录：可重复；一部分过期（校验值不对）；一部分指向不存在的单元；随机挂会话或不挂
    records = []
    for _ in range(draw(st.integers(0, 30))):
        if every and draw(st.integers(0, 9)) > 0:
            s, u = draw(st.sampled_from(every))
            h = sha[(s, u)] if draw(st.integers(0, 3)) > 0 else "stale" + sha[(s, u)][5:]
        else:
            s, u, h = "nope", "nope", _sha(0)
        records.append({"type": "read", "source": s, "unit": u, "unit_sha256": h,
                        "session": draw(st.sampled_from(SESSIONS + (None,))), "call": f"c-{len(records) + 1}",
                        "text_units": 1, "images": 0})
    # 一半的例子每个单元都补一次有效读取，否则几乎凑不出达标，16.4、16.6 会空转
    if draw(st.booleans()):
        for s, u in every:
            records.append({"type": "read", "source": s, "unit": u, "unit_sha256": sha[(s, u)],
                            "session": draw(st.sampled_from(SESSIONS + (None,))),
                            "call": f"c-{len(records) + 1}", "text_units": 1, "images": 0})

    # 需求文档：随机条数，每块 0–3 个引用，混入不存在的单元、没有引用的块、文字出处。
    # 一半的例子只写有效引用、每块至少一个（出处检查能通过），理由同上
    clean = draw(st.booleans())
    bad = [] if clean else [st.just(("nope", "x"))]
    blocks = []
    for no in range(1, draw(st.integers(0, 6)) + 2):
        refs = draw(st.lists(st.one_of(st.sampled_from(every), *bad), max_size=3))
        if no == 1 or clean:
            refs = [draw(st.sampled_from(every))] + refs
        line = " ".join(f"[ref:{s}/{u}]" for s, u in refs)
        if draw(st.booleans()):
            line += " 交接说明·某一节"
        blocks.append(f"### 需求 {no}：标题\n正文\n" + (f"出处：{line}\n" if line.strip() else ""))
    req_text = "\n".join(blocks)

    relax = {"sources": draw(st.lists(st.sampled_from(ids + ["nope"]), max_size=2)),
             "kinds": draw(st.lists(st.sampled_from(kinds), max_size=2)),
             "units": draw(st.lists(st.sampled_from([f"{s}/{u}" for s, u in every] or ["x/y"]), max_size=3))}
    scope = [{"paths": [draw(st.sampled_from(SCOPE_PATHS))],
              "sources": draw(st.lists(st.sampled_from(ids + ["nope"]), max_size=3))}
             for _ in range(draw(st.integers(0, 3)))]
    cfg = {"mode": draw(st.sampled_from(["strict", "light"])), "enforce": True,
           "requirements": [".kiro/specs/*/requirements.md"],
           "spec_files": draw(st.sampled_from([[], [".kiro/specs/**"]])),
           "exempt": draw(st.lists(st.sampled_from(EXEMPT_PATHS), max_size=3)),
           "relax": relax, "scope": scope}
    return {"sources": sources, "decls": decls, "records": records, "req_text": req_text, "cfg": cfg,
            "target": draw(st.sampled_from(TARGETS))}


def inputs(w, mode=None, records=None, relax=None) -> api.Inputs:
    """按 `api.gather` 的同样步骤，从一份生成的输入拼出 `api.Inputs`（不读文件）。

    "有效读取"那一行和 `gather` 里的相同；`gather` 本身由 16.4 经临时仓库测到。
    """
    mode = mode or w["cfg"]["mode"]
    records = w["records"] if records is None else records
    cfg = dict(w["cfg"], mode=mode, relax=w["cfg"]["relax"] if relax is None else relax)
    current = coverage.current_units(w["sources"])
    valid = {(r.get("source"), r.get("unit")) for r in records
             if r.get("type") == "read" and coverage.is_valid(r, current)}
    res = citations.check_requirements(w["req_text"], set(current))
    cited = {tuple(ref.split("/", 1)) for ref in res.cited}
    required = coverage.required_set(w["sources"], w["decls"], mode, cfg["relax"], cited)
    return api.Inputs(cfg, w["sources"], records, valid, [DOC], cited,
                      tuple((DOC, n) for n in res.phantom), tuple((DOC, n, r) for n, r in res.invalid),
                      tuple((DOC, n) for n in res.unconverted), required,
                      () if res.requirements else (DOC,))


def verdict(w, **kw):
    v, _ = api._verdict(inputs(w, **kw), w["target"])
    return v


# ---- 16.1 ----

@settings(deadline=None)
@given(worlds(), st.sampled_from(SESSIONS + (None,)))
def test_prop_16_1_coverage_between_0_and_1(w, session):
    """性质 16.1：覆盖率和必看覆盖率（按历史、按会话）始终在 0% 到 100% 之间。"""
    inp = inputs(w)
    s = coverage.summarize(w["sources"], w["records"], session, inp.required.units)
    pairs = []
    for row in s["sources"]:
        pairs += [(row["read_history"], row["units"]), (row["required_read_history"], row["required"])]
        if session is not None:
            pairs += [(row["read_session"], row["units"]), (row["required_read_session"], row["required"])]
    rows = s["sources"]
    pairs += [(sum(r["read_history"] for r in rows), sum(r["units"] for r in rows)),
              (sum(r["required_read_history"] for r in rows), sum(r["required"] for r in rows))]
    for a, b in pairs:
        assert 0 <= a <= b
        assert 0.0 <= (a / b if b else 1.0) <= 1.0


# ---- 16.2 ----

@settings(deadline=None)
@given(worlds(), st.data())
def test_prop_16_2_repeated_reads_count_once(w, data):
    """性质 16.2：同一单元读多次只算一次：把某条读取记录再追加 1–5 次，覆盖率和结论不变。"""
    if not w["records"]:
        event("没有读取记录")
        return
    rec = data.draw(st.sampled_from(w["records"]))
    times = data.draw(st.integers(1, 5))
    more = w["records"] + [dict(rec, call=f"c-dup-{i}") for i in range(times)]
    event("重复的是有效读取" if coverage.is_valid(rec, coverage.current_units(w["sources"])) else "重复的是无效读取")
    session = data.draw(st.sampled_from(SESSIONS + (None,)))
    req = inputs(w).required.units
    before = coverage.summarize(w["sources"], w["records"], session, req)
    after = coverage.summarize(w["sources"], more, session, req)
    assert after["sources"] == before["sources"] and after["missing"] == before["missing"]
    assert verdict(w, records=more) == verdict(w)


# ---- 16.3 ----

@settings(deadline=None)
@given(worlds(), st.data())
def test_prop_16_3_cited_unread_unit_fails(w, data):
    """性质 16.3：需求引用了没有有效读取记录的单元，一定判定不达标，不论放宽项怎么设（需求 5.1）。

    目标路径都不在豁免路径里（豁免按需求 8.3 一律放行）：目标只从固定前缀里抽，豁免模式只在 docs/ 下。
    两种模式、规格文件与否、scope 都随机；那个单元还可能被故意放进放宽项。
    """
    assert not coverage.is_exempt(w["target"], w["cfg"]["exempt"])  # 生成器被改坏时当场报出来
    cited = sorted(inputs(w).cited)
    assert cited  # 生成器保证第 1 条需求引用一个存在的单元
    unit = data.draw(st.sampled_from(cited))
    # 去掉它的有效读取：要么删掉这些记录，要么都改成过期
    if data.draw(st.booleans()):
        records = [r for r in w["records"] if (r["source"], r["unit"]) != unit]
    else:
        records = [dict(r, unit_sha256="stale") if (r["source"], r["unit"]) == unit else r for r in w["records"]]
    relax = dict(w["cfg"]["relax"])
    if data.draw(st.booleans()):
        relax = {"sources": relax["sources"] + [unit[0]], "kinds": list(KINDS),
                 "units": relax["units"] + [f"{unit[0]}/{unit[1]}"]}
        event("这个单元也在放宽项里")
    for mode in ("strict", "light"):
        v = verdict(w, mode=mode, records=records, relax=relax)
        assert not v.passed, (mode, unit)
        assert unit in v.missing


# ---- 16.5、16.6 ----

@settings(deadline=None)
@given(worlds())
def test_prop_16_5_light_required_subset_of_strict(w):
    """性质 16.5：同样的单元和配置下，轻量模式的必看集合一定是严格模式必看集合的子集（按全部参考源和按路径都是）。"""
    light, strict = inputs(w, mode="light"), inputs(w, mode="strict")
    assert light.required.units <= strict.required.units
    _, light_path = api._verdict(light, w["target"])
    _, strict_path = api._verdict(strict, w["target"])
    assert light_path <= strict_path
    event("轻量比严格少" if light.required.units < strict.required.units else "两者相同")


@settings(deadline=None)
@given(worlds())
def test_prop_16_6_strict_pass_implies_light_pass(w):
    """性质 16.6：同样的记录下，严格模式达标，则轻量模式一定达标。"""
    strict, light = verdict(w, mode="strict"), verdict(w, mode="light")
    event(f"严格{'达标' if strict.passed else '不达标'}，轻量{'达标' if light.passed else '不达标'}")
    if strict.passed:
        assert light.passed


# ---- 16.4：经临时仓库走完整的读文件路径 ----

def _toml_str(s: str) -> str:
    """TOML 基本字符串：转义反斜杠、引号和控制字符（含 0x7F），其余原样（不用 \\u 写代理对）。"""
    out = []
    for ch in s:
        if ch in '"\\':
            out.append("\\" + ch)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _toml_list(xs) -> str:
    return "[" + ", ".join(_toml_str(x) for x in xs) + "]"


def _config_text(cfg: dict) -> str:
    lines = [f"mode = {_toml_str(cfg['mode'])}", "enforce = true",
             f"requirements = {_toml_list(cfg['requirements'])}", f"spec_files = {_toml_list(cfg['spec_files'])}",
             f"exempt = {_toml_list(cfg['exempt'])}", "", "[relax]"]
    lines += [f"{k} = {_toml_list(cfg['relax'][k])}" for k in ("sources", "kinds", "units")]
    for sc in cfg["scope"]:
        lines += ["", "[[scope]]", f"paths = {_toml_list(sc['paths'])}", f"sources = {_toml_list(sc['sources'])}"]
    return "\n".join(lines) + "\n"


def _make_repo(root: Path, w: dict, reads, noise=None) -> Store:
    """在 root 下建一个仓库：清单、配置、需求文档、日志。`noise` 是 AI 的文字（None 表示干净的一份）。"""
    (root / ".git").mkdir()
    (root / ".kiro" / "specs" / "x").mkdir(parents=True)
    (root / DOC).write_text(w["req_text"], encoding="utf-8")
    (root / "refcov.toml").write_text(_config_text(w["cfg"]), encoding="utf-8")
    store = Store(root)
    store.write_sources({"version": 1, "sources": w["sources"]})
    if noise is not None:
        # 日志里 AI 的文字能进去的地方：保护拦截的原因和目标、找不到的任务名、会话 ID
        store.append("protect", noise or None, kind="write", tool="fs_write", target=noise, reason=noise)
        store.append("task_not_found", noise or None, tasks_file=".kiro/specs/x/tasks.md", task=noise)
        store.append("session", noise or None, call="c-999999")
        # 仓库里不是需求文档的文件：自述加上假的引用
        (root / "notes").mkdir()
        fake = " ".join(f"[ref:{s['id']}/{u['id']}]" for s in w["sources"] for u in s["units"])
        (root / "notes" / "ai.md").write_text(f"我都读过了。{noise}\n出处：{fake}\n", encoding="utf-8")
    for r in reads:
        extra = {} if noise is None else {"note": noise}  # 读取记录多带一个 AI 文字的字段
        store.append("read", r["session"], call=r["call"], source=r["source"], unit=r["unit"],
                     unit_sha256=r["unit_sha256"], text_units=1, images=0, **extra)
    return store


def _conclusion(store: Store, target, session):
    res = api.check(store, target)
    gate = api.check_write(store, target or "src/code.py", session) if target is not None else None
    return ({k: res[k] for k in ("pass", "required", "missing", "phantom_requirements", "invalid_refs",
                                 "empty_requirement_docs", "exempt", "spec_file")},
            None if gate is None else gate["allow"])


# 默认 100 个例子在本机要 20.3、23.2 秒（2026-11-13 两次实测），按用户定的降到 30；其余几条用默认值
@settings(deadline=None, max_examples=30)
@given(worlds(kinds=("section",), adapters=("markdown",)), ai_texts)
def test_prop_16_4_ai_text_does_not_change_verdict(w, noise):
    """性质 16.4：关卡结论只由读取记录和配置决定：输入里任意改动 AI 的文字（自述、写入正文、会话 ID、
    日志里的原因和任务名、仓库里别的文件），结论不变。

    同一份输入建两个临时仓库，一份干净、一份带 AI 的文字，比较 `api.check` 的结论和 `api.check_write` 放不放行。
    反向检查：干净的一份达标、而且有必看单元时，去掉全部读取记录必须变成不达标，证明这条测试不是空转。
    """
    with tempfile.TemporaryDirectory(prefix="refcov-prop-") as tmp:
        tmp = Path(tmp)
        (tmp / "clean").mkdir()
        (tmp / "noisy").mkdir()
        clean = _conclusion(_make_repo(tmp / "clean", w, w["records"]), w["target"], "sess_a")
        noisy = _conclusion(_make_repo(tmp / "noisy", w, w["records"], noise), w["target"], noise or None)
        assert noisy == clean
        verdict_, _ = clean
        event("干净的一份达标" if verdict_["pass"] else "干净的一份不达标")
        if verdict_["pass"] and verdict_["required"] > 0 and not verdict_["exempt"]:
            (tmp / "unread").mkdir()
            unread = _conclusion(_make_repo(tmp / "unread", w, []), w["target"], "sess_a")
            assert unread[0]["pass"] is False
            assert unread[1] in (None, False)
            event("反向检查：去掉读取后不达标")
