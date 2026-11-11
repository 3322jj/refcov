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
    return any(fnmatch.fnmatchcase(r, str(p).replace("\\", "/").lower()) for p in patterns)


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
        """读 refcov.toml；不存在时用默认值。文件里写了的项覆盖默认值。"""
        cfg = copy.deepcopy(DEFAULT_CONFIG)
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

    def _read_lines(self) -> list[bytes]:
        try:
            data = self.log_path.read_bytes()
        except FileNotFoundError:
            return []
        lines = data.split(b"\n")
        if lines and lines[-1] == b"":
            lines.pop()
        return lines

    def append(self, type: str, session: str | None = None, **fields) -> dict:
        """追加一条记录，返回写进去的记录。2 秒内拿不到锁时抛 LockTimeout，日志不变。"""
        for reserved in ("seq", "time", "type", "session", "prev"):
            if reserved in fields:
                raise ValueError(f"字段 {reserved} 由日志自己填")
        self.ensure_state_dir()
        self._acquire_lock()
        try:
            lines = self._read_lines()
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
        finally:
            self._release_lock()

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
