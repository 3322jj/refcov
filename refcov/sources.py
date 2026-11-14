"""适配器接口、单元 ID 规则和登记参考源（需求 1、2、3.4、3.5，设计 2、3.1、4）。

只用标准库。登记时按名字选用 `refcov.adapters` 里的适配器；视频、地理适配器在各自的应用里，
核心层不 import 它们（需求 2.6）。
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Protocol, Sequence

from refcov import __version__
from refcov.store import Store, now_iso

LIMIT = 4000  # 单元正文上限，按换行统一后的 len 算（设计 4 第 3 条）
EMPTY_ID = "section"

_ID_JUNK = re.compile(r"[\s\[\]@]+")  # 空白、方括号、@ 换成一个 -（设计 4 第 1 条）
_ID_BAD = re.compile(r"[\s\[\]]")  # 任何单元 ID 都不许含的字符（需求 2.5）
_BLANK = re.compile(r"^[ \t]*\n", re.M)  # 空行：只含空格、制表符的行，连同它的换行


@dataclass(frozen=True)
class KindDecl:
    """单元类型的声明（需求 2.2）：严格模式下是否默认必看，是否关键类型（轻量模式必看）。"""

    strict: bool
    key: bool = False


@dataclass(frozen=True)
class Image:
    """`read` 返回里的图片（需求 2.1，例如视频关键帧）。"""

    data: bytes
    mime: str


@dataclass(frozen=True)
class Unit:
    """一个单元。`text` 是正文（不含标题行），换行已统一为 `\\n`。"""

    id: str
    title: str
    kind: str
    text: str
    sha256: str = field(init=False)
    chars: int = field(init=False)

    def __post_init__(self):
        validate_unit_id(self.id)
        object.__setattr__(self, "sha256", hashlib.sha256(self.text.encode("utf-8")).hexdigest())
        object.__setattr__(self, "chars", len(self.text))

    def manifest_entry(self) -> dict:
        """写进清单 `units` 的一项（设计 3.1）。"""
        return {"id": self.id, "title": self.title, "kind": self.kind,
                "sha256": self.sha256, "chars": self.chars}


class Adapter(Protocol):
    """适配器接口：三个函数（需求 2.1）加两项声明。

    - `name`：适配器名，写进清单的 `adapter`。
    - `kinds`：单元类型 → `KindDecl`（需求 2.2）。
    - `split(data, name)`：把参考源原文拆成单元。`name` 是文件名（不带扩展名），
      没有标题的部分用它当标题。
    - `read(data, name, unit_id)`：读一个单元，返回文字和图片的列表。
    - `facts(data, name, unit_id)`：这个单元可核对的事实。
    单元不存在时 `read` 和 `facts` 抛 `KeyError`。
    """

    name: str
    kinds: dict[str, KindDecl]

    def split(self, data: bytes, name: str) -> list[Unit]: ...

    def read(self, data: bytes, name: str, unit_id: str) -> list[str | Image]: ...

    def facts(self, data: bytes, name: str, unit_id: str) -> dict: ...


def check_declarations(kinds: dict[str, KindDecl]) -> None:
    """需求 2.4：关键类型一定也是严格模式必看的类型。不满足时抛 ValueError。"""
    bad = sorted(k for k, d in kinds.items() if d.key and not d.strict)
    if bad:
        raise ValueError(f"关键类型必须也是严格必看的类型：{', '.join(bad)}")


def normalize_newlines(text: str) -> str:
    """`\\r\\n` 和单独的 `\\r` 都换成 `\\n`。拆分、算长度、算校验值都在这之后（设计 4 第 8 条）。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def validate_unit_id(unit_id: str) -> None:
    """单元 ID 不能为空，不能含空白和方括号（需求 2.5）。不满足时抛 ValueError。"""
    if not unit_id or _ID_BAD.search(unit_id):
        raise ValueError(f"单元 ID 不能为空，也不能含空白或方括号：{unit_id!r}")


def title_to_id(title: str) -> str:
    """设计 4 第 1 条：连续的空白、`[`、`]`、`@` 换成一个 `-`，去掉首尾的 `-`；为空时用 `section`。"""
    return _ID_JUNK.sub("-", title).strip("-") or EMPTY_ID


def assign_ids(titles: Sequence[str], borrowed: Iterable[int] = ()) -> list[str]:
    """设计 4 第 2、5 条：同一参考源里的标题按文档顺序生成 ID，返回顺序和 `titles` 相同。

    先给每个标题保留它自己生成的 ID；同一个 ID 第二次出现起，从 `-2` 往后找空号。
    空号要避开已经给出的 ID，也要避开所有标题自己的 ID（包括后面才出现的）。
    查重用 `casefold`，不区分大小写；ID 保留原来的大小写。

    `borrowed` 是标题借自文件名的位置（例如第一个标题之前的那段）。它们不算标题：
    等所有真标题分完 ID 再分，和真标题撞了就从 `-2` 起找空号。
    """
    bases = [title_to_id(t) for t in titles]
    late = sorted(set(borrowed))
    reserved = {b.casefold() for i, b in enumerate(bases) if i not in late}
    taken: set[str] = set()
    ids = [""] * len(bases)
    for i in [i for i in range(len(bases)) if i not in late] + late:
        base = uid = bases[i]
        if uid.casefold() in taken:
            n = 2
            while (c := f"{base}-{n}".casefold()) in taken or c in reserved:
                n += 1
            uid = f"{base}-{n}"
        taken.add(uid.casefold())
        ids[i] = uid
    return ids


