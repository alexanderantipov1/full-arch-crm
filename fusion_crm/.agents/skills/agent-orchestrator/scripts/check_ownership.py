#!/usr/bin/env python3
"""Check changed files against mission ownership.yaml."""

from __future__ import annotations

import argparse
import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by environment.
    yaml = None


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required for ownership checks")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def changed_files(base: str) -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is not available on PATH")
    proc = subprocess.run(  # noqa: S603 - fixed git command with user-provided revision.
        [git, "diff", "--name-only", f"{base}...HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout.strip())
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check git diff files against mission ownership rules."
    )
    parser.add_argument("--mission-folder", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--base", default="main")
    parser.add_argument(
        "--files",
        nargs="*",
        help="Optional explicit file list; defaults to git diff --name-only base...HEAD",
    )
    args = parser.parse_args()

    mission_folder = Path(args.mission_folder).resolve()
    rules = load_yaml(mission_folder / "ownership.yaml")
    task_rules = (rules.get("tasks") or {}).get(args.task)
    if not task_rules:
        print(f"missing ownership rules for task {args.task}", file=sys.stderr)
        return 2

    files = args.files if args.files is not None else changed_files(args.base)
    allowed = task_rules.get("allowed_paths") or []
    forbidden = (rules.get("global_forbidden_paths") or []) + (
        task_rules.get("forbidden_paths") or []
    )

    violations: list[str] = []
    for path in files:
        if matches_any(path, forbidden):
            violations.append(f"forbidden: {path}")
        elif allowed and not matches_any(path, allowed):
            violations.append(f"outside allowed scope: {path}")

    if violations:
        print("ownership check: FAIL")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("ownership check: PASS")
    for path in files:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
