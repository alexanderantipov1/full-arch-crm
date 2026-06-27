#!/usr/bin/env python3
"""Print git worktree commands for agent branch orchestration."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "mission"


def parse_task(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("task must be formatted as ID=label")
    task_id, label = value.split("=", 1)
    task_id = task_id.strip()
    label = slugify(label)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", task_id):
        raise argparse.ArgumentTypeError(f"invalid task id: {task_id}")
    return task_id.upper(), label


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print worktree setup commands for parallel terminal agents."
    )
    parser.add_argument("--mission", required=True, help="Mission title")
    parser.add_argument(
        "--repo-name",
        default=Path.cwd().name,
        help="Repository folder name used for sibling worktree paths",
    )
    parser.add_argument(
        "--base",
        default="main",
        help="Base branch for all worktrees",
    )
    parser.add_argument(
        "--task",
        action="append",
        type=parse_task,
        required=True,
        help="Task mapping formatted as ID=label, for example A1=credential-api",
    )
    args = parser.parse_args()

    mission = slugify(args.mission)
    print("# Review before running. These commands are not executed by this script.")
    print("git fetch --all --prune")
    print(f"git worktree add ../{args.repo_name}-integration -b integration/{mission} {args.base}")

    for task_id, label in args.task:
        branch = f"agent/{mission}-{task_id.lower()}-{label}"
        path = f"../{args.repo_name}-{task_id}"
        print(f"git worktree add {path} -b {branch} {args.base}")

    print()
    print("# Suggested launch prompts:")
    for task_id, _label in args.task:
        print(
            f"# {task_id}: Follow the task brief at <mission-folder>/tasks/{task_id}.md "
            f"in ../{args.repo_name}-{task_id}; write report to <mission-folder>/reports/{task_id}.md"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