def split_long(text: str, limit: int = LIMIT) -> list[str]:
    """设计 4 第 3 条：正文超过 `limit` 个字符就切成几段，拼回去等于原文。

    切在不超过 `limit` 的最后一个空行之后（空行算前一段的）。没有这样的空行，或者
    前一段只剩空白，就在第 `limit` 个字符处硬切。每段都不为空；只含空白的段只可能
    来自硬切（前 `limit` 个字符全是空白）。
    """
    if limit < 1:
        raise ValueError("limit 至少为 1")
    parts = []
    while len(text) > limit:
        first = len(text) - len(text.lstrip())  # 第一个非空白字符的位置
        cuts = [m.end() for m in _BLANK.finditer(text, 0, limit) if m.end() > first]
        cut = cuts[-1] if cuts else limit
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    return parts


def make_units(sections: Iterable[tuple[str, str]], kind: str, limit: int = LIMIT,
               borrowed: Iterable[int] = ()) -> list[Unit]:
    """把 (标题, 正文) 序列变成单元：先按标题定 ID，再拆超长的（设计 4 第 3 条）。

    `borrowed` 见 `assign_ids`；它只影响分 ID 的先后，单元顺序和 `sections` 相同。
    拆出的第 n 段（n ≥ 2）标题是"原标题 (n)"，ID 是原 ID 加 `@n`。标题生成的 ID 里
    没有 `@`，所以拆分出的 ID 不用再查重名。
    """
    sections = list(sections)
    units = []
    ids = assign_ids([t for t, _ in sections], borrowed)
    for (title, body), uid in zip(sections, ids):
        for n, part in enumerate(split_long(normalize_newlines(body), limit), start=1):
            if n == 1:
                units.append(Unit(uid, title, kind, part))
            else:
                units.append(Unit(f"{uid}@{n}", f"{title} ({n})", kind, part))
    return units


def find_unit(units: Iterable[Unit], unit_id: str) -> Unit:
    """按 ID 精确查找单元，找不到抛 KeyError。"""
    for u in units:
        if u.id == unit_id:
            return u
    raise KeyError(unit_id)


# ---- 登记参考源（需求 1.1、1.4、1.5、3.4，任务 4）----

SOURCE_ID = re.compile(r"[a-z0-9-]+")  # 和 citation.md 引用正则里的参考源 ID 部分一致
MARKDOWN_EXT = (".md", ".markdown")
MARKDOWN_TYPES = {"text/markdown", "text/x-markdown"}
FETCH_TIMEOUT = 10.0
USER_AGENT = f"refcov/{__version__} (+https://github.com/3322jj/refcov)"


class RegisterError(Exception):
    """登记失败。消息就是给用户看的原因。抛出时清单、缓存、日志都没动。"""


@dataclass(frozen=True)
class Registered:
    """登记结果。`written` 为 False 表示来源和内容都没变，什么都没写。"""

    entry: dict
    changed: bool
    written: bool


