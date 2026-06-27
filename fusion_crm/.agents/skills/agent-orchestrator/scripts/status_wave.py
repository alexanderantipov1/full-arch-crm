#!/usr/bin/env python3
"""Print mission runtime status for the local dashboard."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Local imports — paths.py + M-3 helpers live next to this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import activity_heuristic as _activity  # noqa: E402
import paths as _paths  # noqa: E402
import pid_check as _pid_check  # noqa: E402

REPO_ROOT = _paths.REPO_ROOT
DEFAULT_MISSION = REPO_ROOT / ".agents" / "orchestration" / "current"


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def process_alive(pid: Any) -> str:
    if not isinstance(pid, int):
        return "unknown"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "stopped"
    except PermissionError:
        return "unknown"
    return "alive"


def main() -> None:
    parser = argparse.ArgumentParser(description="Show orchestrator mission runtime status.")
    parser.add_argument("--mission", type=Path, default=DEFAULT_MISSION)
    parser.add_argument("--stale-minutes", type=int, default=10)
    args = parser.parse_args()
    spec_dir = args.mission.resolve()
    mission_id = _paths.mission_id_from_spec_path(spec_dir)
    runtime_dir = _paths.mission_runtime_dir(mission_id)
    runtime = read_json(runtime_dir / "runtime.json")
    now = datetime.now(UTC)
    print(f"Mission spec:    {spec_dir}")
    print(f"Mission runtime: {runtime_dir}")
    print(f"Updated:         {runtime.get('updated_at', 'not recorded')}")
    print()
    print("Sessions:")
    sessions = runtime.get("sessions", [])
    if not sessions:
        print("- none")
    for item in sessions:
        if not isinstance(item, dict):
            continue
        last_activity = parse_time(str(item.get("last_activity") or ""))
        stale = "unknown"
        if last_activity:
            minutes = int((now - last_activity).total_seconds() // 60)
            stale = f"{minutes}m ago"
            if minutes >= args.stale_minutes:
                stale += " STALE"
        log_path = item.get("log_path")
        activity = (
            _activity.activity_state(Path(log_path)) if log_path else "idle"
        )
        runtime_status = _pid_check.runtime_status(item.get("pid"))
        print(
            "- {task} | {agent} | {status} | {linear} | pid={pid} {alive} | "
            "rt={runtime_status} | activity={activity} | {stale} | {note}".format(
                task=item.get("task_id", ""),
                agent=item.get("agent", ""),
                status=item.get("status", ""),
                linear=item.get("linear_issue_id", ""),
                pid=item.get("pid", ""),
                alive=process_alive(item.get("pid")),
                runtime_status=runtime_status,
                activity=activity,
                stale=stale,
                note=item.get("current_note", ""),
            )
        )
    print()
    print("Handoffs:")
    handoffs = runtime.get("handoffs", [])
    if not handoffs:
        print("- none")
    for item in handoffs[-20:]:
        if not isinstance(item, dict):
            continue
        print(
            "- {time} | {from_role}/{from_agent} -> {to_role}/{to_agent} | {task} | {linear} | {status} | {reason}".format(
                time=item.get("created_at", ""),
                from_role=item.get("from_role", ""),
                from_agent=item.get("from_agent", ""),
                to_role=item.get("to_role", ""),
                to_agent=item.get("to_agent", ""),
                task=item.get("task_id", ""),
                linear=item.get("linear_issue_id", ""),
                status=item.get("status", ""),
                reason=item.get("reason", ""),
            )
        )
    print()
    reports_dir = spec_dir / "reports"
    reports = sorted(reports_dir.glob("*-worker-report.md")) if reports_dir.is_dir() else []
    print(f"Reports: {len(reports)}")
    for path in reports[-20:]:
        try:
            print(f"- {path.relative_to(REPO_ROOT)}")
        except ValueError:
            print(f"- {path}")


if __name__ == "__main__":
    main()
