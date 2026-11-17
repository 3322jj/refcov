"""钩子的 errors.log 兜底（2026-11-17，Claude 审 a4969bc 时提出）：核心层导入不了时，log_error 照样写日志。
钩子出错往往正是因为核心层导入不了，这时候最需要日志。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "integrations" / "kiro" / "hook.py"


def test_log_error_still_writes_when_the_core_layer_cannot_be_imported(tmp_path):
    """性质：只把 hook.py 复制到一个没有核心层的目录，用 python -S 运行（子进程，不带仓库的路径），
    调用 log_error 以后 errors.log 里有这一行，而且核心层的 Store 确实没有被导入。"""
    copy = tmp_path / "integrations" / "kiro"
    copy.mkdir(parents=True)
    shutil.copy(HOOK, copy / "hook.py")
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('hook_copy', {str(copy / 'hook.py')!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "mod.log_error('pre-write', 'core-missing-check', ValueError('boom'))\n"
        "print('core imported:', 'refcov.store' in sys.modules)\n",
        encoding="utf-8",
    )
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    res = subprocess.run([sys.executable, "-S", str(driver)], cwd=str(tmp_path),
                         capture_output=True, text=True, env=env, timeout=120)
    assert res.returncode == 0, res.stderr
    assert "core imported: False" in res.stdout
    entry = json.loads((tmp_path / ".refcov" / "errors.log").read_text(encoding="utf-8").splitlines()[-1])
    assert entry["event"] == "pre-write"
    assert entry["reason"] == "core-missing-check"
    assert entry["error"] == "ValueError"
