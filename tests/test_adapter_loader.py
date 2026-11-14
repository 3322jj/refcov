"""按名字选适配器：配置的 `[adapters]` 写适配器文件的路径，核心层用 importlib 从文件加载
（镜头应用需求第二部分 C4，骨架需求 2.1、2.2、2.6、14.2）。

适配器是测试里现写的 .py 文件，放在带连字符的目录 apps/fake-shot/ 下（不能当包名导入，正是用路径写法的原因）。
"""

import shutil

import pytest

from refcov import api, cli
from refcov.adapters import loader, markdown
from refcov.sources import RegisterError, register
from refcov.store import Store

LIST_MD = "# probe\n\n## shot-a\nstart: 0.0\n\n## shot-b\nstart: 5.0\n"

ADAPTER = '''
from dataclasses import dataclass

from refcov.sources import Image, KindDecl, find_unit, make_units

name = "fake"
kinds = {"shot": KindDecl(strict=STRICT)}


@dataclass
class Probe:  # dataclass 要能从 sys.modules 里按模块名找回自己
    x: int = 1


def split(data, file_name):
    secs = []
    for block in data.decode("utf-8-sig").split("## ")[1:]:
        title, _, body = block.partition("\\n")
        secs.append((title.strip(), body))
    return make_units(secs, "shot")


def read(data, file_name, unit_id):
    u = find_unit(split(data, file_name), unit_id)
    return [f"fake {u.id}", Image(b"IMG", "image/png")]


def facts(data, file_name, unit_id):
    return {}
'''


def adapter_source(strict=True):
    return ADAPTER.replace("STRICT", str(strict))


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "list.md").write_text(LIST_MD, encoding="utf-8")
    (tmp_path / "apps" / "fake-shot").mkdir(parents=True)
    (tmp_path / "apps" / "fake-shot" / "adapter.py").write_text(adapter_source(), encoding="utf-8")
    (tmp_path / "refcov.toml").write_text('[adapters]\nfake = "apps/fake-shot/adapter.py"\n', encoding="utf-8")
    return tmp_path


def state(store):
    return ({p.relative_to(store.state_dir).as_posix(): p.read_bytes() for p in store.state_dir.rglob("*")
             if p.is_file()} if store.state_dir.exists() else None)


def test_register_read_and_check_with_a_declared_adapter(repo):
    """登记、列单元、读（文字加图片）、必看集合都认配置里声明的适配器；类型声明 strict=True 所以两个镜头都必看。"""
    store = Store(repo)
    res = register(store, "docs/list.md", "vid", adapter="fake")
    assert res.written and res.entry["adapter"] == "fake"
    assert [u["id"] for u in res.entry["units"]] == ["shot-a", "shot-b"]
    assert [(u["id"], u["kind"]) for u in api.list_units(store, "vid")] == [("shot-a", "shot"), ("shot-b", "shot")]
    assert api.check(store)["required"] == 2 and not api.check(store)["pass"]
    r = api.read(store, "vid", "shot-a")
    assert r.texts == ["fake shot-a"] and len(r.images) == 1 and r.images[0].data == b"IMG"
    api.read(store, "vid", "shot-b")
    assert api.check(store)["pass"] and store.verify_chain().ok


def test_kind_declaration_comes_from_the_adapter_and_edits_are_reloaded(repo):
    """改了适配器文件（strict 改成 False）：下一次加载就按新声明算，必看集合变空。"""
    store = Store(repo)
    register(store, "docs/list.md", "vid", adapter="fake")
    assert api.check(store)["required"] == 2
    (repo / "apps" / "fake-shot" / "adapter.py").write_text(adapter_source(strict=False) + "\n# 改了\n",
                                                           encoding="utf-8")
    assert api.check(store)["required"] == 0


def test_cli_add_with_adapter_option(repo, monkeypatch, capsys):
    """`refcov add <文件> --id <ID> --adapter <名字>`；不写 --adapter 时是文档适配器。"""
    monkeypatch.chdir(repo)
    assert cli.main(["add", "docs/list.md", "--id", "vid", "--adapter", "fake"]) == 0
    assert "已登记 vid：2 个单元" in capsys.readouterr().out
    assert Store(repo).read_sources()["sources"][0]["adapter"] == "fake"
    assert cli.main(["add", "docs/list.md", "--id", "doc"]) == 0
    assert [s["adapter"] for s in Store(repo).read_sources()["sources"]] == ["fake", "markdown"]
    assert cli.main(["add", "docs/list.md", "--id", "bad", "--adapter", "nope"]) == 1
    assert "配置里没有适配器 'nope'" in capsys.readouterr().err


def test_reregistering_with_another_adapter_updates_the_entry(repo):
    """同一个文件换适配器重新登记：不算"没变"，清单里的适配器和单元都更新；同一个适配器再登记一次才是"没变"。"""
    store = Store(repo)
    assert register(store, "docs/list.md", "vid").entry["adapter"] == "markdown"
    again = register(store, "docs/list.md", "vid", adapter="fake")
    assert again.written and again.changed and again.entry["adapter"] == "fake"
    assert not register(store, "docs/list.md", "vid", adapter="fake").written
    assert store.verify_chain().ok


def test_markdown_is_builtin_and_cannot_be_redirected(repo):
    """`markdown` 永远是内置的文档适配器，配置里写同名项也不改它。"""
    (repo / "refcov.toml").write_text('[adapters]\nmarkdown = "apps/fake-shot/adapter.py"\n', encoding="utf-8")
    assert loader.load(Store(repo), "markdown") is markdown


