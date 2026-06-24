#!/usr/bin/env python3
"""Fix-lane — a persistent scratch worktree for interactive small fixes.

The orchestrated Workers get isolated worktrees from `launch_worker.py`. This
helper covers the *other* daily reality: hand-opened debugging where you fix a
little here, a little there. Doing that in the canonical checkout (on shared
`main`/HEAD while autonomous work is in flight) is exactly what causes dirty-tree
collisions. The fix-lane gives interactive fixes their own isolated home so they
never touch the integration checkout.

One lane per day by default: branch `fix/<YYYY-MM-DD>` off fresh `origin/main`,
in a worktree beside the canonical checkout. Batch small logical commits there,
then fast-path merge under one umbrella Linear issue (see PARALLEL_WORK_POLICY
"The interactive fix-lane").

Concurrency: pass an area LABEL to get a per-area lane so several debug sessions
(Codex + multiple Claude terminals) run in parallel without colliding — one lane
per session, partitioned by non-overlapping area, exactly like big tasks.

Usage:
    fix_lane.py                 # ensure the day lane; print its path + status
    fix_lane.py seo             # per-area lane ../fusion-fix-seo on fix/seo-<date>
    fix_lane.py --status        # just show status, do not create
    fix_lane.py --sync          # fast-forward the lane onto latest origin/main
    fix_lane.py seo --sync      # ...the seo lane
    fix_lane.py --branch fix/x  # use an explicit branch name

This script only manages a worktree + branch. It never pushes, deletes remote
refs, deploys, or edits code.
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

REPO_ROOT = _paths.REPO_ROOT
DEFAULT_LANE_DIR = REPO_ROOT.parent / "fusion-fix-lane"

EXIT_OK = 0
EXIT_GIT_FAILED = 3
EXIT_GUARDRAIL = 2


def _git(args: list[str], cwd: Path | None = None, check: bool = False):
    git_bin = shutil.which("git")
    if git_bin is None:
        print("error: git not found on PATH", file=sys.stderr)
        sys.exit(EXIT_GIT_FAILED)
    # git_bin is resolved via shutil.which; args are fixed git subcommands.
    return subprocess.run(  # noqa: S603
        [git_bin, *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        check=check,
    )


def slugify(label: str) -> str:
    """Lowercase, keep [a-z0-9-], collapse the rest to '-'. Empty -> ''."""
    out = "".join(c if c.isalnum() else "-" for c in label.lower())
    return "-".join(p for p in out.split("-") if p)


def default_branch(label: str | None = None) -> str:
    today = datetime.date.today().isoformat()
    slug = slugify(label) if label else ""
    return f"fix/{slug}-{today}" if slug else f"fix/{today}"


def lane_dir_for(label: str | None) -> Path:
    slug = slugify(label) if label else ""
    return REPO_ROOT.parent / (f"fusion-fix-{slug}" if slug else "fusion-fix-lane")


def branch_exists(branch: str) -> bool:
    return (
        _git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"]).returncode
        == 0
    )


def worktree_paths() -> dict[str, str]:
    """Map worktree path -> branch from `git worktree list --porcelain`."""
    res = _git(["worktree", "list", "--porcelain"])
    out: dict[str, str] = {}
    cur = ""
    for line in res.stdout.splitlines():
        if line.startswith("worktree "):
            cur = line[len("worktree ") :].strip()
        elif line.startswith("branch "):
            ref = line[len("branch ") :].strip()
            out[cur] = ref.rsplit("/", 1)[-1] if ref.startswith("refs/heads/") else ref
    return out


def lane_status(lane_dir: Path, branch: str) -> None:
    if not lane_dir.exists():
        print(f"fix-lane: not created yet ({lane_dir})")
        return
    ab = _git(
        ["rev-list", "--left-right", "--count", "origin/main...HEAD"], cwd=lane_dir
    ).stdout.split()
    behind, ahead = (ab + ["0", "0"])[:2]
    dirty = len(
        [ln for ln in _git(["status", "--porcelain"], cwd=lane_dir).stdout.splitlines() if ln]
    )
    print(f"fix-lane: {lane_dir}")
    print(f"  branch: {branch}")
    print(f"  vs origin/main: {ahead} ahead / {behind} behind")
    print(f"  uncommitted: {dirty} path(s)")
    print(f"  cd {lane_dir}")


def ensure_lane(lane_dir: Path, branch: str) -> int:
    _git(["fetch", "origin", "main", "--quiet"])

    existing = worktree_paths()
    if str(lane_dir) in {str(Path(p).resolve()) for p in existing}:
        print(f"fix-lane already exists -> {lane_dir}")
        lane_status(lane_dir, branch)
        return EXIT_OK

    if lane_dir.exists():
        print(
            f"error: {lane_dir} exists but is not a registered worktree; "
            "remove it or pass --branch with a fresh path.",
            file=sys.stderr,
        )
        return EXIT_GUARDRAIL

    if branch_exists(branch):
        res = _git(["worktree", "add", str(lane_dir), branch])
    else:
        res = _git(["worktree", "add", str(lane_dir), "-b", branch, "origin/main"])
    if res.returncode != 0:
        print(f"error creating worktree: {res.stderr.strip()}", file=sys.stderr)
        return EXIT_GIT_FAILED

    print(f"fix-lane ready -> {lane_dir} (branch {branch}, off origin/main)")
    lane_status(lane_dir, branch)
    return EXIT_OK


def sync_lane(lane_dir: Path, branch: str) -> int:
    if not lane_dir.exists():
        print("fix-lane does not exist yet; run without --sync to create it.")
        return EXIT_GUARDRAIL
    _git(["fetch", "origin", "main", "--quiet"])
    res = _git(["merge", "--ff-only", "origin/main"], cwd=lane_dir)
    if res.returncode == 0:
        print(f"fix-lane fast-forwarded onto origin/main: {res.stdout.strip()}")
    else:
        print(
            "fix-lane could NOT fast-forward (it has its own commits). Rebase or "
            "merge manually:\n"
            f"  cd {lane_dir} && git rebase origin/main",
            file=sys.stderr,
        )
        return EXIT_GUARDRAIL
    lane_status(lane_dir, branch)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fix-lane scratch worktree for small fixes.")
    ap.add_argument(
        "label",
        nargs="?",
        default=None,
        help="optional area label for a per-area parallel lane (e.g. 'seo')",
    )
    ap.add_argument("--branch", default=None, help="explicit branch name (overrides label)")
    ap.add_argument("--dir", default=None, help="explicit worktree dir (overrides label)")
    ap.add_argument("--status", action="store_true", help="show status only")
    ap.add_argument("--sync", action="store_true", help="fast-forward lane onto origin/main")
    args = ap.parse_args(argv)

    branch = args.branch or default_branch(args.label)
    lane_dir = Path(args.dir).resolve() if args.dir else lane_dir_for(args.label)

    if args.status:
        lane_status(lane_dir, branch)
        return EXIT_OK
    if args.sync:
        return sync_lane(lane_dir, branch)
    return ensure_lane(lane_dir, branch)


if __name__ == "__main__":
    raise SystemExit(main())
