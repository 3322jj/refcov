"""干净环境的安装验收（设计 7.2）。默认跳过，设 REFCOV_CLEAN_INSTALL=1 才跑。

只在临时目录里做：从提交的内容（git archive HEAD）打 wheel；用 uv tool install 装到临时的 UV_TOOL_DIR 和
UV_TOOL_BIN_DIR（找不到 uv 时退回 venv 加 pip）。子进程的环境里没有 PYTHONPATH，所以被导入的是安装好的那一份。
工作区里 refcov、refcov_mcp、integrations、pyproject.toml 有没提交的改动时直接失败：这个测试装的是 HEAD。
"""

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GATE = os.environ.get("REFCOV_CLEAN_INSTALL") == "1"
pytestmark = pytest.mark.skipif(not GATE, reason="设 REFCOV_CLEAN_INSTALL=1 才跑（在临时目录里装，要先提交）")

WIN = os.name == "nt"
PAYLOAD = {"hook_event_name": "PreToolUse", "tool_name": "fs_write",
           "tool_input": {"path": ".refcov/x", "text": "x"}, "session_id": "clean-install-test"}


def _exe(folder: Path, name: str) -> Path:
    return folder / (name + (".exe" if WIN else ""))


def _clean_env(extra=None) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(extra or {})
    return env


def _uv():
    found = shutil.which("uv")
    if found:
        return found
    cand = Path.home() / ".local" / "bin" / ("uv.exe" if WIN else "uv")
    return str(cand) if cand.is_file() else None


def _run(args, **kw):
    return subprocess.run(args, capture_output=True, timeout=900, **kw)


def _text(res) -> str:
    return (res.stdout + res.stderr).decode("utf-8", errors="replace")


@pytest.fixture(scope="module")
def installed(tmp_path_factory):
    dirty = _run(["git", "status", "--porcelain", "--", "refcov", "refcov_mcp", "integrations", "pyproject.toml"],
                 cwd=REPO).stdout.decode("utf-8").strip()
    if dirty:
        pytest.fail("工作区里这些路径有没提交的改动。这个测试装的是 HEAD，先提交再跑：\n" + dirty)
    tmp = tmp_path_factory.mktemp("clean")
    zip_path = tmp / "rc.zip"
    res = _run(["git", "archive", "--format=zip", "-o", str(zip_path), "HEAD"], cwd=REPO)
    assert res.returncode == 0, _text(res)
    src = tmp / "src"
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(src)
    wheels = tmp / "wheels"
    res = _run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheels), str(src)], env=_clean_env())
    assert res.returncode == 0, _text(res)[-2000:]
    (wheel,) = list(wheels.glob("refcov-*.whl"))
    uv = _uv()
    if uv:
        tool_dir, bin_dir = tmp / "tools", tmp / "bin"
        env = _clean_env({"UV_TOOL_DIR": str(tool_dir), "UV_TOOL_BIN_DIR": str(bin_dir)})
        res = _run([uv, "tool", "install", str(wheel)], env=env, cwd=str(tmp))
        assert res.returncode == 0, _text(res)[-2000:]
        refcov, python, prefix = _exe(bin_dir, "refcov"), _exe(tool_dir / "refcov" / ("Scripts" if WIN else "bin"), "python"), tool_dir / "refcov"
        mode = "uv"
    else:
        venv = tmp / "venv"
        assert _run([sys.executable, "-m", "venv", str(venv)], env=_clean_env()).returncode == 0
        scripts = venv / ("Scripts" if WIN else "bin")
        python = _exe(scripts, "python")
        res = _run([str(python), "-m", "pip", "install", str(wheel)], env=_clean_env())
        assert res.returncode == 0, _text(res)[-2000:]
        refcov, prefix, mode = _exe(scripts, "refcov"), venv, "venv"
    return {"wheel": wheel, "refcov": refcov, "python": python, "prefix": prefix, "mode": mode, "tmp": tmp}


def _fresh_project(installed, name: str) -> Path:
    proj = installed["tmp"] / name
    proj.mkdir()
    assert _run(["git", "init", "-q"], cwd=str(proj)).returncode == 0
    return proj


def _refcov(installed, proj: Path, *args):
    return _run([str(installed["refcov"]), *args], cwd=str(proj), env=_clean_env())


def test_wheel_contents(installed):
    """设计 7.2：wheel 里有接入层和 5 个模板，没有 apps/、site/、tests/、docs/、.kiro/。"""
    with zipfile.ZipFile(installed["wheel"]) as z:
        names = z.namelist()
    for need in ["integrations/__init__.py", "integrations/kiro/hook.py", "integrations/commands.py",
                 "refcov/cli.py", "refcov_mcp/server.py"]:
        assert need in names, need
    hooks = [n for n in names if n.startswith("integrations/kiro/hooks/refcov-") and n.endswith(".json")]
    assert len(hooks) == 5, hooks
    for bad in ("apps/", "site/", "tests/", "docs/", ".kiro/"):
        assert not [n for n in names if n.startswith(bad)], bad


