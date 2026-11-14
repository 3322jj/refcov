"""状态目录、配置、清单和只追加日志（设计 2、3.1、3.2、3.4）。

只用标准库。仓库根目录一律由调用方传入，这里不按当前目录找状态目录。
"""

from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
import os
import posixpath
import time
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

STATE_DIR = ".refcov"
CONFIG_FILE = "refcov.toml"
SOURCES_FILE = "sources.json"
LOG_FILE = "log.jsonl"
LOCK_FILE = "log.lock"
CACHE_DIR = "cache"

GENESIS = "0" * 64
LOCK_TIMEOUT = 2.0
LOCK_RETRY = 0.05
LOCK_STALE = 10.0

DEFAULT_CONFIG = {
    "mode": "strict",
    "enforce": True,
    "requirements": [],
    "spec_files": [],
    "watch": [],
    "confirm": ["docs/decisions/**"],
    "exempt": ["DEVLOG.md", "**/DEVLOG.md", "docs/decisions/**"],
    "relax": {"sources": [], "kinds": [], "units": []},
    "scope": [],
    "adapters": {},  # 适配器名 → 适配器文件路径（相对仓库根目录），见 refcov/adapters/loader.py
}


class StoreError(Exception):
    """状态目录或配置出错。"""


class ConfigError(StoreError):
    """配置文件读不了或取值不对。"""


class LockTimeout(StoreError):
    """规定时间内拿不到日志锁。"""


@dataclass(frozen=True)
class ChainResult:
    """哈希链校验结果。broken_at 是第一个 prev 或 seq 对不上的行号（从 1 数），完整时为 None。"""

    ok: bool
    lines: int
    broken_at: int | None = None

    def describe(self) -> str:
        return "链完整" if self.ok else f"第 {self.broken_at} 行起断开"