def fetch_url(url: str, timeout: float = FETCH_TIMEOUT) -> tuple[bytes, str | None]:
    """用 urllib 抓网址，返回 (原始字节, Content-Type)。出错时抛 urllib 自己的异常。"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type")


def content_sha256(text: str) -> str:
    """参考源整体的校验值：去掉 BOM、换行统一成 `\\n` 后的 UTF-8 字节的 SHA-256。

    同一份 .md 在 Windows 上可能是 CRLF（core.autocrlf），在 CI 上是 LF，按原始字节算会对不上。
    """
    return hashlib.sha256(normalize_newlines(text).encode("utf-8")).hexdigest()


def _is_url(origin: str) -> bool:
    return urllib.parse.urlsplit(origin).scheme.lower() in ("http", "https")


def file_name(origin: str, source_id: str) -> str:
    """拆单元时借来当标题的文件名（不带扩展名）。登记和读取都按清单里的 `origin` 算，结果一致。

    网址取路径最后一段（先 unquote），本地文件取文件名；为空时用参考源 ID。
    """
    if _is_url(origin):
        last = urllib.parse.unquote(urllib.parse.urlsplit(origin).path).rsplit("/", 1)[-1]
    else:
        last = origin.replace("\\", "/").rsplit("/", 1)[-1]
    return PurePosixPath(last).stem or source_id


def _load_url(origin: str, fetch) -> tuple[bytes, str]:
    try:
        data, ctype = fetch(origin)
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
        raise RegisterError(f"抓取失败：{origin}：{e}") from e
    mime = (ctype or "").split(";", 1)[0].strip().lower()
    last = urllib.parse.unquote(urllib.parse.urlsplit(origin).path).rsplit("/", 1)[-1]
    md_name = last.lower().endswith(MARKDOWN_EXT)
    if not (mime in MARKDOWN_TYPES or (mime == "text/plain" and md_name)):
        raise RegisterError(
            f"不支持该格式：{origin} 返回的 Content-Type 是 {ctype or '（没有）'}。"
            "只登记 Markdown（text/markdown；text/plain 只在地址以 .md 或 .markdown 结尾时接受）"
        )
    return data, origin


def _load_file(store: Store, origin: str) -> tuple[bytes, str]:
    path = Path(origin)
    if not path.is_absolute():
        path = store.root / path
    resolved = path.resolve()  # 先 resolve：去掉 ..，跟到链接指向的真实位置
    root = store.root.resolve()
    if not Path(os.path.normcase(resolved)).is_relative_to(os.path.normcase(root)):
        raise RegisterError(f"参考源文件要放在仓库里：{resolved} 不在 {root} 下")
    if resolved.suffix.lower() not in MARKDOWN_EXT:
        raise RegisterError(f"不支持该格式：{origin}。只登记 Markdown（扩展名 .md 或 .markdown）")
    try:
        data = resolved.read_bytes()
    except OSError as e:
        raise RegisterError(f"读取失败：{origin}：{e}") from e
    return data, os.path.relpath(resolved, root).replace("\\", "/")


def register(store: Store, origin: str, source_id: str,
             fetch: Callable[[str], tuple[bytes, str | None]] = fetch_url,
             adapter: str = "markdown") -> Registered:
    """登记或重新登记一个参考源（本地 Markdown 文件或网址）。

    `adapter` 是适配器名：默认 `markdown`（内置）；别的名字要用户先在配置的 `[adapters]` 里声明（C4）。
    不管用哪个适配器，登记的文件都还是 UTF-8 的 Markdown 文本（拆单元由适配器负责）。

    抓取、解码、拆分在拿锁之前做完（抓网址最多 10 秒，锁超过 10 秒会被别的进程当残留删掉）。
    锁里只做：读清单、比对、写缓存、追加 `register`、替换清单。日志排在清单前面：中途出错时
    宁可"日志有登记、清单没变"（凭证提前失效），不要"清单变了、日志没记"。
    来源和校验值都没变时什么都不写。任何一步失败都抛 RegisterError 或 StoreError。
    本地相对路径按仓库根目录解释；清单里存相对仓库根目录、用 `/` 分隔的路径。
    """
    from refcov.adapters import loader

    if not SOURCE_ID.fullmatch(source_id):
        raise RegisterError(f"参考源 ID 只能用小写字母、数字和短横线：{source_id!r}")
    if _is_url(origin):
        data, stored = _load_url(origin, fetch)
    else:
        data, stored = _load_file(store, origin)
    name = file_name(stored, source_id)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise RegisterError(f"不是 UTF-8 编码：{origin}：{e}") from e
    sha = content_sha256(text)
    try:
        ad = loader.load(store, adapter)
    except loader.AdapterError as e:
        raise RegisterError(str(e)) from e
    try:
        units = ad.split(data, name)
    except Exception as e:  # 适配器自己的错误：不改清单、缓存、日志
        raise RegisterError(f"适配器 {adapter} 拆分失败：{type(e).__name__}: {e}") from e
    undeclared = sorted({u.kind for u in units} - set(ad.kinds))
    if undeclared:
        raise RegisterError(f"适配器 {adapter} 拆出的单元类型没有声明：{'、'.join(undeclared)}")

    with store.locked():
        try:
            manifest = store.read_sources()
        except (OSError, ValueError) as e:
            raise RegisterError(f"清单读不了：{store.sources_path}：{e}") from e
        sources = manifest.setdefault("sources", [])
        old = next((s for s in sources if s.get("id") == source_id), None)
        if (old and old.get("origin") == stored and old.get("sha256") == sha
                and old.get("adapter") == ad.name):
            return Registered(old, changed=False, written=False)
        changed = old is None or old.get("sha256") != sha or old.get("adapter") != ad.name
        store.cache_dir.mkdir(parents=True, exist_ok=True)
        cache = store.cache_dir / sha
        tmp = cache.with_name(sha + ".tmp")
        tmp.write_bytes(data)  # 缓存里存原始字节
        os.replace(tmp, cache)
        rec = store.append_locked("register", None, source=source_id, origin=stored, sha256=sha,
                                  adapter=ad.name, units=len(units), changed=changed)
        entry = {"id": source_id, "origin": stored, "fetched": now_iso(), "sha256": sha,
                 "adapter": ad.name, "registered_seq": rec["seq"],
                 "units": [u.manifest_entry() for u in units]}
        if old is None:
            sources.append(entry)
        else:
            sources[sources.index(old)] = entry
        store.write_sources(manifest)
    return Registered(entry, changed=changed, written=True)
