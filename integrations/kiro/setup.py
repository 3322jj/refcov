"""把 RefCov 装进用户的仓库（简化上手设计 2）：写 MCP 配置、复制 5 个钩子、写 refcov.toml 模板。

用法：在用户仓库的根目录运行 RefCov 克隆目录里的这个脚本。
    python <RefCov 目录>/integrations/kiro/setup.py [--force]

只补装，不覆盖。--force 只覆盖 MCP 配置里的 refcov 一项和 5 个钩子文件；refcov.toml 永远不覆盖（它只由用户改）。
只用标准库，不 import refcov：装之前就能运行，也不依赖 refcov 的版本。
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE / "hook.py"
TEMPLATES = HERE / "hooks"
OLD_PREFIX = "python integrations/kiro/hook.py"

CONFIG_TEMPLATE = """\
# RefCov 配置（setup.py 生成的模板）。只能由用户手动修改；AI 经 Kiro 工具写这个文件会被拦（需求 14.2）。
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

# 非 Markdown 材料：先在 [adapters] 里声明适配器，再写 [sources.<名字>] 的 files
# [adapters]
# shot = "apps/shot-coverage/adapter.py"
#
# [sources.shot]
# files = ["videos/*.mp4"]
"""


def hook_command(template: str, python: str, hook: str, root: str) -> str:
    """模板里的钩子命令：前缀 `python integrations/kiro/hook.py` 换成绝对路径和 `--root`，事件名留在最后。
    不以这个前缀开头的命令原样返回。"""
    if not template.startswith(OLD_PREFIX):
        return template
    return f'"{python}" "{hook}" --root "{root}"' + template[len(OLD_PREFIX):]


def _rewrite_commands(node, python: str, hook: str, root: str) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                node[key] = hook_command(value, python, hook, root)
            else:
                _rewrite_commands(value, python, hook, root)
    elif isinstance(node, list):
        for value in node:
            _rewrite_commands(value, python, hook, root)


def write_mcp(repo: Path, root: str, force: bool) -> str:
    """`.kiro/settings/mcp.json`：不存在就新建；存在且合法，只加或（--force）替换 mcpServers.refcov 一项。"""
    path = repo / ".kiro" / "settings" / "mcp.json"
    rel = path.relative_to(repo).as_posix()
    entry = {"command": sys.executable, "args": ["-m", "refcov_mcp", "--root", root], "disabled": False}
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"mcpServers": {"refcov": entry}}, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        return f"写了 {rel}（MCP 配置，解释器和仓库根都是绝对路径）"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("不是 JSON 对象")
    except (OSError, ValueError):
        return (f"没改 {rel}：不是合法的 JSON。请手动把下面这一项加进 mcpServers：\n"
                + json.dumps({"refcov": entry}, indent=2, ensure_ascii=False))
    servers = data.setdefault("mcpServers", {})
    if "refcov" in servers and not force:
        return f"跳过 {rel} 里的 mcpServers.refcov（已存在；加 --force 覆盖）"
    servers["refcov"] = entry
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return f"写了 {rel} 里的 mcpServers.refcov"


def copy_hooks(repo: Path, root: str, force: bool) -> list[str]:
    """复制 5 个钩子模板到 `.kiro/hooks/`，命令改成绝对路径。同名文件不覆盖；--force 只覆盖这 5 个。"""
    out = []
    for src in sorted(TEMPLATES.glob("refcov-*.json")):
        dst = repo / ".kiro" / "hooks" / src.name
        rel = dst.relative_to(repo).as_posix()
        if dst.exists() and not force:
            out.append(f"跳过 {rel}（已存在；加 --force 覆盖）")
            continue
        data = json.loads(src.read_text(encoding="utf-8"))
        _rewrite_commands(data, sys.executable, str(HOOK), root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.append(f"写了 {rel}")
    return out


def write_config(repo: Path) -> str:
    """`refcov.toml`：不存在才写模板；存在就不动，--force 也不动。"""
    path = repo / "refcov.toml"
    if path.exists():
        return "refcov.toml 已存在，没有动（这个文件只由你改）"
    path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    return "写了 refcov.toml 模板（[sources] 的 files 为空，等你写要读的材料）"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # 输出中文；被管道接住时不随控制台代码页走
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="把 RefCov 装进当前仓库（在仓库根目录运行）。")
    parser.add_argument("--force", action="store_true",
                        help="覆盖 MCP 配置里的 refcov 一项和 5 个钩子文件；refcov.toml 永不覆盖")
    args = parser.parse_args(argv)
    repo = Path.cwd()
    if not (repo / ".git").exists():
        print(f"没有装：请在仓库根目录运行（{repo} 下没有 .git）。", file=sys.stderr)
        return 1
    root = str(repo.resolve())
    lines = [write_mcp(repo, root, args.force), *copy_hooks(repo, root, args.force), write_config(repo)]
    print("\n".join(lines))
    print("下一步：1）在 refcov.toml 的 [sources] 里写要读的材料；2）在仓库根目录运行 refcov sync；"
          "3）在 Kiro 里重连 refcov MCP。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
