"""Smoke tests for `run_wave.py` and `status_wave.py`."""

# ruff: noqa: S603
# Subprocess args are hard-coded test scaffolding (sys.executable + known
# script paths under the skill); no untrusted input flows in.

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
RUN_WAVE = SCRIPTS / "run_wave.py"
STATUS_WAVE = SCRIPTS / "status_wave.py"


def _wave_tasks(common_linear):
    return [
        {
            "task_id": "WAVE-1",
            "linear_id": common_linear,
            "linear_url": "https://linear.app/x/y",
            "linear_title": "wave one",
            "prompt": "echo one",
            "runtime": "codex",
            "mode": "print",
            "codex_full_auto": True,
            "workspace": "self",
            "allow_self_execute": True,
            "scope": "tiny",
        },
        {
            "task_id": "WAVE-2",
            "linear_id": common_linear,
            "linear_url": "https://linear.app/x/y",
            "linear_title": "wave two",
            "prompt": "echo two",
            "runtime": "claude-code",
            "mode": "print",
            "claude_permission_mode": "auto",
            "workspace": "self",
            "allow_self_execute": True,
            "scope": "tiny",
        },
    ]


def test_run_wave_print_mode_invokes_launcher_per_task(mission_dir, fake_runtime_path):
    tasks_file = mission_dir / "wave.json"
    tasks_file.write_text(
        json.dumps({"tasks": _wave_tasks("ENG-213")}, indent=2), encoding="utf-8",
    )
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, str(RUN_WAVE),
         "--tasks", str(tasks_file),
         "--mission", str(mission_dir),
         "--mode", "print"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"run_wave failed: {result.stderr}"
    # Both tasks should have produced a printed launch command line.
    assert "codex exec" in result.stdout
    assert "--dangerously-bypass-approvals-and-sandbox" in result.stdout
    assert "claude -p" in result.stdout
    assert "--permission-mode auto" in result.stdout


def test_run_wave_records_both_sessions_in_runtime_json(mission_dir, fake_runtime_path):
    tasks_file = mission_dir / "wave.json"
    tasks_file.write_text(
        json.dumps({"tasks": _wave_tasks("ENG-213")}, indent=2), encoding="utf-8",
    )
    env = os.environ.copy()
    subprocess.run(
        [sys.executable, str(RUN_WAVE),
         "--tasks", str(tasks_file),
         "--mission", str(mission_dir),
         "--mode", "print"],
        capture_output=True, text=True, env=env, check=True,
    )
    payload = json.loads((mission_dir / "runtime.json").read_text(encoding="utf-8"))
    task_ids = sorted(s["task_id"] for s in payload["sessions"])
    assert task_ids == ["WAVE-1", "WAVE-2"]


def test_status_wave_prints_session_summary(mission_dir, fake_runtime_path):
    tasks_file = mission_dir / "wave.json"
    tasks_file.write_text(
        json.dumps({"tasks": _wave_tasks("ENG-213")}, indent=2), encoding="utf-8",
    )
    env = os.environ.copy()
    subprocess.run(
        [sys.executable, str(RUN_WAVE),
         "--tasks", str(tasks_file),
         "--mission", str(mission_dir),
         "--mode", "print"],
        capture_output=True, text=True, env=env, check=True,
    )
    result = subprocess.run(
        [sys.executable, str(STATUS_WAVE), "--mission", str(mission_dir)],
        capture_output=True, text=True, env=env, check=False,
    )
    assert result.returncode == 0
    # Both task ids must surface in the status output.
    assert "WAVE-1" in result.stdout
    assert "WAVE-2" in result.stdout
