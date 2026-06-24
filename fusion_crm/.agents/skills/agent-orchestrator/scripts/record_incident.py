#!/usr/bin/env python3
"""Append an incident entry to a mission incidents.md file."""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path


def next_incident_id(existing: str, today: str) -> str:
    pattern = re.compile(rf"INC-{today}-(\d{{3}})")
    numbers = [int(match.group(1)) for match in pattern.finditer(existing)]
    return f"INC-{today}-{(max(numbers) + 1 if numbers else 1):03d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Record an orchestrator incident.")
    parser.add_argument("--mission-folder", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--severity",
        choices=("low", "medium", "high", "blocker"),
        default="medium",
    )
    parser.add_argument(
        "--area",
        choices=(
            "planning",
            "launch",
            "worker",
            "Linear",
            "contract",
            "ownership",
            "integration",
            "verification",
            "release",
        ),
        default="planning",
    )
    parser.add_argument("--detected-by", default="orchestrator")
    parser.add_argument("--what-happened", default="TBD")
    parser.add_argument("--impact", default="TBD")
    parser.add_argument("--root-cause", default="TBD")
    parser.add_argument("--immediate-fix", default="TBD")
    parser.add_argument("--lesson-candidate", default="TBD")
    parser.add_argument("--follow-up", default="TBD")
    args = parser.parse_args()

    mission_folder = Path(args.mission_folder).resolve()
    incidents_path = mission_folder / "incidents.md"
    existing = incidents_path.read_text(encoding="utf-8") if incidents_path.exists() else "# Incident Log\n"
    today = datetime.now(UTC).strftime("%Y%m%d")
    incident_id = next_incident_id(existing, today)
    now = datetime.now(UTC).isoformat()

    entry = f"""

## {incident_id}: {args.title}

Date: {now}
Detected by: {args.detected_by}
Severity: {args.severity}
Area: {args.area}

### What happened

{args.what_happened}

### Impact

{args.impact}

### Root cause

{args.root_cause}

### Immediate fix

{args.immediate_fix}

### Durable lesson candidate

{args.lesson_candidate}

### Follow-up action

{args.follow_up}
"""
    incidents_path.write_text(existing.rstrip() + entry + "\n", encoding="utf-8")
    print(f"{incident_id} {incidents_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