def test_refcov_and_hook_module_come_from_the_install(installed, tmp_path):
    """设计 7.2 第 4 条：导入的是安装好的那一份，不是克隆里的。"""
    code = "import refcov, integrations.kiro.hook as h; print(refcov.__file__); print(h.__file__)"
    res = _run([str(installed["python"]), "-P", "-c", code], cwd=str(tmp_path), env=_clean_env())
    assert res.returncode == 0, _text(res)
    paths = [Path(line).resolve() for line in res.stdout.decode("utf-8").split()]
    prefix = installed["prefix"].resolve()
    for p in paths:
        assert str(p).startswith(str(prefix)), p
        assert not str(p).startswith(str(REPO.resolve())), p


def test_init_and_doctor_in_a_temp_project_and_second_init_is_identical(installed):
    proj = _fresh_project(installed, "proj-ok")
    assert _refcov(installed, proj, "init").returncode == 0
    res = _refcov(installed, proj, "doctor")
    assert res.returncode == 0, _text(res)
    before = {p.relative_to(proj).as_posix(): p.read_bytes() for p in proj.rglob("*") if p.is_file()}
    assert _refcov(installed, proj, "init").returncode == 0
    after = {p.relative_to(proj).as_posix(): p.read_bytes() for p in proj.rglob("*") if p.is_file()}
    assert after == before


def test_init_and_doctor_in_a_project_path_with_spaces_and_chinese(installed):
    """设计 7.2 的可选变体：项目路径带空格和中文，init 写出的绝对路径命令仍然能用，doctor 没有问题。"""
    proj = _fresh_project(installed, "项目 带 空格")
    assert _refcov(installed, proj, "init").returncode == 0
    res = _refcov(installed, proj, "doctor")
    assert res.returncode == 0, _text(res)


def _mcp_path(proj: Path) -> Path:
    return proj / ".kiro" / "settings" / "mcp.json"


@pytest.mark.parametrize("sabotage", ["delete_hook", "root_elsewhere", "interpreter_missing", "toml_syntax",
                                      "pending_sync"])
def test_doctor_finds_each_sabotage(installed, sabotage):
    """设计 7.2 第 7 条：每种人为破坏，doctor 退出码为 1，并报出来（有修法）。"""
    proj = _fresh_project(installed, f"proj-{sabotage}")
    assert _refcov(installed, proj, "init").returncode == 0
    if sabotage == "delete_hook":
        (proj / ".kiro" / "hooks" / "refcov-pretask.json").unlink()
    elif sabotage == "root_elsewhere":
        data = json.loads(_mcp_path(proj).read_text(encoding="utf-8"))
        data["mcpServers"]["refcov"]["args"][-1] = str(proj.parent / "elsewhere")
        _mcp_path(proj).write_text(json.dumps(data), encoding="utf-8")
    elif sabotage == "interpreter_missing":
        data = json.loads(_mcp_path(proj).read_text(encoding="utf-8"))
        data["mcpServers"]["refcov"]["command"] = str(proj.parent / "no-such" / "python.exe")
        _mcp_path(proj).write_text(json.dumps(data), encoding="utf-8")
    elif sabotage == "toml_syntax":
        (proj / "refcov.toml").write_bytes(b'mode = "unterminated\n')
    elif sabotage == "pending_sync":
        (proj / "refcov.toml").write_text('mode = "strict"\n[sources]\nfiles = ["notes/*.md"]\n', encoding="utf-8")
        (proj / "notes").mkdir()
        (proj / "notes" / "a.md").write_text("# A\n", encoding="utf-8")
    res = _refcov(installed, proj, "doctor")
    assert res.returncode == 1, _text(res)


def test_hook_command_written_by_init_is_blocked_when_run_by_the_shell(installed):
    """设计 7.2 第 3 条：init 写出的 refcov-pre-write.json 里的命令，原样用 shell 跑一次，
    喂一个写 .refcov/x 的输入，退出码必须是 2。"""
    proj = _fresh_project(installed, "proj-block")
    assert _refcov(installed, proj, "init").returncode == 0
    (hook,) = json.loads((proj / ".kiro" / "hooks" / "refcov-pre-write.json").read_text(encoding="utf-8"))["hooks"]
    command = hook["action"]["command"]
    res = subprocess.run(command, shell=True, input=json.dumps(PAYLOAD).encode("utf-8"), cwd=str(proj),
                         capture_output=True, env=_clean_env(), timeout=300)
    assert res.returncode == 2, _text(res)
    assert "RefCov" in res.stderr.decode("utf-8", errors="replace")
    assert not (proj / ".refcov" / "x").exists()
