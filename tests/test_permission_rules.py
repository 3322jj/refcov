"""两条权限规则（设计第 5、6.4 节，需求 4）：init 只打印，doctor 分别查，缺哪条给哪条的提示。

进程内运行接入层。权限文件用临时路径，不碰真的用户目录；init 不写用户目录，用临时 USERPROFILE/HOME 证明。
"""

import contextlib
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from integrations.kiro import doctor  # noqa: E402
from integrations.kiro import init as kiro_init  # noqa: E402


def _git(root: Path) -> Path:
    (root / ".git").mkdir(parents=True, exist_ok=True)
    return root


def _quiet_init(repo: Path) -> str:
    out = io.StringIO()
    with mock.patch.object(kiro_init, "module_importable", lambda *a: True), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        assert kiro_init.run(repo, False) == 0
    return out.getvalue()


def _write_mcp(repo: Path, servers: dict) -> None:
    path = repo / ".kiro" / "settings" / "mcp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")


def _entry(module: str = "refcov_mcp") -> dict:
    return {"command": sys.executable, "args": ["-P", "-m", module, "--root", "x"], "disabled": False}


def _printed_rules(server: str = "refcov") -> str:
    return kiro_init.permission_rules_text(server)


def test_init_prints_the_two_rules_and_lists_read_tools_by_name(tmp_path):
    text = _quiet_init(_git(tmp_path))
    for tool in ("list_units", "read_unit", "check", "report", "propose_sources"):
        assert f'"refcov/{tool}"' in text
    assert '"refcov/apply_proposal"' in text
    assert "effect: allow" in text and "effect: ask" in text
    assert "refcov/*" not in text


def test_init_does_not_write_the_user_permission_file(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    _quiet_init(_git(tmp_path / "repo"))
    assert list(home.iterdir()) == []


def test_server_name_prefers_refcov_then_the_first_entry_that_runs_refcov_mcp(tmp_path):
    repo = _git(tmp_path)
    _write_mcp(repo, {"other": _entry("something_else"), "rc": _entry()})
    assert kiro_init.server_name(repo) == "rc"
    _write_mcp(repo, {"rc": _entry(), "refcov": _entry()})
    assert kiro_init.server_name(repo) == "refcov"


def test_server_name_defaults_when_mcp_json_is_missing_or_broken(tmp_path):
    repo = _git(tmp_path)
    assert kiro_init.server_name(repo) == "refcov"
    (repo / ".kiro" / "settings").mkdir(parents=True)
    (repo / ".kiro" / "settings" / "mcp.json").write_text("{not json", encoding="utf-8")
    assert kiro_init.server_name(repo) == "refcov"


def test_doctor_hints_both_rules_when_the_file_is_missing(tmp_path):
    checks = doctor.permission_checks("refcov", tmp_path / "missing.yaml")
    assert [c["level"] for c in checks] == ["hint", "hint"]
    assert any("读资料时每次都会弹窗" in c["message"] for c in checks)
    assert any("apply_proposal" in c["message"] for c in checks)
    assert all(c["fix"] for c in checks)


def test_doctor_is_quiet_when_both_rules_are_present(tmp_path):
    path = tmp_path / "permissions.yaml"
    path.write_text(_printed_rules(), encoding="utf-8")
    checks = doctor.permission_checks("refcov", path)
    assert [c["level"] for c in checks] == ["ok", "ok"]


def test_a_missing_read_tool_is_named_in_the_allow_hint(tmp_path):
    path = tmp_path / "permissions.yaml"
    path.write_text(_printed_rules().replace(', "refcov/report"', ""), encoding="utf-8")
    checks = doctor.permission_checks("refcov", path)
    assert [c["level"] for c in checks] == ["hint", "ok"]
    assert "refcov/report" in checks[0]["message"]


def test_a_missing_ask_rule_is_hinted_with_the_always_allow_risk(tmp_path):
    path = tmp_path / "permissions.yaml"
    path.write_text(_printed_rules().split("  - capability: mcp\n    match: [\"refcov/apply_proposal\"]")[0],
                    encoding="utf-8")
    checks = doctor.permission_checks("refcov", path)
    assert [c["level"] for c in checks] == ["ok", "hint"]
    assert "Always allow" in checks[1]["message"]


def test_rules_for_another_server_name_do_not_count(tmp_path):
    path = tmp_path / "permissions.yaml"
    path.write_text(_printed_rules("other"), encoding="utf-8")
    checks = doctor.permission_checks("refcov", path)
    assert [c["level"] for c in checks] == ["hint", "hint"]


def test_flow_style_rules_are_not_found_and_the_hint_says_so(tmp_path):
    path = tmp_path / "permissions.yaml"
    path.write_text('rules:\n  - {capability: mcp, match: ["refcov/apply_proposal"], effect: ask}\n', encoding="utf-8")
    checks = doctor.permission_checks("refcov", path)
    assert checks[1]["level"] == "hint"


def test_doctor_permission_checks_never_return_a_problem(tmp_path):
    for content in ("", "garbage: [", _printed_rules()):
        path = tmp_path / "p.yaml"
        path.write_text(content, encoding="utf-8")
        assert all(c["level"] in ("ok", "hint") for c in doctor.permission_checks("refcov", path))