def test_no_adapters_table_behaves_as_before(tmp_path):
    """不写 [adapters]：文档适配器照旧，别的名字报"配置里没有"。"""
    (tmp_path / ".git").mkdir()
    (tmp_path / "list.md").write_text(LIST_MD, encoding="utf-8")
    store = Store(tmp_path)
    assert register(store, "list.md", "doc").entry["adapter"] == "markdown"
    with pytest.raises(RegisterError, match="配置里没有适配器 'fake'"):
        register(store, "list.md", "vid", adapter="fake")


def break_adapter(kind, repo):
    """返回 (配置文本或 None, 适配器文件名, 适配器源码, 期望的报错片段)。"""
    ok_cfg = '[adapters]\nfake = "apps/fake-shot/adapter.py"\n'
    src = adapter_source()
    absolute = repo / "apps" / "fake-shot" / "adapter.py"  # 本平台上的绝对路径；TOML 用单引号字面量，不转义反斜杠
    return {
        "no-config": (None, "adapter.py", src, "配置里没有适配器"),
        "not-a-table": ("adapters = 7\n", "adapter.py", src, "必须是一张表"),
        "absolute": (f"[adapters]\nfake = '{absolute}'\n", "adapter.py", src, "不接受绝对路径"),
        "outside": ('[adapters]\nfake = "../outside.py"\n', "adapter.py", src, "不在"),
        "missing-file": ('[adapters]\nfake = "apps/fake-shot/none.py"\n', "adapter.py", src, "找不到适配器文件"),
        "not-py": ('[adapters]\nfake = "apps/fake-shot/adapter.txt"\n', "adapter.txt", src, "要是 .py 文件"),
        "non-string": ("[adapters]\nfake = 5\n", "adapter.py", src, "必须是适配器文件的路径"),
        "missing-attrs": (ok_cfg, "adapter.py", 'name = "fake"\n', "缺少"),
        "not-callable": (ok_cfg, "adapter.py", src.replace("def facts", "facts = 1\ndef _facts"), "缺少"),
        "name-mismatch": (ok_cfg, "adapter.py", src.replace('name = "fake"', 'name = "other"'), "不一致"),
        "import-error": (ok_cfg, "adapter.py", "import no_such_module_xyz\n" + src, "加载出错"),
        "syntax-error": (ok_cfg, "adapter.py", "def (:\n", "加载出错"),
        "bad-kinds": (ok_cfg, "adapter.py", src.replace("KindDecl(strict=True)", "KindDecl(strict=False, key=True)"),
                      "类型声明不合格"),
        "empty-kinds": (ok_cfg, "adapter.py", src.replace('{"shot": KindDecl(strict=True)}', "{}"), "不能为空"),
    }[kind]


@pytest.mark.parametrize("kind", ["no-config", "not-a-table", "absolute", "outside", "missing-file", "not-py",
                                  "non-string", "missing-attrs", "not-callable", "name-mismatch", "import-error",
                                  "syntax-error", "bad-kinds", "empty-kinds"])
def test_unusable_adapters_fail_registration_without_touching_state(repo, kind):
    """配置或适配器文件有问题：登记失败并说明原因，状态目录里什么都没写（需求 1.5）。"""
    cfg, fname, src, expect = break_adapter(kind, repo)
    if cfg is None:
        (repo / "refcov.toml").unlink()
    else:
        (repo / "refcov.toml").write_text(cfg, encoding="utf-8")
    (repo / "apps" / "fake-shot" / fname).write_text(src, encoding="utf-8")
    (repo.parent / "outside.py").write_text(src, encoding="utf-8")
    store = Store(repo)
    with pytest.raises(RegisterError, match=expect):
        register(store, "docs/list.md", "vid", adapter="fake")
    assert state(store) is None


def test_undeclared_unit_kind_is_refused(repo):
    """适配器拆出的单元类型不在它自己的 kinds 里：登记失败，什么都不写。"""
    p = repo / "apps" / "fake-shot" / "adapter.py"
    p.write_text(adapter_source().replace('make_units(secs, "shot")', 'make_units(secs, "ghost")'), encoding="utf-8")
    store = Store(repo)
    with pytest.raises(RegisterError, match="没有声明：ghost"):
        register(store, "docs/list.md", "vid", adapter="fake")
    assert state(store) is None


def test_split_error_fails_registration(repo):
    """适配器的 split 抛异常：登记失败，不改清单、缓存、日志。"""
    p = repo / "apps" / "fake-shot" / "adapter.py"
    p.write_text(adapter_source().replace('secs = []', 'raise RuntimeError("坏了")\n    secs = []', 1),
                 encoding="utf-8")
    store = Store(repo)
    with pytest.raises(RegisterError, match="拆分失败：RuntimeError: 坏了"):
        register(store, "docs/list.md", "vid", adapter="fake")
    assert state(store) is None


def test_removed_declaration_blocks_reads_but_not_checks(repo):
    """用户从配置里删了声明：读取报错（不退回文档适配器）；check 和 report 照常出结果，单元按严格必看算。"""
    store = Store(repo)
    register(store, "docs/list.md", "vid", adapter="fake")
    (repo / "refcov.toml").unlink()
    before = state(store)
    with pytest.raises(api.ReadError, match="用不了"):
        api.read(store, "vid", "shot-a")
    assert state(store) == before
    assert api.check(store)["required"] == 2
    assert api.report(store, None)["sources"][0]["id"] == "vid"
