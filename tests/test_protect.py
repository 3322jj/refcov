"""保护检查（任务 14，需求 14.1–14.5，设计 8 第 2 步）。hook.py 的 pre-write、pre-shell 分支。

"必须放行"的命令取自 2026-11-12 这个会话里 agent 真跑过的命令，加上 tasks.md 任务 14 列的几条；
"必须拦"的命令是 tasks.md 列的 4 条、用户 2026-11-12 定的 `.kiro/hooks`，以及几种绕法和坏输入。
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from refcov import cli
from refcov.store import Store

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "integrations" / "kiro" / "hook.py"

_spec = importlib.util.spec_from_file_location("refcov_kiro_hook", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

ALLOWED_SHELL = [
    None,  # control_pwsh_process 的 stop：command 是 null（docs/验证结果.md 第 7 项）
    "",
    "git status --short",
    "git -c core.quotepath=false status --short",
    "git diff --stat 2>$null",
    "git -c core.safecrlf=false diff --stat 2>$null",
    "git add docs/DEVLOG.md refcov/api.py refcov/cli.py tests/test_hook.py integrations/kiro/hook.py",
    "git add integrations/kiro/hooks/refcov-pre-shell.json integrations/kiro/refcov.example.toml",
    'git commit -m "task 13: control_pwsh_process hook matching verified"; "exit=$LASTEXITCODE"',
    'git push origin main 2>&1; "exit=$LASTEXITCODE"',
    "Start-Sleep -Seconds 10; git push origin main 2>&1",
    "git rev-parse HEAD",
    "python -m pytest -q -p no:warnings --no-header 2>&1 | Select-String -Pattern 'passed|failed'",
    "python -m pytest tests/test_hook.py tests/test_protect.py -q",
    "pytest tests/test_refcov_mcp.py",
    "python -m pytest tests/test_mcp_server.py -q",
    "python -m refcov report",
    "python -m refcov report --json --session sess_x",
    "refcov report --json",
    "python -m refcov check integrations/kiro/hook.py",
    "python -m refcov check-spec .kiro/specs/refcov-skeleton/requirements.md",
    'Start-Sleep -Seconds 90; "done"',
    '$r = Invoke-RestMethod -Uri "https://api.github.com/repos/3322jj/refcov/commits/b1f1827/check-runs"',
    "Get-Content docs/DEVLOG.md -Tail 5",
    "Select-String -Path .kiro/specs/refcov-skeleton/requirements.md -Pattern '^出处：' -Encoding utf8",
    "python $env:TEMP\\refcov_convert.py",
    "Get-ChildItem .kiro/steering, .kiro/specs/refcov-skeleton",
    "Write-Output trial-allow-1",
]

BLOCKED_SHELL = [
    # tasks.md 任务 14 列的 4 条
    "refcov add x --id y",
    "python -m refcov confirm x",
    "Add-Content .refcov/log.jsonl x",
    "python integrations/kiro/hook.py PreToolUse",
    # 状态目录和配置：出现就拦（读也拦，看记录用 MCP 的 report）
    "Get-Content .refcov\\log.jsonl",
    "git add .refcov/sources.json",
    "Set-Content refcov.toml 'mode = \"light\"'",
    "Copy-Item integrations/kiro/refcov.example.toml refcov.toml",
    'git commit -m "add refcov.toml"',
    # 钩子目录：出现就拦，正反斜杠都算（用户 2026-11-12 定，偏离需求原文）
    "Move-Item .kiro/hooks/refcov-pre-write.json $env:TEMP",
    "Remove-Item .kiro\\hooks\\refcov-pre-shell.json",
    "Get-ChildItem .KIRO/Hooks",
    "git add .kiro/hooks/refcov-prompt.json",
    # 运行钩子脚本、MCP 服务
    "python3 integrations\\kiro\\hook.py prompt",
    "python.exe d:\\agent\\kiro\\refcov\\integrations\\kiro\\hook.py post-mcp",
    "Get-Content x.json | python integrations/kiro/hook.py pre-shell",
    "python -m refcov_mcp --root .",
    # 只能用户跑的子命令
    "echo hi && refcov add docs/x.md --id x",
    "REFCOV ADD x --id y",
    "refcov.exe confirm docs/decisions/a.md",
    "(python -m refcov add x --id y)",
]


def protect(tool, tool_input):
    return hook.protect_reason({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input})


@pytest.mark.parametrize("command", ALLOWED_SHELL)
@pytest.mark.parametrize("tool", ["execute_pwsh", "control_pwsh_process", "execute_bash"])
def test_daily_commands_are_allowed(tool, command):
    """需求 14.4：本项目的日常命令（git add、跑测试、refcov report/check）放行。"""
    assert protect(tool, {"command": command}) is None


@pytest.mark.parametrize("command", BLOCKED_SHELL)
@pytest.mark.parametrize("tool", ["execute_pwsh", "control_pwsh_process", "execute_bash"])
def test_protected_commands_are_blocked(tool, command):
    """需求 14.2、14.4：碰状态目录、配置、钩子目录，运行钩子脚本或 MCP 服务，跑只能用户跑的子命令，都拦。"""
    reason = protect(tool, {"command": command})
    assert reason and "RefCov" in reason


@pytest.mark.parametrize("path", [
    ".refcov/log.jsonl", ".refcov\\sources.json", ".refcov", "./.refcov/x", "docs/../.refcov/x",
    ".REFCOV/Log.jsonl", "refcov.toml", "REFCOV.TOML", "./refcov.toml",
])
@pytest.mark.parametrize("tool", ["fs_write", "str_replace", "fs_append"])
def test_write_to_state_or_config_is_blocked(tool, path):
    """需求 14.1、14.2：写文件工具的目标在状态目录下或是配置文件，就拦。只看 tool_input.path。"""
    assert protect(tool, {"path": path, "text": "x"})


def test_absolute_paths_are_normalized():
    assert protect("fs_write", {"path": str(hook.ROOT / ".refcov" / "log.jsonl")})
    assert protect("fs_write", {"path": str(hook.ROOT / "refcov.toml")})
    assert protect("fs_write", {"path": str(hook.ROOT / "refcov" / "api.py")}) is None


@pytest.mark.parametrize("path", [
    "refcov/api.py", "refcov_mcp/server.py", "docs/refcov.toml", "integrations/kiro/refcov.example.toml",
    ".refcovx/a", "integrations/kiro/hook.py", ".kiro/hooks/refcov-pre-write.json", "docs/DEVLOG.md",
])
def test_ordinary_writes_are_allowed(path):
    """核心包 refcov/ 不是状态目录 .refcov/；写钩子目录由 Kiro 自己要求确认，这一层只管 shell。"""
    assert protect("fs_write", {"path": path, "text": "正文里写 .refcov 和 refcov.toml 也不拦"}) is None


def test_write_check_ignores_body():
    """需求 8.5、tech.md：只按 tool_input.path 判断，不在正文里搜。"""
    assert protect("str_replace", {"path": "docs/a.md", "oldStr": ".refcov/log.jsonl", "newStr": "refcov.toml"}) is None


def test_other_tools_are_not_checked():
    assert protect("mcp_refcov_report", {"format": "text"}) is None
    assert protect("read_file", {"path": ".refcov/log.jsonl"}) is None


@pytest.mark.parametrize("data", [
    {"tool_name": "fs_write", "tool_input": {"text": "x"}},  # 没有 path
    {"tool_name": "fs_write", "tool_input": {"path": 5}},
    {"tool_name": "execute_pwsh", "tool_input": {"command": ["refcov", "add"]}},
    {"tool_name": "execute_pwsh", "tool_input": "refcov add x"},
    {"tool_name": "execute_pwsh"},
])
def test_bad_input_raises(data):
    """需求 14.5：保护检查认不出输入时抛异常，由 main 按拦截处理（退出码 2）。"""
    with pytest.raises(Exception):
        hook.protect_reason({"hook_event_name": "PreToolUse", **data})


def test_user_only_matches_core():
    """设计 6：只能用户跑的子命令，核心层和 hook.py 各一份，必须一致。"""
    assert hook.USER_ONLY == cli.USER_ONLY == ("add", "confirm")


# ---- 经 subprocess 跑 hook.py（临时目录当仓库根目录）----

@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "integrations" / "kiro").mkdir(parents=True)
    shutil.copyfile(HOOK, tmp_path / "integrations" / "kiro" / "hook.py")
    return tmp_path


def run(root, event, data=None, raw=None):
    stdin = raw if raw is not None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    env = dict(os.environ, PYTHONPATH=str(REPO))
    return subprocess.run([sys.executable, str(root / "integrations" / "kiro" / "hook.py"), event],
                          input=stdin, capture_output=True, env=env, timeout=60, cwd=root)


def shell(command, tool="execute_pwsh"):
    return {"hook_event_name": "PreToolUse", "session_id": "sess_t", "tool_name": tool,
            "tool_input": {"command": command}}


def test_block_exits_2_with_reason_and_protect_record(repo):
    """拦截：退出码 2，原因写 stderr（tech.md），stdout 为空；追加一条 protect 记录（需求 14.3）。"""
    proc = run(repo, "pre-shell", shell("Add-Content .refcov/log.jsonl x"))
    assert proc.returncode == 2 and proc.stdout == b""
    assert "RefCov" in proc.stderr.decode("utf-8")
    (rec,) = [r for r in Store(repo).records() if r["type"] == "protect"]
    assert rec["session"] == "sess_t" and rec["kind"] == "shell" and rec["tool"] == "execute_pwsh"
    assert rec["target"] == "Add-Content .refcov/log.jsonl x"


def test_write_block_records_path(repo):
    data = {"hook_event_name": "PreToolUse", "session_id": "sess_t", "tool_name": "fs_write",
            "tool_input": {"path": "refcov.toml", "text": "mode = 'light'"}}
    proc = run(repo, "pre-write", data)
    assert proc.returncode == 2
    (rec,) = [r for r in Store(repo).records() if r["type"] == "protect"]
    assert rec["kind"] == "write" and rec["target"] == "refcov.toml"
    assert not (repo / "refcov.toml").exists()


def test_allow_exits_0_and_writes_nothing(repo):
    for event, data in (("pre-shell", shell("git add integrations/kiro/hook.py")),
                        ("pre-shell", shell(None, tool="control_pwsh_process")),
                        ("pre-write", {"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": "fs_write",
                                       "tool_input": {"path": "refcov/api.py", "text": "x"}})):
        proc = run(repo, event, data)
        assert proc.returncode == 0 and proc.stdout == b"" and proc.stderr == b""
    assert not (repo / ".refcov").exists()


@pytest.mark.parametrize("raw", [b"", b"{not json", b"[1, 2]", "\ufffd坏".encode("utf-8")])
def test_unreadable_input_blocks(repo, raw):
    """需求 14.5：保护检查里任何异常都按拦截处理。"""
    for event in ("pre-shell", "pre-write"):
        proc = run(repo, event, raw=raw)
        assert proc.returncode == 2, (event, raw, proc.stderr)
        assert "RefCov" in proc.stderr.decode("utf-8")


def test_block_works_when_core_is_missing(tmp_path):
    """需求 14.5：保护检查不 import 核心层；核心层加载失败时照样拦，只是不写 protect 记录。"""
    (tmp_path / "integrations" / "kiro").mkdir(parents=True)
    shutil.copyfile(HOOK, tmp_path / "integrations" / "kiro" / "hook.py")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONNOUSERSITE"] = "1"
    proc = subprocess.run([sys.executable, "-S", str(tmp_path / "integrations" / "kiro" / "hook.py"), "pre-shell"],
                          input=json.dumps(shell("refcov add x --id y")).encode("utf-8"),
                          capture_output=True, env=env, timeout=60, cwd=tmp_path)
    assert proc.returncode == 2 and "RefCov" in proc.stderr.decode("utf-8")
    assert not (tmp_path / ".refcov" / "log.jsonl").exists()


def test_hook_configs_match_design():
    """设计 8：两个钩子配置的触发器、匹配条件和命令。"""
    cfgs = {}
    for name in ("refcov-pre-write.json", "refcov-pre-shell.json"):
        (h,) = json.loads((REPO / "integrations" / "kiro" / "hooks" / name).read_text(encoding="utf-8"))["hooks"]
        cfgs[name] = h
    assert cfgs["refcov-pre-write.json"]["trigger"] == "PreToolUse"
    assert cfgs["refcov-pre-write.json"]["matcher"] == "^(fs_write|str_replace|fs_append)$"
    assert cfgs["refcov-pre-write.json"]["action"]["command"] == "python integrations/kiro/hook.py pre-write"
    assert cfgs["refcov-pre-shell.json"]["matcher"] == "^(execute_pwsh|control_pwsh_process|execute_bash)$"
    assert cfgs["refcov-pre-shell.json"]["action"]["command"] == "python integrations/kiro/hook.py pre-shell"
