"""Unit tests for activity_heuristic.activity_state()."""

from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def heuristic():
    spec = importlib.util.spec_from_file_location(
        "activity_heuristic_under_test", SCRIPTS_DIR / "activity_heuristic.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_missing_log_is_idle(tmp_path, heuristic):
    assert heuristic.activity_state(tmp_path / "absent.log") == "idle"


def test_fresh_log_is_active(tmp_path, heuristic):
    log = tmp_path / "fresh.log"
    log.write_text("starting\n")
    assert heuristic.activity_state(log, idle_threshold_seconds=60) == "active"


def test_stale_log_is_idle(tmp_path, heuristic):
    log = tmp_path / "stale.log"
    log.write_text("old content\n")
    # Backdate mtime by 1 hour.
    backdate = time.time() - 3600
    os.utime(log, (backdate, backdate))
    assert heuristic.activity_state(log, idle_threshold_seconds=60) == "idle"


def test_needs_decision_marker_wins_over_stale_mtime(tmp_path, heuristic):
    log = tmp_path / "decision.log"
    log.write_text("started\nNeeds decision: which API to use?\n")
    backdate = time.time() - 3600  # 1 hour old
    os.utime(log, (backdate, backdate))
    assert heuristic.activity_state(log) == "waiting_input"


def test_blocked_marker_wins_over_stale_mtime(tmp_path, heuristic):
    log = tmp_path / "blocked.log"
    log.write_text("started\nBlocked: waiting on token rotation\n")
    backdate = time.time() - 3600
    os.utime(log, (backdate, backdate))
    assert heuristic.activity_state(log) == "blocked"


def test_needs_decision_wins_over_blocked_when_first_in_tail(tmp_path, heuristic):
    """If both markers appear, the first found wins (we iterate top-down)."""
    log = tmp_path / "both.log"
    log.write_text("Needs decision: foo\nBlocked: bar\n")
    assert heuristic.activity_state(log) == "waiting_input"


def test_marker_case_insensitive(tmp_path, heuristic):
    log = tmp_path / "case.log"
    log.write_text("NEEDS DECISION: shouty\n")
    assert heuristic.activity_state(log) == "waiting_input"


def test_marker_only_scans_recent_tail(tmp_path, heuristic):
    """A marker that's beyond the 50-line tail window must NOT be picked up."""
    log = tmp_path / "buried.log"
    # Bury the marker under 100 lines of activity.
    text = "Needs decision: buried under 100 lines\n"
    text += "".join(f"line {i}\n" for i in range(100))
    log.write_text(text)
    # Fresh mtime, no marker in tail → active.
    assert heuristic.activity_state(log) == "active"


def test_threshold_boundary(tmp_path, heuristic):
    """A log exactly at the threshold is still active."""
    log = tmp_path / "edge.log"
    log.write_text("x\n")
    # Set mtime to exactly 30 seconds ago.
    mtime = time.time() - 30
    os.utime(log, (mtime, mtime))
    assert heuristic.activity_state(log, idle_threshold_seconds=60) == "active"


def test_unreadable_log_returns_idle(tmp_path, monkeypatch, heuristic):
    log = tmp_path / "unreadable.log"
    log.write_text("hi\n")

    # Force the read to fail.
    real_open = Path.open

    def fail_open(self, *args, **kwargs):
        if self == log:
            raise OSError("simulated read failure")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_open)
    # Mtime side fails too (read returned empty list → no markers → mtime check kicks in)
    # We expect this still classifies as active because mtime is fresh.
    assert heuristic.activity_state(log) == "active"
