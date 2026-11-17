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


PERMISSION_SECTION = "Kiro 权限（两条规则，只提示）"


def _rule_blocks(text: str) -> list[str]:
    """用户级权限文件按行切成规则块：每个 `- capability:` 开头的行起一块，到下一块为止（设计第 5 节）。"""
    blocks, cur = [], None
    for line in text.splitlines():
        if line.strip().startswith("- capability:"):
            if cur is not None:
                blocks.append("\n".join(cur))
            cur = [line]
        elif cur is not None:
            cur.append(line)
    if cur is not None:
        blocks.append("\n".join(cur))
    return blocks


def _missing(blocks: list[str], effect: str, names: list[str]) -> list[str]:
    """names 里没有出现在"同一块里有 capability: mcp 和 effect: <effect>"的规则中的那些名字。

    全都有就返回空列表；没有这样的块，返回全部名字。
    """
    best = None
    for block in blocks:
        if "capability: mcp" not in block or f"effect: {effect}" not in block:
            continue
        miss = [n for n in names if f'"{n}"' not in block and f"'{n}'" not in block]
        if best is None or len(miss) < len(best):
            best = miss
        if not miss:
            break
    return list(names) if best is None else best


def permission_checks(server: str, path: Path | None = None) -> list[dict]:
    """两条规则分别查（设计第 5 节，需求 4.2）：读取工具的 allow，和 apply_proposal 的 ask。

    文本查找，不引 YAML 库：规则按 `- capability:` 切块，一块里同时有 `capability: mcp`、对应的 effect 和
    要找的名字，才算有。只写提示，不算问题，不影响退出码；不判断用户的其他规则。
    """
    if path is None:
        path = Path.home() / ".kiro" / "settings" / "permissions.yaml"
    try:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    except (OSError, UnicodeDecodeError):
        text = ""
    blocks = _rule_blocks(text)
    reads = [f"{server}/{tool}" for tool in kiro_init.READ_TOOLS]
    write = f"{server}/{kiro_init.WRITE_TOOL}"
    out = []
    missing = _missing(blocks, "allow", reads)
    if missing:
        out.append(_check(PERMISSION_SECTION, "hint",
                          f"读资料时每次都会弹窗：{path} 里没有读取工具的 allow 规则（缺：{'、'.join(missing)}）。",
                          "在用户级权限文件里加上 refcov init 打印的第一条规则（init 只打印，不替你写）"))
    else:
        out.append(_check(PERMISSION_SECTION, "ok", "读取工具的 allow 规则已经有"))
    if _missing(blocks, "ask", [write]):
        out.append(_check(PERMISSION_SECTION, "hint",
                          f"登记（{kiro_init.WRITE_TOOL}）没有 ask 规则：批准框里可能出现 Always allow，选了以后就不再问。",
                          "在用户级权限文件里加上 refcov init 打印的第二条规则"))
    else:
        out.append(_check(PERMISSION_SECTION, "ok", f"{kiro_init.WRITE_TOOL} 的 ask 规则已经有"))
    return out


def run(repo: Path) -> list[dict]:
    return mcp_checks(repo) + hook_checks(repo) + permission_checks(kiro_init.server_name(repo))
