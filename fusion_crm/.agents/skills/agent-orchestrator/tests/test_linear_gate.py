"""Linear gate: missing --linear-id or --linear-url must abort the launcher."""

# ruff: noqa: S603
# Subprocess args are hard-coded test scaffolding (sys.executable + a known
# launcher path under the skill); no untrusted input flows in.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parent.parent / "scripts" / "launch_worker.py"


def _common_args(mission, **overrides):
    args = [
        "--mission", str(mission),
        "--runtime", "codex",
        "--mode", "print",
        "--task-id", "GATE-1",
        "--linear-id", "ENG-213",
        "--linear-url", "https://linear.app/x/y",
        "--linear-title", "x",
        "--prompt", "echo ok", "--workspace", "self", "--allow-self-execute", "--scope", "tiny",
    ]
    # Apply overrides as raw replacement pairs.
    for key, value in overrides.items():
        flag = "--" + key.replace("_", "-")
        if flag in args:
            idx = args.index(flag)
            args[idx + 1] = value
    return args


def test_linear_gate_rejects_empty_id(tmp_path):
    args = _common_args(tmp_path, linear_id="   ")
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Linear gate" in (result.stderr + result.stdout)


def test_linear_gate_rejects_empty_url(tmp_path):
    args = _common_args(tmp_path, linear_url="   ")
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Linear gate" in (result.stderr + result.stdout)


def test_linear_gate_passes_with_valid_ids(tmp_path):
    args = _common_args(tmp_path)
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "codex exec" in result.stdout
