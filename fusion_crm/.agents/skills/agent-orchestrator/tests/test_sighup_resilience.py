"""SIGHUP regression guard.

The 2026-05-20 incident: a subshell launches the launcher; the subshell exits;
its controlling terminal closes; if `start_new_session=True` is missing on the
Popen call, the worker dies from SIGHUP before writing anything. This test
reproduces that exact pattern using a fake binary shim and asserts the worker
survives.
"""

# ruff: noqa: S603, S607
# S603: subprocess args are hard-coded test scaffolding.
# S607: `bash` is invoked by short name on purpose — the test relies on the
#       developer's $PATH-resolved shell to reproduce the original SIGHUP
#       scenario as it would happen from a user terminal.

from __future__ import annotations

import glob
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parent.parent / "scripts" / "launch_worker.py"


def _wait_for_log(log_path: Path, expected: str, timeout_s: float = 6.0) -> str:
    """Poll until expected marker appears or timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if log_path.is_file():
            text = log_path.read_text(encoding="utf-8")
            if expected in text:
                return text
        time.sleep(0.2)
    return log_path.read_text(encoding="utf-8") if log_path.is_file() else ""


def test_worker_survives_subshell_exit(mission_dir, fake_runtime_path):
    """Launcher run inside a subshell; subshell exits; worker must finish writing."""
    # Pass the active PATH (which includes the fake shim) down to the subshell.
    env = os.environ.copy()

    cmd = [
        sys.executable, str(LAUNCHER),
        "--mission", str(mission_dir),
        "--runtime", "codex",
        "--mode", "background",
        "--task-id", "SIGHUP-1",
        "--linear-id", "ENG-213",
        "--linear-url", "https://linear.app/x/y",
        "--linear-title", "sighup",
        "--prompt", "echo ok", "--workspace", "self", "--allow-self-execute", "--scope", "tiny",
    ]

    # Quote args for bash so the launcher receives exactly the same argv.
    quoted = " ".join(shlex.quote(c) for c in cmd)
    # `bash -c "..."` runs the launcher and exits as soon as the launcher
    # exits. The launcher must detach the worker via setsid so the worker
    # survives this subshell exit.
    result = subprocess.run(
        ["bash", "-c", quoted],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"subshell-driven launcher failed: {result.stderr}"

    # Locate the worker log.
    matches = glob.glob(str(mission_dir / "logs" / "SIGHUP-1-*.log"))
    assert matches, "no log file produced"
    log_path = Path(matches[0])

    text = _wait_for_log(log_path, "SHIM_END")
    assert "SHIM_START" in text, "worker never started — launcher itself broken"
    assert "SHIM_END" in text, (
        f"worker died before finishing — SIGHUP regression. log:\n{text}"
    )
    # ppid=1 confirms it was reparented away from the subshell.
    assert "ppid=1" in text


def test_worker_log_grows_after_subshell_exits(mission_dir, fake_runtime_path):
    """Concrete check: log size at launcher exit < log size after worker finishes."""
    env = os.environ.copy()
    cmd = [
        sys.executable, str(LAUNCHER),
        "--mission", str(mission_dir),
        "--runtime", "codex",
        "--mode", "background",
        "--task-id", "SIGHUP-2",
        "--linear-id", "ENG-213",
        "--linear-url", "https://linear.app/x/y",
        "--linear-title", "sighup",
        "--prompt", "echo ok", "--workspace", "self", "--allow-self-execute", "--scope", "tiny",
    ]
    subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
    matches = glob.glob(str(mission_dir / "logs" / "SIGHUP-2-*.log"))
    log_path = Path(matches[0])

    # Right after the launcher exits.
    early = log_path.stat().st_size

    # Wait for the shim to finish its sleep.
    time.sleep(3)
    late = log_path.stat().st_size

    assert late > early, (
        f"log did not grow after launcher exit: early={early} late={late} — "
        "SIGHUP regression"
    )
