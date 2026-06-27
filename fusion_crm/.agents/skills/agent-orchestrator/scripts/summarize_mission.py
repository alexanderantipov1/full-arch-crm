#!/usr/bin/env python3
"""Create a compact handoff file for resuming an orchestration mission."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def read_text(path: Path, *, max_chars: int | None = None) -> str:
    if not path.exists():
        return "_Missing._\n"
    text = path.read_text(encoding="utf-8", errors="replace")
    if max_chars is not None and len(text) > max_chars:
        omitted = len(text) - max_chars
        text = text[:max_chars] + f"\n\n_Trimmed {omitted} chars._\n"
    return text.rstrip() + "\n"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def tmux_alive(session_name: str) -> bool:
    tmux = shutil.which("tmux")
    if tmux is None:
        return False
    proc = subprocess.run(  # noqa: S603 - session name comes from orchestrator runtime.
        [tmux, "has-session", "-t", session_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0


def runtime_summary(runtime: dict[str, Any]) -> str:
    runs = runtime.get("runs", [])
    if not runs:
        return "_No runtime entries._\n"

    lines = [
        "| Wave | Task | Agent | Mode | Status | Worktree | Report | Log |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for run in runs:
        wave_id = run.get("wave_id", "-")
        for task in run.get("tasks", []):
            status = "unknown"
            if task.get("dry_run"):
                status = "dry-run"
            elif "pid" in task:
                status = "running" if pid_alive(int(task["pid"])) else "not-running"
            elif "tmux_session" in task:
                status = (
                    "running"
                    if tmux_alive(str(task["tmux_session"]))
                    else "not-running"
                )
            report = "yes" if Path(task.get("report_path", "")).exists() else "no"
            log = "yes" if Path(task.get("log_path", "")).exists() else "no"
            lines.append(
                "| {wave} | {task_id} | {agent} | {mode} | {status} | `{worktree}` | {report} | {log} |".format(
                    wave=wave_id,
                    task_id=task.get("task_id", "-"),
                    agent=task.get("agent", "-"),
                    mode=task.get("mode", "-"),
                    status=status,
                    worktree=task.get("worktree", "-"),
                    report=report,
                    log=log,
                )
            )
    return "\n".join(lines) + "\n"


def reports_summary(reports_dir: Path, *, max_chars_per_report: int) -> str:
    reports = sorted(
        path
        for path in reports_dir.glob("*.md")
        if path.name.upper() != "TEMPLATE.MD"
    )
    if not reports:
        return "_No reports found._\n"

    chunks: list[str] = []
    for report in reports:
        chunks.append(f"### {report.name}\n")
        chunks.append(read_text(report, max_chars=max_chars_per_report))
    return "\n".join(chunks).rstrip() + "\n"


def git_status() -> str:
    git = shutil.which("git")
    if git is None:
        return "_git not found on PATH._\n"
    proc = subprocess.run(  # noqa: S603 - fixed read-only git status command.
        [git, "status", "--short"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = proc.stdout.strip()
    return output + "\n" if output else "_Clean._\n"


def build_handoff(mission_folder: Path, max_chars_per_report: int) -> str:
    runtime = load_json(mission_folder / "runtime.json")
    return "\n".join(
        [
            "# Agent Orchestration Handoff",
            "",
            f"Generated: {now_iso()}",
            f"Mission folder: `{mission_folder}`",
            "",
            "## Resume Prompt",
            "",
            "```text",
            "Use the orchestrator protocol in .agents/orchestrator/PROTOCOL.md.",
            "",
            f"Resume mission from {mission_folder}.",
            "Read handoff.md first, then inspect backlog.md, daily-sprint.md, goal.md, acceptance.md, verification.md, linear-sync.md, contract.md, ownership.md, ownership.yaml, board.md, integration-plan.md, decision-log.md, runlog.md, incidents.md, lessons.md, runtime.json, and any reports needed for the next decision. Evaluate goal.md and acceptance.md, summarize current state, identify blockers, sync Linear if needed, apply accepted lessons, and prepare the next wave or integration plan. Do not implement feature work unless explicitly asked.",
            "```",
            "",
            "## Git Status",
            "",
            "```text",
            git_status().rstrip(),
            "```",
            "",
            "## Mission",
            "",
            read_text(mission_folder / "mission.md").rstrip(),
            "",
            "## Backlog",
            "",
            read_text(mission_folder / "backlog.md").rstrip(),
            "",
            "## Daily Sprint",
            "",
            read_text(mission_folder / "daily-sprint.md").rstrip(),
            "",
            "## Goal",
            "",
            read_text(mission_folder / "goal.md").rstrip(),
            "",
            "## Acceptance",
            "",
            read_text(mission_folder / "acceptance.md").rstrip(),
            "",
            "## Verification",
            "",
            read_text(mission_folder / "verification.md").rstrip(),
            "",
            "## Linear Sync",
            "",
            read_text(mission_folder / "linear-sync.md").rstrip(),
            "",
            "## Shared Contract",
            "",
            read_text(mission_folder / "contract.md").rstrip(),
            "",
            "## Ownership",
            "",
            read_text(mission_folder / "ownership.md").rstrip(),
            "",
            "## Ownership YAML",
            "",
            "```yaml",
            read_text(mission_folder / "ownership.yaml").rstrip(),
            "```",
            "",
            "## Board",
            "",
            read_text(mission_folder / "board.md").rstrip(),
            "",
            "## Integration Plan",
            "",
            read_text(mission_folder / "integration-plan.md").rstrip(),
            "",
            "## Decision Log",
            "",
            read_text(mission_folder / "decision-log.md", max_chars=12000).rstrip(),
            "",
            "## Run Log",
            "",
            read_text(mission_folder / "runlog.md", max_chars=12000).rstrip(),
            "",
            "## Incidents",
            "",
            read_text(mission_folder / "incidents.md", max_chars=12000).rstrip(),
            "",
            "## Lessons",
            "",
            read_text(mission_folder / "lessons.md", max_chars=12000).rstrip(),
            "",
            "## Runtime",
            "",
            runtime_summary(runtime).rstrip(),
            "",
            "## Reports",
            "",
            reports_summary(
                mission_folder / "reports",
                max_chars_per_report=max_chars_per_report,
            ).rstrip(),
            "",
            "## Next Orchestrator Checklist",
            "",
            "- Confirm which workers are still running.",
            "- Read any reports marked blocked or partial.",
            "- Check file ownership before launching more workers.",
            "- Review incidents and apply accepted lessons before planning the next wave.",
            "- Escalate only consolidated user approvals.",
            "- Update this handoff after the next wave or integration step.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate handoff.md for resuming an agent orchestration mission."
    )
    parser.add_argument("--mission-folder", required=True)
    parser.add_argument(
        "--output",
        default="handoff.md",
        help="Output filename relative to mission folder, or an absolute path",
    )
    parser.add_argument(
        "--max-chars-per-report",
        type=int,
        default=6000,
        help="Trim each report to this many characters",
    )
    args = parser.parse_args()

    mission_folder = Path(args.mission_folder).resolve()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = mission_folder / output_path

    output_path.write_text(
        build_handoff(
            mission_folder,
            max_chars_per_report=args.max_chars_per_report,
        ),
        encoding="utf-8",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
