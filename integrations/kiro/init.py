"""`refcov init` 的实现（接入层，只用标准库）：写 Kiro 的 MCP 配置、5 个钩子和配置文件模板。

只能由用户在终端运行（USER_ONLY，设计第 6 节）。`integrations/commands.py` 转交到这里。
设计第 4 节：`--force` 只换 MCP 的 refcov 项的 command 和 args，其他键保留；只覆盖这 5 个钩子文件；
配置文件永不覆盖。写钩子之前先探测：这个解释器找不到钩子模块，就一个文件都不写（设计 4.2）。
"""

import json
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent  # integrations/kiro
TEMPLATES = PKG / "hooks"  # 模板不改（设计 2.4）；init 只替换命令的前缀
HOOK_MODULE = "integrations.kiro.hook"  # 钩子模块（设计 2.2）
MCP_MODULE = "refcov_mcp"
OLD_PREFIX = "python integrations/kiro/hook.py"  # 模板里的钩子命令前缀
PROBE_TIMEOUT = 60

CONFIG_TEMPLATE = """\
# RefCov 配置（refcov init 生成的模板）。只能由用户手动修改；AI 经 Kiro 工具写这个文件会被拦。
# 路径都相对仓库根目录、用 / 分隔，匹配时不分大小写；* 也能跨 /。

mode = "strict"          # strict | light
enforce = true           # false 时关卡一律放行，记录照常

# 哪些文件是需求文档、规格文件（Kiro 的规格放在 .kiro/specs/ 下）
requirements = [".kiro/specs/*/requirements.md"]
spec_files   = [".kiro/specs/**"]

# 要算校验值的 Kiro 钩子文件，和上一次报告比，变了就标红
watch = [".kiro/hooks/refcov-*.json"]

# 要算校验值、并且要用户确认的文件
confirm = ["docs/decisions/**"]

# 豁免：写这些文件不检查是否达标。根目录的 DEVLOG.md 要单独列
exempt = ["DEVLOG.md", "**/DEVLOG.md", "docs/decisions/**"]

# 参考材料。files 里写要读的材料（通配符，相对仓库根目录）。
# 写好以后，在仓库根目录运行 refcov sync 登记它们。网址不能写在这里，用 refcov add 登记。
[sources]
files = []

# 登记只收 Markdown，视频不能直接登记。要先用镜头应用生成清单：
# 在 RefCov 仓库的 apps/shot-coverage 里运行 detect，生成 <视频>.shots.md（默认放在视频旁边）。
# 声明适配器和登记清单的写法见 apps/shot-coverage/README.md。
# [adapters]
# shot = "apps/shot-coverage/adapter.py"
#
# [sources.shot]
# files = ["videos/*.shots.md"]
"""


def hook_command(template: str, python: str, root: str) -> str:
    """模板命令的前缀换成 `"<解释器>" -P -m integrations.kiro.hook --root "<仓库根>"`，事件名留在后面。
    不以模板前缀开头的命令原样返回。"""
    if not template.startswith(OLD_PREFIX):
        return template
    return f'"{python}" -P -m {HOOK_MODULE} --root "{root}"' + template[len(OLD_PREFIX):]


