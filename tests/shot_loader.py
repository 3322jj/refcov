"""测试用：从文件路径加载镜头适配器（和核心层加载它的办法一样，目录名带连字符不能当包名导入）。"""

import importlib.util
import sys
from pathlib import Path

ADAPTER_PATH = Path(__file__).resolve().parents[1] / "apps" / "shot-coverage" / "adapter.py"
CLI_PATH = ADAPTER_PATH.with_name("cli.py")
MODULE = "shot_adapter_under_test"


def install(root: Path):
    """在临时仓库 `root` 里放一份适配器副本、声明配置，经核心层的加载器加载，返回新加载的模块。

    适配器按自己的文件位置找仓库根目录，所以要测"相对路径按仓库根目录算"，适配器必须在被测仓库里。
    每次返回的都是新的模块对象（进程内的核对缓存不会串到别的测试）。
    """
    import shutil

    from refcov.adapters import loader
    from refcov.store import Store

    target = root / "apps" / "shot-coverage"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ADAPTER_PATH, target / "adapter.py")
    (root / ".git").mkdir(exist_ok=True)
    (root / "refcov.toml").write_text('[adapters]\nshot = "apps/shot-coverage/adapter.py"\n', encoding="utf-8")
    return loader.load(Store(root), "shot")


def load():
    """加载（只加载一次）并返回适配器模块。"""
    if MODULE in sys.modules:
        return sys.modules[MODULE]
    spec = importlib.util.spec_from_file_location(MODULE, ADAPTER_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[MODULE] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(MODULE, None)
        raise
    return mod
