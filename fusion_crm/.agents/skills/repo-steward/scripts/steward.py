#!/usr/bin/env python3
"""Repo Steward — periodic git/mission hygiene with a hard reversibility split.

The Steward is the *acting* counterpart to the read-only Production Reviewer.
It is the Integrator's janitorial loop: it keeps merged branches, stale
worktrees, and the mission pointer tidy across missions, on a schedule.

REVERSIBILITY IS THE CONTRACT. Two classes of work, and the line between them
is enforced here in code, not just in prose:

  * AUTO (reversible, local-only) — applied with ``--apply``:
      - delete local branches already merged into ``origin/main``
        (never the current branch, never ``main``, never a branch checked
        out in a worktree); ``git branch -d`` refuses unmerged branches as a
        second backstop.
      - ``git worktree prune`` — drops administrative entries for worktree
        directories that are already gone. Never removes a live directory.

  * APPROVAL QUEUE (irreversible / outward-facing) — NEVER executed here,
    only written out as exact commands for the operator to run:
      - ``git push origin main`` (fast-forward only).
      - ``git push origin --delete <branch>`` for remote-merged branches.
      - ``git worktree remove <path>`` for live worktrees.
      - ``current`` pointer repoint suggestions, PR reconcile notes.

This script CANNOT push, delete remote refs, deploy, touch ``.env*``, or edit
product code. Its entire ``--apply`` blast radius is local and reversible. That
is what makes a scheduled, unattended run safe under the repo's
"never push/drop/destroy without explicit confirmation" rule.

Usage:
    steward.py                 # dry-run: report + write approval queue
    steward.py --apply         # also perform the reversible (local) set
    steward.py --json          # machine-readable summary on stdout
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "agent-orchestrator" / "scripts"),
)
import paths as _paths  # noqa: E402

REPO_ROOT = _paths.REPO_ROOT

EXIT_OK = 0
EXIT_GIT_FAILED = 3

PROTECTED_BRANCHES = {"main", "master"}


# --------------------------------------------------------------------------- #
# Pure helpers — no side effects, unit-tested without a real repo.
# --------------------------------------------------------------------------- #
def parse_ahead_behind(counts: str) -> tuple[int, int]:
    """Parse ``git rev-list --left-right --count A...B`` output.

    Returns ``(left, right)`` = ``(behind, ahead)`` when called as
    ``origin/main...HEAD``. Tolerant of empty/garbage input (returns 0, 0).
    """
    parts = counts.split()
    if len(parts) != 2:
        return (0, 0)
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return (0, 0)


def parse_branch_list(raw: str) -> list[tuple[bool, str]]:
    """Parse ``git branch`` porcelain-ish output.

    Returns ``(is_current, name)`` pairs. ``*`` marks the current branch and
    ``+`` marks a branch checked out in another worktree.
    """
    out: list[tuple[bool, str]] = []
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        is_current = line.startswith("*")
        name = line[1:].strip() if line[0] in "*+" else line.strip()
        if not name or name.startswith("("):  # detached HEAD entries
            continue
        out.append((is_current, name))
    return out


def deletable_merged_branches(
    merged_raw: str,
    worktree_branches: set[str],
) -> list[str]:
    """Local branches that are safe to delete locally.

    Input is ``git branch --merged origin/main`` output. Excludes the current
    branch (``*``), protected branches, and any branch checked out in a
    worktree (``+`` prefix, or present in ``worktree_branches``).
    """
    result: list[str] = []
    for is_current, name in parse_branch_list(merged_raw):
        if is_current:
            continue
        if name in PROTECTED_BRANCHES:
            continue
        if name in worktree_branches:
            continue
        result.append(name)
    return result


def build_queue(
    ahead: int,
    behind: int,
    remote_merged: list[str],
    live_worktrees_to_remove: list[str],
) -> list[dict[str, str]]:
    """Build the operator approval queue (exact, copy-pasteable commands)."""
    queue: list[dict[str, str]] = []
    if ahead > 0 and behind == 0:
        queue.append(
            {
                "kind": "push",
                "reason": f"local main is {ahead} commit(s) ahead of origin (fast-forward)",
                "command": "git push origin main",
            }
        )
    elif ahead > 0 and behind > 0:
        queue.append(
            {
                "kind": "push-diverged",
                "reason": f"main diverged: {ahead} ahead / {behind} behind — needs manual reconcile, NOT a plain push",
                "command": "git log --oneline --left-right origin/main...HEAD",
            }
        )
    for b in remote_merged:
        queue.append(
            {
                "kind": "remote-branch-delete",
                "reason": f"remote branch '{b}' is merged into origin/main",
                "command": f"git push origin --delete {b}",
            }
        )
    for path in live_worktrees_to_remove:
        queue.append(
            {
                "kind": "worktree-remove",
                "reason": f"live worktree '{path}' is on a merged branch",
                "command": f"git worktree remove {path}",
            }
        )
    return queue


# --------------------------------------------------------------------------- #
# Git plumbing.
# --------------------------------------------------------------------------- #
def _git(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    git_bin = shutil.which("git")
    if git_bin is None:
        print("error: git not found on PATH", file=sys.stderr)
        sys.exit(EXIT_GIT_FAILED)
    # git_bin is resolved via shutil.which; args are fixed git subcommands.
    return subprocess.run(  # noqa: S603
        [git_bin, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def worktree_branches() -> tuple[set[str], list[tuple[str, str]]]:
    """Return (branches checked out in worktrees, [(path, branch)] for non-main)."""
    res = _git(["worktree", "list", "--porcelain"])
    branches: set[str] = set()
    entries: list[tuple[str, str]] = []
    cur_path = ""
    for line in res.stdout.splitlines():
        if line.startswith("worktree "):
            cur_path = line[len("worktree ") :].strip()
        elif line.startswith("branch "):
            ref = line[len("branch ") :].strip()
            name = ref.rsplit("/", 1)[-1] if ref.startswith("refs/heads/") else ref
            branches.add(name)
            if Path(cur_path).resolve() != REPO_ROOT.resolve():
                entries.append((cur_path, name))
    return branches, entries


def collect(args: argparse.Namespace) -> dict:
    _git(["fetch", "origin", "--prune", "--quiet"])

    ahead_behind = _git(
        ["rev-list", "--left-right", "--count", "origin/main...HEAD"]
    ).stdout.strip()
    behind, ahead = parse_ahead_behind(ahead_behind)

    wt_branches, wt_entries = worktree_branches()

    local_merged = _git(["branch", "--merged", "origin/main"]).stdout
    local_deletable = deletable_merged_branches(local_merged, wt_branches)

    remote_merged_raw = _git(["branch", "-r", "--merged", "origin/main"]).stdout
    remote_merged = [
        name.strip()
        for _, name in parse_branch_list(remote_merged_raw)
        if name.strip()
        and not name.endswith("/main")
        and not name.endswith("/master")
        and "/HEAD" not in name
    ]
    # strip the "origin/" prefix for the delete command
    remote_merged = [n.split("/", 1)[1] for n in remote_merged if "/" in n]

    # Live worktrees whose branch is merged into origin/main -> queue removal.
    live_worktrees_to_remove = [
        path for path, branch in wt_entries if branch in local_deletable
    ]

    queue = build_queue(ahead, behind, remote_merged, live_worktrees_to_remove)

    return {
        "ahead": ahead,
        "behind": behind,
        "local_deletable": local_deletable,
        "remote_merged": remote_merged,
        "live_worktrees_to_remove": live_worktrees_to_remove,
        "queue": queue,
    }


def run_drift_checks() -> list[dict[str, str]]:
    """Read-only verification probes. Never mutate anything."""
    checks: list[dict[str, str]] = []
    venv_py = REPO_ROOT / ".venv" / "bin"
    ruff = venv_py / "ruff"
    if ruff.exists():
        r = subprocess.run(  # noqa: S603  — fixed local venv tool path
            [str(ruff), "check", "packages", "apps"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        checks.append(
            {"name": "ruff check packages apps", "ok": str(r.returncode == 0)}
        )
    alembic = venv_py / "alembic"
    if alembic.exists():
        r = subprocess.run(  # noqa: S603  — fixed local venv tool path
            [str(alembic), "check"],
            cwd=REPO_ROOT / "packages" / "db",
            capture_output=True,
            text=True,
        )
        ok = r.returncode == 0 and "No new upgrade operations" in (r.stdout + r.stderr)
        checks.append({"name": "alembic check (drift)", "ok": str(ok)})
    return checks


# --------------------------------------------------------------------------- #
# Apply (reversible only) + reporting.
# --------------------------------------------------------------------------- #
def apply_reversible(state: dict) -> list[str]:
    applied: list[str] = []
    for branch in state["local_deletable"]:
        r = _git(["branch", "-d", branch])
        if r.returncode == 0:
            applied.append(f"deleted local branch {branch}")
        else:
            applied.append(f"SKIP local branch {branch}: {r.stderr.strip()}")
    pr = _git(["worktree", "prune", "-v"])
    if pr.stdout.strip():
        applied.append(f"worktree prune: {pr.stdout.strip()}")
    return applied


def write_queue_file(state: dict, drift: list[dict[str, str]]) -> Path:
    out_dir = _paths.runtime_root() / "repo-steward"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "STEWARD_QUEUE.md"
    lines = [
        "# Repo Steward — operator approval queue",
        "",
        "These actions are irreversible or outward-facing. The Steward does NOT",
        "run them. Review, then run the ones you approve.",
        "",
        f"main: {state['ahead']} ahead / {state['behind']} behind origin/main",
        "",
    ]
    if not state["queue"]:
        lines.append("_Queue is empty — nothing awaiting approval._")
    else:
        for item in state["queue"]:
            lines.append(f"- **{item['kind']}** — {item['reason']}")
            lines.append(f"  ```\n  {item['command']}\n  ```")
    lines += ["", "## Drift checks (read-only)", ""]
    for c in drift:
        mark = "✅" if c["ok"] == "True" else "❌"
        lines.append(f"- {mark} {c['name']}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Repo Steward — git/mission hygiene.")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="perform the reversible (local-only) set; default is dry-run",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable summary")
    ap.add_argument(
        "--no-drift", action="store_true", help="skip ruff/alembic drift probes"
    )
    args = ap.parse_args(argv)

    state = collect(args)
    drift = [] if args.no_drift else run_drift_checks()

    applied: list[str] = []
    if args.apply:
        applied = apply_reversible(state)

    queue_file = write_queue_file(state, drift)

    if args.json:
        print(json.dumps({**state, "applied": applied, "drift": drift}, indent=2))
        return EXIT_OK

    print("=== Repo Steward ===")
    print(f"main: {state['ahead']} ahead / {state['behind']} behind origin/main")
    print()
    label = "Applied (reversible, local)" if args.apply else "Would auto-apply (run --apply)"
    print(f"-- {label} --")
    if args.apply:
        for line in applied or ["(nothing)"]:
            print(f"  {line}")
    else:
        for b in state["local_deletable"] or ["(no merged local branches)"]:
            print(f"  delete local branch: {b}")
    print()
    print("-- Approval queue (operator runs these) --")
    for item in state["queue"] or [{"kind": "(empty)", "command": ""}]:
        print(f"  [{item['kind']}] {item.get('command', '')}")
    print()
    print("-- Drift checks --")
    for c in drift or [{"name": "(skipped)", "ok": "True"}]:
        mark = "OK " if c["ok"] == "True" else "FAIL"
        print(f"  {mark} {c['name']}")
    print()
    print(f"Approval queue written to: {queue_file}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
