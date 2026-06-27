#!/usr/bin/env python3
"""Convenience wrapper to bring up the orchestrator control plane.

Runs status_wave once, starts the read-only dashboard as a child
process, opens the browser (with --no-open opt-out), and blocks until
Ctrl-C. On signal, sends SIGTERM to the dashboard child with a 5s
grace before SIGKILL.

Exit codes:
- 0 clean shutdown
- 2 guardrail (runtime root missing)
- 3 dashboard failed to come up
"""

from __future__ import annotations

import argparse
import json
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

REPO_ROOT = _paths.REPO_ROOT
DASHBOARD = REPO_ROOT / ".agents" / "dashboard" / "server.py"
STATUS_WAVE = Path(__file__).resolve().parent / "status_wave.py"

EXIT_OK = 0
EXIT_GUARDRAIL = 2
EXIT_DASHBOARD_FAILED = 3

DEFAULT_PORT = 8787
STARTUP_TIMEOUT_SECONDS = 10
SHUTDOWN_GRACE_SECONDS = 5


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the orchestrator control plane (status_wave + dashboard + browser).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser automatically.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Dashboard port. Default {DEFAULT_PORT}.",
    )
    parser.add_argument(
        "--mission",
        type=Path,
        default=None,
        help="Mission spec dir override for the status_wave call (defaults to auto-detect).",
    )
    return parser.parse_args(argv)


def _python_bin() -> str:
    """Prefer the project's venv python if available; else current interpreter."""
    venv = REPO_ROOT / ".venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
    return sys.executable


def _run_status_wave(mission: Path | None) -> None:
    py = _python_bin()
    cmd = [py, str(STATUS_WAVE)]
    if mission is not None:
        cmd.extend(["--mission", str(mission)])
    print(f"--- status_wave ({' '.join(cmd)}) ---")
    # Inherits stdout/stderr so the operator sees the output.
    subprocess.run(cmd, check=False)  # noqa: S603
    print("--- end status_wave ---")


def _start_dashboard(port: int) -> subprocess.Popen[bytes]:
    py = _python_bin()
    cmd = [py, str(DASHBOARD), "--port", str(port)]
    return subprocess.Popen(  # noqa: S603
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )


def _wait_until_ready(port: int, timeout: float) -> bool:
    url = f"http://127.0.0.1:{port}/api/snapshot"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:  # noqa: S310
                if resp.status == 200:
                    # Drain a tiny bit so the snapshot is fully read.
                    resp.read(64)
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        except json.JSONDecodeError:
            pass
        time.sleep(0.2)
    return False


def _shutdown(child: subprocess.Popen[bytes]) -> None:
    if child.poll() is not None:
        return
    try:
        child.terminate()
    except ProcessLookupError:
        return
    try:
        child.wait(timeout=SHUTDOWN_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        child.kill()
    except ProcessLookupError:
        return
    try:
        child.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        pass


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runtime_root = _paths.runtime_root()
    if not runtime_root.exists():
        runtime_root.mkdir(parents=True, exist_ok=True)
    if not DASHBOARD.is_file():
        print(f"Dashboard not found at {DASHBOARD}", file=sys.stderr)
        return EXIT_GUARDRAIL

    _run_status_wave(args.mission)

    child = _start_dashboard(args.port)
    try:
        ready = _wait_until_ready(args.port, STARTUP_TIMEOUT_SECONDS)
        if not ready:
            print("Dashboard failed to come up within timeout.", file=sys.stderr)
            _shutdown(child)
            return EXIT_DASHBOARD_FAILED

        url = f"http://127.0.0.1:{args.port}"
        print(f"Agent dashboard: {url}")
        print(f"Runtime root:    {runtime_root}")
        print("Press Ctrl-C to shut down.")
        if not args.no_open and shutil.which is not None:
            try:
                webbrowser.open(url)
            except webbrowser.Error:
                pass

        # Block until the child exits or we get a signal.
        def _on_signal(signum, _frame):  # noqa: ARG001
            raise KeyboardInterrupt()

        signal.signal(signal.SIGTERM, _on_signal)
        try:
            child.wait()
        except KeyboardInterrupt:
            print("\n--- shutting down ---")
            _shutdown(child)
            return EXIT_OK
        return EXIT_OK
    finally:
        _shutdown(child)


if __name__ == "__main__":
    sys.exit(main())
