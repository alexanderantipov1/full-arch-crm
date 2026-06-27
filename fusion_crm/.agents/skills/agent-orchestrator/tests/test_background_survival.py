"""Integration test for `--mode background`: worker must survive launcher exit.

This is the direct regression guard for the 2026-05-20 incident in which
codex / claude-code workers exited immediately and wrote 0-byte logs because
`subprocess.Popen` lacked `start_new_session=True`. The fix uses a PATH-shim
fake binary so the test runs hermetically without the real codex / claude CLIs.
"""

# ruff: noqa: S603
# Subprocess args are hard-coded test scaffolding (sys.executable + a known
# launcher path under the skill); no untrusted input flows in.

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parent.parent / "scripts" / "launch_worker.py"


def _launch(mission, runtime, env):
    args = [
        sys.executable, str(LAUNCHER),
        "--mission", str(mission),
        "--runtime", runtime,
        "--mode", "background",
        "--task-id", f"BG-{runtime.upper()}",
        "--linear-id", "ENG-213",
        "--linear-url", "https://linear.app/x/y",
        "--linear-title", "smoke",
        "--prompt", "echo ok", "--workspace", "self", "--allow-self-execute", "--scope", "tiny",
    ]
    result = subprocess.run(args, capture_output=True, text=True, env=env, check=False)
    return result


def _log_path(mission, task_id):
    matches = glob.glob(str(mission / "logs" / f"{task_id}-*.log"))
    assert matches, f"no log file matching {task_id} in {mission/'logs'}"
    return Path(matches[0])


@pytest.mark.parametrize("runtime", ["codex", "claude-code"])
def test_background_worker_survives_launcher_exit(mission_dir, fake_runtime_path, runtime):
    env = os.environ.copy()
    result = _launch(mission_dir, runtime, env)

    assert result.returncode == 0, f"launcher failed: {result.stderr}"
    assert "Started " in result.stdout

    # Give the shim time to finish sleeping (it sleeps 2s).
    time.sleep(3)

    log_path = _log_path(mission_dir, f"BG-{runtime.upper()}")
    contents = log_path.read_text(encoding="utf-8")

    assert contents != "", "log file is empty — SIGHUP regression?"
    assert "SHIM_START" in contents, "worker never wrote start marker"
    assert "SHIM_END" in contents, "worker died before writing end marker — SIGHUP regression"


@pytest.mark.parametrize("runtime", ["codex", "claude-code"])
def test_background_worker_reparented_to_init(mission_dir, fake_runtime_path, runtime):
    """ppid=1 in the log proves `start_new_session=True` detached the worker."""
    env = os.environ.copy()
    _launch(mission_dir, runtime, env)
    time.sleep(3)

    log_path = _log_path(mission_dir, f"BG-{runtime.upper()}")
    contents = log_path.read_text(encoding="utf-8")
    # Shim prints `SHIM_START pid=<pid> ppid=<ppid> name=<name>` — after the
    # launcher exits, the kernel reparents the orphan to init (pid 1 on Linux
    # or launchd pid 1 on macOS). If `start_new_session=True` were missing,
    # the child would die before printing this line.
    assert "ppid=1" in contents, (
        f"worker not reparented to init — start_new_session regression. log:\n{contents}"
    )


def test_background_writes_runtime_json_state(mission_dir, fake_runtime_path):
    env = os.environ.copy()
    result = _launch(mission_dir, "codex", env)
    assert result.returncode == 0

    payload = json.loads((mission_dir / "runtime.json").read_text(encoding="utf-8"))
    sessions = payload["sessions"]
    assert sessions, "no session recorded"
    session = sessions[-1]
    assert session["status"] == "running"
    assert session["launch_mode"] == "background"
    assert "pid" in session
    assert isinstance(session["pid"], int)
