#!/usr/bin/env python3
"""Worker control plane CLI: --list / --status / --kill / --attach.

Reads the active mission's `runtime.json` via `paths.py` and exposes
the per-session control surface that supersedes hand-rolled
`ps aux` + `tail -f` workflows.

Exit codes:
- 0 success
- 2 guardrail / argparse violation
- 3 unknown session id
- 4 git / signal operation failed
- 5 user interrupted (Ctrl-C in --attach)
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import activity_heuristic as _activity  # noqa: E402
import paths as _paths  # noqa: E402
import pid_check as _pid_check  # noqa: E402

EXIT_OK = 0
EXIT_GUARDRAIL = 2
EXIT_UNKNOWN_SESSION = 3
EXIT_OP_FAILED = 4
EXIT_INTERRUPTED = 5

DEFAULT_GRACE_SECONDS = 10
DEFAULT_TAIL_LINES = 20
DEFAULT_IDLE_THRESHOLD = 60


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip() + "\n")


def tail_lines(path: Path, n: int) -> list[str]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return text.splitlines()[-n:]


def auto_detect_mission(repo_root: Path) -> Path | None:
    """Pick the newest non-archived mission folder. Mirrors the ENG-223 mtime fallback."""
    orchestration = repo_root / ".agents" / "orchestration"
    if not orchestration.is_dir():
        return None
    candidates = []
    for child in orchestration.iterdir():
        if child.is_dir() and child.name != "archived" and not child.name.startswith("."):
            try:
                candidates.append((child.stat().st_mtime, child))
            except OSError:
                continue
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


def load_sessions(mission_spec_dir: Path) -> tuple[Path, dict[str, Any]]:
    """Return (runtime.json path, parsed payload) for a mission."""
    mission_id = mission_spec_dir.name
    runtime_dir = _paths.mission_runtime_dir(mission_id)
    runtime_path = runtime_dir / "runtime.json"
    return runtime_path, read_json(runtime_path)


def find_session(sessions: list[dict[str, Any]], session_id: str) -> dict[str, Any] | None:
    for item in sessions:
        if isinstance(item, dict) and item.get("id") == session_id:
            return item
    return None


def enrich(session: dict[str, Any], idle_threshold: int) -> dict[str, Any]:
    """Compute derived runtime_status + agent_activity for a session.

    Does NOT mutate the input dict. Returns a shallow copy with the
    two derived fields added.
    """
    enriched = dict(session)
    enriched["runtime_status"] = _pid_check.runtime_status(session.get("pid"))
    log_path = session.get("log_path")
    if log_path:
        enriched["agent_activity"] = _activity.activity_state(
            Path(log_path), idle_threshold_seconds=idle_threshold
        )
    else:
        enriched["agent_activity"] = "idle"
    return enriched


def cmd_list(runtime: dict[str, Any], idle_threshold: int) -> int:
    sessions = [s for s in runtime.get("sessions", []) if isinstance(s, dict)]
    if not sessions:
        print("No active sessions.")
        return EXIT_OK
    print(
        f"{'session_id':14s} {'task_id':10s} {'role/agent':22s} "
        f"{'status':18s} {'runtime':8s} {'activity':14s} {'pid':>7s} {'last_activity':24s}"
    )
    for raw in sessions:
        e = enrich(raw, idle_threshold)
        print(
            f"{str(e.get('id', ''))[:14]:14s} "
            f"{str(e.get('task_id', ''))[:10]:10s} "
            f"{(str(e.get('role', '?')) + '/' + str(e.get('agent', '?')))[:22]:22s} "
            f"{str(e.get('status', ''))[:18]:18s} "
            f"{str(e.get('runtime_status', '')):8s} "
            f"{str(e.get('agent_activity', '')):14s} "
            f"{str(e.get('pid', '')):>7s} "
            f"{str(e.get('last_activity', ''))[:24]:24s}"
        )
    return EXIT_OK


def cmd_status(runtime: dict[str, Any], session_id: str, tail_lines_n: int, idle_threshold: int) -> int:
    sessions = [s for s in runtime.get("sessions", []) if isinstance(s, dict)]
    session = find_session(sessions, session_id)
    if session is None:
        print(f"Unknown session id: {session_id}", file=sys.stderr)
        return EXIT_UNKNOWN_SESSION
    e = enrich(session, idle_threshold)
    print(f"Session:           {e.get('id')}")
    print(f"Task:              {e.get('task_id')}")
    print(f"Role / agent:      {e.get('role')} / {e.get('agent')}")
    print(f"Linear:            {e.get('linear_issue_id')}  ({e.get('linear_status')})")
    print(f"Execution status:  {e.get('status')}")
    print(f"Runtime status:    {e.get('runtime_status')}")
    print(f"Agent activity:    {e.get('agent_activity')}  [heuristic]")
    print(f"PID:               {e.get('pid')}")
    print(f"Worktree:          {e.get('worktree')}")
    print(f"Branch:            {e.get('branch')}")
    print(f"Last activity:     {e.get('last_activity')}")
    print(f"Phase:             {e.get('phase')}")
    print(f"Note:              {e.get('current_note')}")
    log_path = e.get("log_path")
    if log_path:
        print()
        print(f"--- last {tail_lines_n} log lines ({log_path}) ---")
        for line in tail_lines(Path(log_path), tail_lines_n):
            print(line)
    return EXIT_OK


def cmd_kill(
    runtime: dict[str, Any],
    runtime_path: Path,
    session_id: str,
    grace_seconds: int,
    idle_threshold: int,
    runlog_path: Path,
) -> int:
    sessions = [s for s in runtime.get("sessions", []) if isinstance(s, dict)]
    session = find_session(sessions, session_id)
    if session is None:
        print(f"Unknown session id: {session_id}", file=sys.stderr)
        return EXIT_UNKNOWN_SESSION
    pid = session.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        print(f"Session {session_id} has no live pid (pid={pid}). Marking cancelled in runtime.json.")
        _mark_cancelled(runtime, runtime_path, session_id)
        _append_runlog_kill(runlog_path, session_id, "no-live-pid")
        return EXIT_OK
    # SIGTERM, wait grace, SIGKILL.
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print(f"PID {pid} already exited.")
        _mark_cancelled(runtime, runtime_path, session_id)
        _append_runlog_kill(runlog_path, session_id, "already-exited")
        return EXIT_OK
    except (PermissionError, OSError) as exc:
        print(f"SIGTERM failed: {exc}", file=sys.stderr)
        return EXIT_OP_FAILED
    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        if _pid_check.runtime_status(pid) != "alive":
            print(f"PID {pid} exited cleanly within {grace_seconds}s grace.")
            _mark_cancelled(runtime, runtime_path, session_id)
            _append_runlog_kill(runlog_path, session_id, "sigterm-clean")
            return EXIT_OK
        time.sleep(0.1)
    # Still alive — SIGKILL.
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except (PermissionError, OSError) as exc:
        print(f"SIGKILL failed: {exc}", file=sys.stderr)
        return EXIT_OP_FAILED
    print(f"PID {pid} did not exit within {grace_seconds}s; sent SIGKILL.")
    _mark_cancelled(runtime, runtime_path, session_id)
    _append_runlog_kill(runlog_path, session_id, "sigkill")
    return EXIT_OK


def _mark_cancelled(runtime: dict[str, Any], runtime_path: Path, session_id: str) -> None:
    sessions = runtime.get("sessions", [])
    for item in sessions:
        if isinstance(item, dict) and item.get("id") == session_id:
            item["status"] = "cancelled"
            item["last_activity"] = utc_now()
            item["needs_human"] = False
            break
    runtime["updated_at"] = utc_now()
    write_json(runtime_path, runtime)


def _append_runlog_kill(runlog_path: Path, session_id: str, reason: str) -> None:
    line = f"- {utc_now()} | worker_ctl | {session_id} | cancelled | --kill issued ({reason})."
    append_line(runlog_path, line)


def cmd_attach(runtime: dict[str, Any], session_id: str) -> int:
    sessions = [s for s in runtime.get("sessions", []) if isinstance(s, dict)]
    session = find_session(sessions, session_id)
    if session is None:
        print(f"Unknown session id: {session_id}", file=sys.stderr)
        return EXIT_UNKNOWN_SESSION
    log_path = session.get("log_path")
    if not log_path:
        print(f"Session {session_id} has no log_path on record.", file=sys.stderr)
        return EXIT_OP_FAILED
    path = Path(log_path)
    if not path.is_file():
        print(f"Log file does not exist: {path}", file=sys.stderr)
        return EXIT_OP_FAILED
    print(f"--- tailing {path} (Ctrl-C to detach) ---")
    try:
        _follow(path)
    except KeyboardInterrupt:
        print("\n--- detached ---")
        return EXIT_INTERRUPTED
    return EXIT_OK


def _follow(path: Path) -> None:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        # Print everything that exists, then tail.
        for line in handle:
            print(line.rstrip())
        while True:
            position = handle.tell()
            line = handle.readline()
            if line:
                print(line.rstrip())
            else:
                time.sleep(0.5)
                handle.seek(position)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Worker control plane: list/status/kill/attach a mission's sessions.",
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="List all sessions for the current mission.")
    action.add_argument("--status", metavar="SID", help="Print compact status block for a session id.")
    action.add_argument("--kill", metavar="SID", help="Terminate a session (SIGTERM then SIGKILL after --grace).")
    action.add_argument("--attach", metavar="SID", help="Tail the worker log to stdout. Read-only.")
    parser.add_argument(
        "--mission", type=Path, default=None,
        help="Mission spec dir override. Defaults to newest non-archived mission folder.",
    )
    parser.add_argument(
        "--grace", type=int, default=DEFAULT_GRACE_SECONDS,
        help=f"Seconds to wait after SIGTERM before SIGKILL. Default {DEFAULT_GRACE_SECONDS}.",
    )
    parser.add_argument(
        "--tail-lines", type=int, default=DEFAULT_TAIL_LINES,
        help=f"Log tail length for --status. Default {DEFAULT_TAIL_LINES}.",
    )
    parser.add_argument(
        "--idle-threshold", type=int, default=DEFAULT_IDLE_THRESHOLD,
        help=f"Seconds of no log growth to call a session 'idle'. Default {DEFAULT_IDLE_THRESHOLD}.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spec_dir = args.mission.resolve() if args.mission else auto_detect_mission(_paths.REPO_ROOT)
    if spec_dir is None:
        print("No active mission found under .agents/orchestration/ (excluding archived/).", file=sys.stderr)
        return EXIT_GUARDRAIL
    runtime_path, runtime = load_sessions(spec_dir)
    runlog_path = runtime_path.parent / "runlog.md"

    if args.list:
        return cmd_list(runtime, args.idle_threshold)
    if args.status:
        return cmd_status(runtime, args.status, args.tail_lines, args.idle_threshold)
    if args.kill:
        return cmd_kill(runtime, runtime_path, args.kill, args.grace, args.idle_threshold, runlog_path)
    if args.attach:
        return cmd_attach(runtime, args.attach)
    return EXIT_GUARDRAIL  # pragma: no cover — argparse enforces required mutex


if __name__ == "__main__":
    sys.exit(main())
