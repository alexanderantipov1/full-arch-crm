#!/usr/bin/env python3
"""Launch a wave of dashboard-visible workers from a JSON task file."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
LAUNCHER = SCRIPT_DIR / "launch_worker.py"


def read_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        tasks = payload.get("tasks", [])
    else:
        tasks = payload
    if not isinstance(tasks, list):
        raise SystemExit("Task file must be a JSON list or an object with a tasks list.")
    normalized = []
    for item in tasks:
        if not isinstance(item, dict):
            raise SystemExit("Each task must be an object.")
        normalized.append(item)
    return normalized


def build_args(base: argparse.Namespace, task: dict[str, Any]) -> list[str]:
    runtime = task.get("runtime", base.runtime)
    role = task.get("role", base.role)
    mode = task.get("mode", base.mode)
    args = [
        sys.executable,
        str(LAUNCHER),
        "--mission",
        str(base.mission),
        "--runtime",
        str(runtime),
        "--role",
        str(role),
        "--mode",
        str(mode),
        "--task-id",
        required(task, "task_id"),
        "--linear-id",
        required(task, "linear_id"),
        "--linear-url",
        required(task, "linear_url"),
        "--linear-title",
        required(task, "linear_title"),
        "--linear-status",
        str(task.get("linear_status", "In Progress")),
        "--worktree",
        str(task.get("worktree", base.worktree)),
        "--branch",
        str(task.get("branch", base.branch)),
        "--phase",
        str(task.get("phase", "assigned")),
        "--reason",
        str(task.get("reason", "Worker assignment accepted by Orchestrator.")),
        "--risk",
        str(task.get("risk", "medium")),
        "--note",
        str(task.get("note", "Worker launched by Orchestrator.")),
    ]
    worker_name = task.get("worker_name")
    if worker_name:
        args.extend(["--worker-name", str(worker_name)])
    if task.get("prompt_file"):
        args.extend(["--prompt-file", str(task["prompt_file"])])
    else:
        args.extend(["--prompt", str(task.get("prompt", ""))])
    if task.get("tmux_name"):
        args.extend(["--tmux-name", str(task["tmux_name"])])
    if "codex_sandbox" in task:
        args.extend(["--codex-sandbox", str(task["codex_sandbox"])])
    if task.get("codex_bypass_approvals"):
        args.append("--codex-bypass-approvals")
    if task.get("codex_full_auto"):
        args.append("--codex-full-auto")
    if "claude_permission_mode" in task:
        args.extend(["--claude-permission-mode", str(task["claude_permission_mode"])])
    # M-2 / ENG-225 — workspace + self-execute guardrail pass-through.
    if "workspace" in task:
        args.extend(["--workspace", str(task["workspace"])])
    if task.get("allow_self_execute"):
        args.append("--allow-self-execute")
    if "scope" in task:
        args.extend(["--scope", str(task["scope"])])
    if "branch_base" in task:
        args.extend(["--branch-base", str(task["branch_base"])])
    return args


def required(task: dict[str, Any], key: str) -> str:
    value = str(task.get(key) or "").strip()
    if not value:
        raise SystemExit(f"Task is missing required field: {key}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch a batch of Codex/Claude Code workers.")
    parser.add_argument("--tasks", type=Path, required=True, help="JSON list or {tasks: [...]} file.")
    parser.add_argument("--mission", type=Path, default=Path(".agents/orchestration/current"))
    parser.add_argument("--runtime", choices=["codex", "claude-code"], default="codex")
    parser.add_argument("--role", choices=["worker", "verifier", "integrator", "reviewer"], default="worker")
    parser.add_argument("--mode", choices=["print", "background", "tmux"], default="print")
    parser.add_argument("--worktree", default=".")
    parser.add_argument("--branch", default="current")
    args = parser.parse_args()

    for task in read_tasks(args.tasks):
        command = build_args(args, task)
        print(f"Launching {task.get('task_id')} as {task.get('runtime', args.runtime)} in {task.get('mode', args.mode)} mode")
        # Intentional local wrapper around launch_worker.py for trusted task files.
        subprocess.run(command, check=True)  # noqa: S603


if __name__ == "__main__":
    main()
