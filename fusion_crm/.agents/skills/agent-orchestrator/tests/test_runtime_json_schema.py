"""Validate `runtime.json` shape against the contract documented in
`.agents/orchestration/CLAUDE.md`.

Without `jsonschema`, the validation is implemented manually: required keys,
allowed enum values, and types. The launcher writes `runtime.json` via
`update_runtime()`, so this test exercises the public artifact, not internals.
"""

# ruff: noqa: S603
# Subprocess args are hard-coded test scaffolding (sys.executable + a known
# launcher path under the skill); no untrusted input flows in.

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parent.parent / "scripts" / "launch_worker.py"

# Status enum from `.agents/orchestration/CLAUDE.md` Runtime Contract.
ALLOWED_SESSION_STATUS = {
    "planned", "assigned", "running", "waiting", "blocked",
    "report-ready", "verification-failed", "ready-for-integration",
    "merged", "cancelled",
}
ALLOWED_HANDOFF_STATUS = {
    "proposed", "accepted", "rejected", "in-progress", "completed",
}

REQUIRED_SESSION_KEYS = {
    "id", "role", "agent", "task_id", "linear_issue_id", "linear_issue_url",
    "linear_status", "linear_title", "status", "phase", "worktree", "branch",
    "last_activity", "needs_human", "risk", "current_note",
}
REQUIRED_HANDOFF_KEYS = {
    "id", "created_at", "task_id", "linear_issue_id",
    "from_role", "from_agent", "to_role", "to_agent", "reason", "status",
}


@pytest.fixture
def fresh_runtime(mission_dir, fake_runtime_path):
    """Run the launcher in print mode against a tmp mission, return the parsed runtime.json."""
    env = os.environ.copy()
    args = [
        sys.executable, str(LAUNCHER),
        "--mission", str(mission_dir),
        "--runtime", "codex",
        "--mode", "print",
        "--task-id", "SCHEMA-1",
        "--linear-id", "ENG-213",
        "--linear-url", "https://linear.app/x/y",
        "--linear-title", "schema",
        "--prompt", "echo ok",
        # M-2: avoid worktree provisioning in this hermetic test.
        "--workspace", "self",
        "--allow-self-execute",
        "--scope", "tiny",
    ]
    subprocess.run(args, capture_output=True, text=True, env=env, check=True)
    return json.loads((mission_dir / "runtime.json").read_text(encoding="utf-8"))


def test_top_level_keys_present(fresh_runtime):
    for key in ("mission_id", "updated_at", "handoffs", "sessions"):
        assert key in fresh_runtime, f"runtime.json missing top-level key: {key}"


def test_mission_id_is_string(fresh_runtime):
    assert isinstance(fresh_runtime["mission_id"], str)
    assert fresh_runtime["mission_id"]


def test_updated_at_iso_zulu(fresh_runtime):
    value = fresh_runtime["updated_at"]
    assert isinstance(value, str)
    assert value.endswith("Z"), f"updated_at must use Zulu suffix: {value!r}"


def test_sessions_have_required_keys(fresh_runtime):
    sessions = fresh_runtime["sessions"]
    assert sessions, "no sessions recorded"
    for session in sessions:
        missing = REQUIRED_SESSION_KEYS - session.keys()
        assert not missing, f"session missing keys: {missing}"


def test_sessions_status_is_allowed_enum(fresh_runtime):
    for session in fresh_runtime["sessions"]:
        assert session["status"] in ALLOWED_SESSION_STATUS, (
            f"session status {session['status']!r} not in allowed enum"
        )


def test_sessions_needs_human_is_bool(fresh_runtime):
    for session in fresh_runtime["sessions"]:
        assert isinstance(session["needs_human"], bool)


def test_handoffs_have_required_keys(fresh_runtime):
    for handoff in fresh_runtime["handoffs"]:
        missing = REQUIRED_HANDOFF_KEYS - handoff.keys()
        assert not missing, f"handoff missing keys: {missing}"


def test_handoffs_status_is_allowed_enum(fresh_runtime):
    for handoff in fresh_runtime["handoffs"]:
        assert handoff["status"] in ALLOWED_HANDOFF_STATUS, (
            f"handoff status {handoff['status']!r} not in allowed enum"
        )
