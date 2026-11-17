"""`refcov init` 和 `refcov doctor` 的转交（设计 4.1）。

refcov/cli.py 只导入这个模块。这里的名字里没有接入层的名字，所以核心层的源码里不出现接入层的导入字符串
（tests/test_core_names.py 检查这一点）。这里再去导入接入层：init 调 integrations/kiro/init.py，
doctor 先调核心的只读检查 refcov.api.doctor_core，再调 integrations/kiro/doctor.py。
"""

from pathlib import Path

_LABEL = {"ok": "好", "problem": "问题", "hint": "提示"}


def format_checks(checks: list[dict]) -> str:
    lines, last = [], None
    for c in checks:
        if c["section"] != last:
            lines.append(f"[{c['section']}]")
            last = c["section"]
        lines.append(f"  {_LABEL[c['level']]}：{c['message']}")
        if c.get("fix"):
            lines.append(f"    修法：{c['fix']}")
    return "\n".join(lines)


def init(repo: Path, force: bool) -> int:
    from integrations.kiro import init as kiro_init

    return kiro_init.run(repo, force)


def doctor(repo: Path) -> int:
    """只读检查。退出码：0 没有问题；1 有问题（提示不算）；2 不能检查（不在仓库根目录）。"""
    if not (repo / ".git").exists():
        print(f"不能检查：请在仓库根目录运行（{repo} 下没有 .git）。")
        return 2
    from integrations.kiro import doctor as kiro_doctor
    from refcov import api
    from refcov.store import Store

    checks = api.doctor_core(Store(repo)) + kiro_doctor.run(repo)
    print(format_checks(checks))
    return 1 if any(c["level"] == "problem" for c in checks) else 0