def now_iso() -> str:
    """本地时间，带时区，精确到秒。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def rel_path(root: Path, path: str | os.PathLike) -> str:
    """转成相对仓库根目录、用 `/` 分隔的路径。相对路径按仓库根目录解释，不按当前目录。"""
    p = str(path).replace("\\", "/")
    if os.path.isabs(p):
        try:
            p = os.path.relpath(p, str(root)).replace("\\", "/")
        except ValueError:  # Windows 上不在同一个盘
            return posixpath.normpath(p)
    p = posixpath.normpath(p)
    return "" if p == "." else p


def path_matches(rel: str, patterns) -> bool:
    """路径和模式都转小写，用 fnmatchcase 匹配（Windows 和 Linux 结果一致）。`*` 能跨 `/`。"""
    r = rel.replace("\\", "/").lower()
    if isinstance(patterns, str):  # 字符串当成一个模式，不逐字符拆开（外部审计 2026-11-12）
        patterns = [patterns]
    return any(fnmatch.fnmatchcase(r, str(p).replace("\\", "/").lower()) for p in patterns)


LIST_KEYS = ("requirements", "spec_files", "watch", "confirm", "exempt")
RELAX_KEYS = ("sources", "kinds", "units")
SCOPE_KEYS = ("paths", "sources")


def _string_lists_to_lists(cfg: dict) -> list[dict]:
    """把写成字符串的列表项换成只有这一项的列表（就地改 cfg），返回写错的位置 [{where, value}]，按配置顺序。

    只处理字符串；别的类型（数字、表、`scope = 7`）不动，保持原来的行为。
    """
    out = []
    for key in LIST_KEYS:
        if isinstance(cfg.get(key), str):
            out.append({"where": key, "value": cfg[key]})
            cfg[key] = [cfg[key]]
    scopes = cfg.get("scope")
    if isinstance(scopes, list):
        for i, sc in enumerate(scopes, start=1):
            if not isinstance(sc, dict):
                continue
            for key in SCOPE_KEYS:
                if isinstance(sc.get(key), str):
                    out.append({"where": f"scope 第 {i} 条 {key}", "value": sc[key]})
                    sc[key] = [sc[key]]
    relax = cfg.get("relax")
    if isinstance(relax, dict):
        for key in RELAX_KEYS:
            if isinstance(relax.get(key), str):
                out.append({"where": f"relax.{key}", "value": relax[key]})
                relax[key] = [relax[key]]
    return out


class Store:
    """一个仓库的状态目录。第一次写入时才建目录，只读操作不建。"""

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root).resolve()
        self.state_dir = self.root / STATE_DIR
        self.config_path = self.root / CONFIG_FILE
        self.sources_path = self.state_dir / SOURCES_FILE
        self.log_path = self.state_dir / LOG_FILE
        self.lock_path = self.state_dir / LOCK_FILE
        self.cache_dir = self.state_dir / CACHE_DIR

    # ---- 目录和路径 ----

    def ensure_state_dir(self) -> Path:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        return self.state_dir

    def rel(self, path) -> str:
        return rel_path(self.root, path)

    def matches(self, path, patterns) -> bool:
        return path_matches(self.rel(path), patterns)

    # ---- 配置（只读） ----

    def load_config(self) -> dict:
        """读 refcov.toml；不存在时用默认值。文件里写了的项覆盖默认值。

        列表项写成字符串时当成只有这一项的列表，写错的位置记在 `string_lists` 里，报告的"配置写错"列出
        （外部审计 2026-11-12：`exempt = "docs/*.md"` 原先被逐字符当成模式，`*` 豁免了全仓库）。不抛 ConfigError，
        抛了会走关卡出错放行。别的类型错误（例如 `scope = 7`）保持原样。偏离需求原文（需求没写这条）。
        """
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["string_lists"] = []
        if not self.config_path.exists():
            return cfg
        try:
            with open(self.config_path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise ConfigError(f"读不了 {CONFIG_FILE}：{e}") from e
        for key, value in data.items():
            if key == "relax" and isinstance(value, dict):
                cfg["relax"].update(value)
            else:
                cfg[key] = value
        cfg["string_lists"] = _string_lists_to_lists(cfg)
        if cfg["mode"] not in ("strict", "light"):
            raise ConfigError(f"mode 只能是 strict 或 light，现在是 {cfg['mode']!r}")
        if not isinstance(cfg["enforce"], bool):
            raise ConfigError("enforce 只能是 true 或 false")
        return cfg

    def config_mtime(self) -> str | None:
        """配置文件最后修改时间（本地时间带时区）；文件不存在时为 None。"""
        try:
            ts = self.config_path.stat().st_mtime
        except FileNotFoundError:
            return None
        return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")

    # ---- 清单 ----

    def read_sources(self) -> dict:
        try:
            with open(self.sources_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"version": 1, "sources": []}

    def write_sources(self, manifest: dict) -> None:
        """整份写入：先写临时文件再替换，写到一半出错不会损坏原清单。"""
        self.ensure_state_dir()
        tmp = self.sources_path.with_name(SOURCES_FILE + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.sources_path)

    # ---- 日志锁 ----

    def _acquire_lock(self, timeout: float = LOCK_TIMEOUT) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    if time.time() - self.lock_path.stat().st_mtime > LOCK_STALE:
                        os.remove(self.lock_path)  # 残留的锁
                        continue
                except FileNotFoundError:
                    continue  # 刚被别人放掉
                except PermissionError:
                    pass  # Windows 上别的进程正在建或删这个文件
            except PermissionError:
                pass  # Windows：锁文件正被删除时 os.open 会报这个
            else:
                try:
                    os.write(fd, str(os.getpid()).encode("ascii"))
                finally:
                    os.close(fd)
                return
            if time.monotonic() >= deadline:
                raise LockTimeout(f"{timeout:g} 秒内拿不到日志锁 {self.lock_path}")
            time.sleep(LOCK_RETRY)

    def _release_lock(self) -> None:
        try:
            os.remove(self.lock_path)
        except FileNotFoundError:
            pass

    # ---- 日志 ----

    def _read_log(self, writer: bool = False) -> tuple[list[bytes], bool]:
        """读出日志的完整行（不含换行符），并返回末尾有没有一段没写完的行。

        一条记录是一次写进去的"一行 JSON + \\n"，所以完整的行一定以 \\n 结尾。
        - 不拿锁的读取方（`writer=False`，例如报告）：末尾没有 \\n 的那段当成别的进程正在写的行，
          不算进记录，也不参与哈希链校验。
        - 拿着锁的写入方（`writer=True`）：这时不会有别人在写，末尾的半行说明上次写入中断。
          抛 StoreError、不写，免得新记录接在半行后面变成一行坏记录。
        """
        try:
            data = self.log_path.read_bytes()
        except FileNotFoundError:
            return [], False
        partial = bool(data) and not data.endswith(b"\n")
        if partial and writer:
            raise StoreError(f"日志末尾有一行没写完，可能上次写入中断：{self.log_path}")
        lines = data.split(b"\n")
        lines.pop()  # 以 \n 结尾时是空串；否则是没写完的那段
        return lines, partial

    def _read_lines(self, writer: bool = False) -> list[bytes]:
        return self._read_log(writer)[0]

    def log_tail_partial(self) -> bool:
        """日志末尾是否有一行还没写完（不拿锁读，只用于报告里提示）。"""
        return self._read_log()[1]

    @contextmanager
    def locked(self, timeout: float = LOCK_TIMEOUT):
        """拿着日志锁执行一段操作（例如登记：读清单、写缓存、追加记录、换清单）。

        拿不到锁时抛 LockTimeout，块里的代码一行都不执行。锁超过 LOCK_STALE 秒会被别的进程
        当残留删掉，所以块里不要做慢操作（例如抓网址）。
        """
        self.ensure_state_dir()
        self._acquire_lock(timeout)
        try:
            yield self
        finally:
            self._release_lock()

    def append(self, type: str, session: str | None = None, **fields) -> dict:
        """追加一条记录，返回写进去的记录。2 秒内拿不到锁时抛 LockTimeout，日志不变。"""
        with self.locked():
            return self.append_locked(type, session, **fields)

    def next_seq_locked(self) -> int:
        """拿着锁时，下一条记录会用的 seq（例如调用编号 `c-<seq>` 要写进这条记录本身）。"""
        lines = self._read_lines(writer=True)
        return int(json.loads(lines[-1].decode("utf-8"))["seq"]) + 1 if lines else 1

    def append_locked(self, type: str, session: str | None = None, **fields) -> dict:
        """调用方已经用 `locked()` 拿着锁时追加一条记录。不拿锁就调用会破坏哈希链。"""
        for reserved in ("seq", "time", "type", "session", "prev"):
            if reserved in fields:
                raise ValueError(f"字段 {reserved} 由日志自己填")
        lines = self._read_lines(writer=True)
        if lines:
            last = lines[-1]
            prev = sha256_bytes(last)
            seq = int(json.loads(last.decode("utf-8"))["seq"]) + 1
        else:
            prev, seq = GENESIS, 1
        record = {"seq": seq, "time": now_iso(), "type": type, "session": session}
        record.update(fields)
        record["prev"] = prev
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with open(self.log_path, "ab") as f:  # 二进制追加：换行固定 \n
            f.write(line + b"\n")
            f.flush()
            os.fsync(f.fileno())
        return record

    def records(self) -> list[dict]:
        """按顺序读出全部记录。"""
        return [json.loads(line.decode("utf-8")) for line in self._read_lines()]

    def verify_chain(self) -> ChainResult:
        """校验哈希链和 seq。

        改了第 N 行（N 不是最后一行）时，第 N+1 行的 prev 对不上，报"第 N+1 行起断开"；
        改了第 N 行自己的 prev 或 seq 时报第 N 行。最后一行被改查不出来，这是哈希链本身的局限。
        """
        lines = self._read_lines()
        expected_prev = GENESIS
        for i, line in enumerate(lines, start=1):
            try:
                rec = json.loads(line.decode("utf-8"))
                good = rec.get("prev") == expected_prev and rec.get("seq") == i
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                good = False
            if not good:
                return ChainResult(ok=False, lines=len(lines), broken_at=i)
            expected_prev = sha256_bytes(line)
        return ChainResult(ok=True, lines=len(lines))
