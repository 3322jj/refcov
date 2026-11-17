"""`refcov doctor` 的接入层部分：MCP 配置、5 个钩子、权限文件。只读（设计第 5 节）。

每一项返回一个字典：section（节名）、level（ok、problem 或 hint）、message（说明）、fix（修法，问题才有）。
路径比较用 os.path.normcase(os.path.realpath(...))（需求 5.10）。
"""

import json
import os
import re
from pathlib import Path

from integrations.kiro import init as kiro_init

_FIRST = re.compile(r'^\s*(?:"([^"]+)"|(\S+))')
_ROOT = re.compile(r'--root\s+(?:"([^"]*)"|(\S+))')
_MODULE = re.compile(r"-m\s+(\S+)")


def _check(section: str, level: str, message: str, fix: str | None = None) -> dict:
    return {"section": section, "level": level, "message": message, "fix": fix}


def same_path(a: str, b: Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(str(b)))


def parse_command(cmd: str) -> dict:
    """钩子或 MCP 命令的几部分：解释器（第一个词，去掉引号）、--root 的值、-m 的模块名、最后一个词（事件名）。"""
    m = _FIRST.match(cmd)
    exe = (m.group(1) or m.group(2)) if m else ""
    r = _ROOT.search(cmd)
    mod = _MODULE.search(cmd)
    words = cmd.split()
    return {"exe": exe, "root": (r.group(1) or r.group(2)) if r else None,
            "module": mod.group(1) if mod else None, "last": words[-1] if words else ""}


def _commands(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                yield value
            else:
                yield from _commands(value)
    elif isinstance(node, list):
        for value in node:
            yield from _commands(value)


def _is_abs_file(path: str) -> bool:
    return os.path.isabs(path) and os.path.isfile(path)


def mcp_checks(repo: Path) -> list[dict]:
    sec, rel = "MCP 配置", ".kiro/settings/mcp.json"
    path = repo / rel
    if not path.is_file():
        return [_check(sec, "problem", f"没有 {rel}", "在仓库根目录运行 refcov init")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data["mcpServers"]
        if not isinstance(servers, dict):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        return [_check(sec, "problem", f"{rel} 不是合法的 JSON，或没有 mcpServers 对象",
                       "改好 JSON 后运行 refcov init；或删掉这个文件再运行 refcov init")]
    entry = servers.get("refcov")
    if not isinstance(entry, dict):
        return [_check(sec, "problem", "mcpServers 里没有 refcov 项", "在仓库根目录运行 refcov init")]
    out = []
    command = entry.get("command")
    args = entry.get("args") if isinstance(entry.get("args"), list) else []
    root = args[args.index("--root") + 1] if "--root" in args and args.index("--root") + 1 < len(args) else None
    if not (isinstance(command, str) and _is_abs_file(command)):
        out.append(_check(sec, "problem", f"command 不是存在的绝对路径：{command}",
                          "运行 refcov init --force（用当前安装的解释器重写 command 和 args）"))
    if not (isinstance(root, str) and same_path(root, repo)):
        out.append(_check(sec, "problem", f"--root 没有指向当前仓库（{root}）",
                          "运行 refcov init --force"))
    if entry.get("disabled") is True:
        out.append(_check(sec, "problem", "refcov 项的 disabled 为真，MCP 服务不会启动",
                          "手工把 .kiro/settings/mcp.json 里 refcov 项的 disabled 改成 false（init 不改这一项）"))
    if isinstance(command, str) and _is_abs_file(command) and not kiro_init.module_importable(
            command, repo, kiro_init.MCP_MODULE):
        out.append(_check(sec, "problem", f"这个解释器找不到 {kiro_init.MCP_MODULE}：{command}",
                          "用装了 RefCov 的解释器运行 refcov init --force"))
    if not out:
        out.append(_check(sec, "ok", "MCP 配置正常"))
    return out


def hook_checks(repo: Path) -> list[dict]:
    sec = "钩子"
    out = []
    for tmpl in sorted(kiro_init.TEMPLATES.glob("refcov-*.json")):
        name = tmpl.name
        event = name[len("refcov-"):-len(".json")]
        path = repo / ".kiro" / "hooks" / name
        if not path.is_file():
            out.append(_check(sec, "problem", f"缺钩子文件 .kiro/hooks/{name}",
                              "运行 refcov init（不覆盖已有的文件）"))
            continue
        try:
            cmds = list(_commands(json.loads(path.read_text(encoding="utf-8"))))
            if len(cmds) != 1:
                raise ValueError
        except (OSError, ValueError):
            out.append(_check(sec, "problem", f"{name} 不是合法的钩子 JSON",
                              "修好 JSON，或运行 refcov init --force"))
            continue
        p = parse_command(cmds[0])
        problems = []
        if p["last"] != event:
            problems.append(f"事件名 {p['last']!r} 和文件名对不上（应为 {event}）")
        if not _is_abs_file(p["exe"]):
            problems.append(f"解释器不是存在的绝对路径：{p['exe']}")
        if p["root"] is None:
            problems.append("命令里没有 --root（靠脚本自己的位置算根，换个位置就失效）")
        elif not same_path(p["root"], repo):
            problems.append(f"--root 没有指向当前仓库（{p['root']}）")
        if p["module"] != kiro_init.HOOK_MODULE:
            problems.append(f"命令不是 -m {kiro_init.HOOK_MODULE} 的形式")
        elif _is_abs_file(p["exe"]) and not kiro_init.module_importable(p["exe"], repo, p["module"]):
            problems.append("这个解释器找不到钩子模块")
        if problems:
            out.append(_check(sec, "problem", f"{name}：" + "；".join(problems),
                              "运行 refcov init --force（只覆盖这 5 个钩子文件）"))
        else:
            out.append(_check(sec, "ok", f"{name} 正常"))
    return out


def permission_checks() -> list[dict]:
    """只报告文件在不在，不判断对错（设计 5.2；第二层才用）。"""
    path = Path.home() / ".kiro" / "settings" / "permissions.yaml"
    if path.is_file():
        return [_check("Kiro 权限（只报告）", "hint", f"用户级权限文件存在：{path}")]
    return [_check("Kiro 权限（只报告）", "hint", "没有用户级权限文件（第二层才用，这一步不检查）")]


def run(repo: Path) -> list[dict]:
    return mcp_checks(repo) + hook_checks(repo) + permission_checks()
