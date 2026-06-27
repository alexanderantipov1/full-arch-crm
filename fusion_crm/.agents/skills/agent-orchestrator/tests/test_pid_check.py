"""Unit tests for pid_check.runtime_status()."""

# ruff: noqa: S603, S607
# Tests intentionally spawn a short subprocess to probe pid liveness.

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pid_check():
    spec = importlib.util.spec_from_file_location(
        "pid_check_under_test", SCRIPTS_DIR / "pid_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_none_pid_is_missing(pid_check):
    assert pid_check.runtime_status(None) == "missing"


def test_zero_pid_is_missing(pid_check):
    assert pid_check.runtime_status(0) == "missing"


def test_negative_pid_is_missing(pid_check):
    assert pid_check.runtime_status(-1) == "missing"


def test_non_int_pid_is_missing(pid_check):
    assert pid_check.runtime_status("123") == "missing"
    assert pid_check.runtime_status(1.5) == "missing"


def test_live_subprocess_reports_alive(pid_check):
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"]
    )
    try:
        assert pid_check.runtime_status(proc.pid) == "alive"
    finally:
        proc.terminate()
        proc.wait(timeout=2)


def test_exited_subprocess_reports_exited(pid_check):
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(0)"]
    )
    proc.wait(timeout=2)
    # Give the kernel a beat to reap any zombie before we probe.
    time.sleep(0.05)
    assert pid_check.runtime_status(proc.pid) in {"exited", "missing"}


def test_almost_certainly_unused_pid_is_exited_or_missing(pid_check):
    """A very high pid we did not spawn should not be reachable."""
    # 2_147_000_000 is well above any realistic PID; not enough to be
    # invalid on its face, but no process will own it.
    status = pid_check.runtime_status(2_147_000_000)
    assert status in {"exited", "missing"}