def module_importable(python: str, cwd: Path, module: str) -> bool:
    """这个解释器在 cwd 里能不能找到 module（只查找，不运行模块，不写字节码）。设计 4.2 和 5.3。
    -P 不把当前目录放进 sys.path，所以只能找到安装的包（和钩子实际运行的条件一样）；-B 不写 .pyc。
    找不到、或探测本身出错，都算找不到。"""
    code = "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec(sys.argv[1]) else 1)"
    try:
        res = subprocess.run([python, "-P", "-B", "-c", code, module], cwd=str(cwd),
                             capture_output=True, timeout=PROBE_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return False
    return res.returncode == 0


def _dump(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_mcp(repo: Path, python: str, root: str, force: bool) -> str:
    """`.kiro/settings/mcp.json`。不存在则新建；合法则只加 `mcpServers.refcov`；`--force` 时只换它的
    command 和 args，其他键（autoApprove、env、disabled 等）保留（需求 3.6）。不合法则不改，打印要粘贴的内容。"""
    path = repo / ".kiro" / "settings" / "mcp.json"
    rel = ".kiro/settings/mcp.json"
    args = ["-P", "-m", MCP_MODULE, "--root", root]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump({"mcpServers": {"refcov": {"command": python, "args": args, "disabled": False}}}),
                        encoding="utf-8")
        return f"写了 {rel}（MCP 配置，解释器和仓库根都是绝对路径）"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
            raise ValueError("不是 JSON 对象，或 mcpServers 不是对象")
    except (OSError, ValueError):
        entry = {"command": python, "args": args, "disabled": False}
        return (f"没改 {rel}：不是合法的 JSON 对象。请手动把下面这一项加进 mcpServers：\n"
                + json.dumps({"refcov": entry}, indent=2, ensure_ascii=False))
    servers = data.setdefault("mcpServers", {})
    current = servers.get("refcov")
    if current is not None and not force:
        return f"跳过 {rel} 里的 mcpServers.refcov（已存在；加 --force 只换 command 和 args）"
    if isinstance(current, dict):
        current["command"] = python
        current["args"] = args  # 其他键保留
    else:
        servers["refcov"] = {"command": python, "args": args, "disabled": False}
    path.write_text(_dump(data), encoding="utf-8")
    return f"写了 {rel} 里的 mcpServers.refcov"


def _rewrite_commands(node, python: str, root: str) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                node[key] = hook_command(value, python, root)
            else:
                _rewrite_commands(value, python, root)
    elif isinstance(node, list):
        for value in node:
            _rewrite_commands(value, python, root)


def copy_hooks(repo: Path, python: str, root: str, force: bool) -> list[str]:
    """复制 5 个钩子模板到 `.kiro/hooks/`，命令改成绝对路径。同名文件不覆盖；`--force` 只覆盖这 5 个。"""
    out = []
    for src in sorted(TEMPLATES.glob("refcov-*.json")):
        rel = f".kiro/hooks/{src.name}"
        dst = repo / ".kiro" / "hooks" / src.name
        if dst.exists() and not force:
            out.append(f"跳过 {rel}（已存在；加 --force 覆盖）")
            continue
        data = json.loads(src.read_text(encoding="utf-8"))
        _rewrite_commands(data, python, root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_dump(data), encoding="utf-8")
        out.append(f"写了 {rel}")
    return out


def write_config(repo: Path) -> str:
    """配置文件：不存在才写模板；存在就不动，`--force` 也不动（只由用户改）。"""
    path = repo / "refcov.toml"
    if path.exists():
        return "配置文件 refcov.toml 已存在，没有动（这个文件只由你改）"
    path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    return "写了 refcov.toml 模板（[sources] 的 files 为空，等你写要读的材料）"


def run(repo: Path, force: bool) -> int:
    """写 MCP 配置、钩子和模板。返回退出码：0 完成（跳过的也算完成）；1 什么都没写。"""
    if not (repo / ".git").exists():
        print(f"没有装：请在仓库根目录运行（{repo} 下没有 .git）。", file=sys.stderr)
        return 1
    python = sys.executable
    if not module_importable(python, repo, HOOK_MODULE):
        print(f"没有写任何文件：解释器 {python} 找不到 {HOOK_MODULE}。"
              "请用同一个解释器重新安装 RefCov（例如 uv tool install，或 pip install -e），再运行 init。",
              file=sys.stderr)
        return 1
    root = str(repo.resolve())
    lines = [write_mcp(repo, python, root, force), *copy_hooks(repo, python, root, force), write_config(repo)]
    print("\n".join(lines))
    print("下一步：1）在 refcov.toml 的 [sources] 里写要读的材料；2）在仓库根目录运行 refcov sync；"
          "3）在 Kiro 里确认 refcov MCP 已连上（refcov doctor 能查 MCP 配置）。")
    return 0
