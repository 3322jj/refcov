"""按名字找适配器（镜头应用需求第二部分 C4，骨架需求 2.1、2.2、2.6）。只用标准库。

- `markdown` 是内置的文档适配器，永远可用，不在配置里写。
- 其他适配器在配置文件的 `[adapters]` 里声明：名字对**适配器文件的路径**（相对仓库根目录），例如
  `mine = "tools/my-adapter/adapter.py"`。路径写法而不是点路径：目录名可以带连字符，不能当包名导入。
- 核心层在需要的时候才用 `importlib` 从这个文件加载，自己不 import 任何具体适配器。
- 配置文件只由用户修改（需求 14.2），所以没有新增 AI 可写的入口。适配器文件本身是代码，和仓库里别的代码
  同样受写文件关卡管，也同样会在核心层的进程里运行：它是用户在配置里点名的文件，要按代码对待。
- 适配器文件要自己带齐依赖：只能 import 标准库和 `refcov`，不要靠兄弟文件（加载时不改 `sys.path`）。
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from refcov.sources import check_declarations
from refcov.store import Store, StoreError

BUILTIN = "markdown"
REQUIRED_FUNCS = ("split", "read", "facts")

_cache: dict = {}  # (路径, 修改时间, 大小) → 已加载的模块；文件改了就重新加载


class AdapterError(Exception):
    """适配器找不到或不合格。消息就是给用户看的原因。"""


def adapter_file(store: Store, name: str) -> Path:
    """配置里 `[adapters].<name>` 指向的适配器文件（已检查：相对路径、在仓库里、是存在的 .py 文件）。"""
    try:
        cfg = store.load_config()
    except StoreError as e:
        raise AdapterError(f"配置读不了，找不到适配器 {name!r}：{e}") from e
    table = cfg.get("adapters")
    if not isinstance(table, dict):
        raise AdapterError("配置里的 adapters 必须是一张表，例如 [adapters] 下写 mine = \"tools/my-adapter/adapter.py\"")
    if name not in table:
        known = "、".join(sorted(table)) or "（没有）"
        raise AdapterError(f"配置里没有适配器 {name!r}（现有：{known}）。要用户在配置文件的 [adapters] 里声明，"
                           "AI 不能改配置")
    value = table[name]
    if not isinstance(value, str) or not value.strip():
        raise AdapterError(f"配置里 adapters.{name} 必须是适配器文件的路径（字符串）")
    if Path(value).is_absolute() or value.startswith(("/", "\\")):
        raise AdapterError(f"adapters.{name} 要写相对仓库根目录的路径，不接受绝对路径：{value}")
    root = store.root.resolve()
    path = (root / value).resolve()  # resolve 去掉 ..，跟到链接指向的真实位置
    if not Path(os.path.normcase(path)).is_relative_to(os.path.normcase(root)):
        raise AdapterError(f"适配器文件要放在仓库里：{path} 不在 {root} 下")
    if path.suffix.lower() != ".py":
        raise AdapterError(f"适配器文件要是 .py 文件：{value}")
    if not path.is_file():
        raise AdapterError(f"找不到适配器文件：{value}")
    return path


def _module_name(name: str) -> str:
    return "refcov_adapter_" + "".join(c if c.isalnum() else "_" for c in name)


def _validate(mod, name: str, value: str) -> None:
    missing = [a for a in ("name", "kinds", *REQUIRED_FUNCS)
               if not hasattr(mod, a) or (a in REQUIRED_FUNCS and not callable(getattr(mod, a)))]
    if missing:
        raise AdapterError(f"适配器文件 {value} 缺少：{'、'.join(missing)}"
                           "（要有 name、kinds，以及 split、read、facts 三个函数）")
    if mod.name != name:
        raise AdapterError(f"适配器文件 {value} 里的 name 是 {mod.name!r}，和配置里的名字 {name!r} 不一致")
    kinds = mod.kinds
    if not isinstance(kinds, dict) or not kinds or not all(
            isinstance(k, str) and hasattr(d, "strict") and hasattr(d, "key") for k, d in kinds.items()):
        raise AdapterError(f"适配器文件 {value} 里的 kinds 必须是 {{单元类型: KindDecl}}，且不能为空")
    try:
        check_declarations(kinds)
    except ValueError as e:
        raise AdapterError(f"适配器文件 {value} 的类型声明不合格：{e}") from e


def load(store: Store, name: str):
    """返回适配器模块。`markdown` 是内置的；其他的按配置里的路径加载。出任何问题都抛 `AdapterError`。"""
    if name == BUILTIN:
        from refcov.adapters import markdown

        return markdown
    path = adapter_file(store, name)
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _cache:
        return _cache[key]
    value = store.rel(path)
    mod_name = _module_name(name)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise AdapterError(f"加载不了适配器文件：{value}")
    mod = importlib.util.module_from_spec(spec)
    old = sys.modules.get(mod_name)
    sys.modules[mod_name] = mod  # dataclass 等要从 sys.modules 里按模块名找回自己
    try:
        spec.loader.exec_module(mod)
        _validate(mod, name, value)
    except AdapterError:
        _restore(mod_name, old)
        raise
    except Exception as e:  # 适配器文件自己的错误：语法、import、运行出错
        _restore(mod_name, old)
        raise AdapterError(f"适配器文件 {value} 加载出错：{type(e).__name__}: {e}") from e
    for k in [k for k in _cache if k[0] == str(path)]:
        del _cache[k]  # 同一个文件的旧版本
    _cache[key] = mod
    return mod


def _restore(mod_name: str, old) -> None:
    if old is None:
        sys.modules.pop(mod_name, None)
    else:
        sys.modules[mod_name] = old
