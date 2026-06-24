#!/usr/bin/env python3
"""Prune stale orchestrator worktrees.

Walks `paths.runtime_root()` looking for `<mission>/worktrees/<task>/`
directories. A worktree is eligible for cleanup when:

  * The mission folder is under `.agents/orchestration/archived/` in the
    canonical repo (i.e. the mission shipped and was archived).
  * AND the worktree's branch is merged into `main`.

Defaults to `--dry-run`: prints prune candidates with reasons but does
not touch the filesystem. `--apply` requires per-item `y/N` confirmation
before invoking `git worktree remove <path>`. `--force` permits removal
of worktrees whose branch has unmerged commits, gated behind a second
confirmation per item.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

REPO_ROOT = _paths.REPO_ROOT
ARCHIVED_DIR = REPO_ROOT / ".agents" / "orchestration" / "archived"

EXIT_OK = 0
EXIT_GUARDRAIL = 2
EXIT_GIT_FAILED = 3
EXIT_DECLINED = 4


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    git_bin = shutil.which("git")
    if git_bin is None:
        raise SystemExit("git is not on PATH; cannot manage worktrees.")
    return subprocess.run(  # noqa: S603
        [git_bin, *args],
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )


def list_worktrees(runtime_root: Path) -> list[Path]:
    """Find every `<runtime_root>/<mission>/worktrees/<task>/` directory."""
    if not runtime_root.is_dir():
        return []
    found: list[Path] = []
    for mission_dir in runtime_root.iterdir():
        if not mission_dir.is_dir():
            continue
        worktrees_dir = mission_dir / "worktrees"
        if not worktrees_dir.is_dir():
            continue
        for child in worktrees_dir.iterdir():
            if child.is_dir():
                found.append(child)
    return found


def mission_archived(mission_id: str) -> bool:
    """True when an archived folder exists matching the mission id."""
    if not ARCHIVED_DIR.is_dir():
        return False
    for archived in ARCHIVED_DIR.iterdir():
        if archived.is_dir() and archived.name.endswith(mission_id):
            return True
    return False


def branch_of(worktree_path: Path) -> str | None:
    """Return the branch name checked out in this worktree, or None on failure."""
    result = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree_path)
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def branch_merged_into_main(branch: str) -> bool:
    """True when `branch` is reachable from `main` (commits already on main)."""
    if branch in {"HEAD", "main"}:
        return True
    result = _git(["merge-base", "--is-ancestor", branch, "main"], cwd=REPO_ROOT)
    return result.returncode == 0


def classify(worktree: Path) -> dict[str, object]:
    """Compute prune eligibility + reason for one worktree."""
    mission_id = worktree.parent.parent.name
    task_id = worktree.name
    branch = branch_of(worktree)
    archived = mission_archived(mission_id)
    merged = bool(branch and branch_merged_into_main(branch))
    eligible = archived and merged
    if eligible:
        reason = f"mission archived AND branch '{branch}' merged into main"
    elif not branch:
        reason = "could not read branch (worktree corrupted?)"
    elif not archived:
        reason = f"mission '{mission_id}' is not archived"
    elif not merged:
        reason = f"branch '{branch}' has unmerged commits"
    else:
        reason = "unknown"
    return {
        "path": worktree,
        "mission_id": mission_id,
        "task_id": task_id,
        "branch": branch,
        "archived": archived,
        "merged": merged,
        "eligible": eligible,
        "reason": reason,
    }


def confirm(prompt: str) -> bool:
    """Read y/N from stdin. Default N. EOF/closed stdin → N."""
    try:
        response = input(f"{prompt} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return response in {"y", "yes"}


def remove_worktree(path: Path) -> bool:
    """Run `git worktree remove <path>`. Returns True on success."""
    result = _git(["worktree", "remove", str(path)], cwd=REPO_ROOT)
    if result.returncode != 0:
        print(
            f"  ERROR removing {path}: rc={result.returncode} "
            f"stderr={result.stderr.strip()}",
            file=sys.stderr,
        )
        return False
    print(f"  removed: {path}")
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prune stale orchestrator worktrees under runtime_root().",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually remove worktrees (with per-item confirmation). Without "
             "this flag the script runs in dry-run mode and only lists candidates.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Permit removal of worktrees whose branch is NOT merged into main. "
             "Requires --apply and an additional confirmation per item.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-essential output.",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=None,
        help="Override the runtime root (defaults to paths.runtime_root()).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.force and not args.apply:
        print("--force requires --apply.", file=sys.stderr)
        return EXIT_GUARDRAIL

    runtime_root = args.runtime_root.resolve() if args.runtime_root else _paths.runtime_root()
    worktrees = list_worktrees(runtime_root)
    if not worktrees:
        if not args.quiet:
            print(f"No worktrees found under {runtime_root}.")
        return EXIT_OK

    classified = [classify(wt) for wt in worktrees]
    removed_any = False

    for entry in classified:
        path = entry["path"]
        eligible = entry["eligible"]
        reason = entry["reason"]
        header = f"{path} (mission={entry['mission_id']}, branch={entry['branch']})"
        if eligible:
            label = "ELIGIBLE"
        elif entry["archived"] and not entry["merged"] and args.force:
            label = "ELIGIBLE-WITH-FORCE"
        else:
            label = "SKIP"
        if not args.quiet or label != "SKIP":
            print(f"[{label}] {header}")
            print(f"  reason: {reason}")
        if not args.apply:
            continue
        if label == "SKIP":
            continue
        if label == "ELIGIBLE-WITH-FORCE":
            print(
                f"  WARNING: branch {entry['branch']} has unmerged commits. "
                "--force was passed; explicit confirmation required."
            )
            if not confirm("  Remove despite unmerged commits?"):
                print("  declined.")
                continue
        if not confirm("  Remove this worktree?"):
            print("  declined.")
            continue
        if remove_worktree(path):
            removed_any = True

    if args.apply and not removed_any:
        return EXIT_DECLINED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
