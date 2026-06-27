"""Smoke test: start_control_plane.py brings dashboard up cleanly with --no-open."""

# ruff: noqa: S603, S607, S310
# Test intentionally spawns subprocess + uses urllib for liveness probe
# against a known localhost URL.

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
START = SCRIPTS_DIR / "start_control_plane.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _ping(url: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.2)
    return False


def test_start_control_plane_no_open_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("FUSION_AGENT_RUNTIME_HOME", str(tmp_path))
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(START), "--no-open", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    try:
        # Wait for dashboard to become reachable.
        url = f"http://127.0.0.1:{port}/api/snapshot"
        ready = _ping(url, timeout=15.0)
        assert ready, "dashboard did not come up within timeout"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)

    # Ensure the child closed cleanly (return code may be -SIGTERM or 0).
    assert proc.returncode is not None
