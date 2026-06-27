---
description: Run the Fusion CRM Repo Steward — reversible git/mission hygiene + an operator approval queue for irreversible actions.
---

Steward arguments (optional): **$ARGUMENTS**

Use this command to tidy the repo periodically the way an Integrator would:
merged branches, stale worktrees, the `current` mission pointer, and surfacing
push / PR / remote-cleanup work. The Steward is the *acting* counterpart to the
read-only `/reviewer`.

## Run it

Read `.agents/skills/repo-steward/SKILL.md` and follow the role exactly, then:

```bash
python3 .agents/skills/repo-steward/scripts/steward.py --apply
```

- `--apply` performs ONLY the reversible, local-only set (delete local
  branches merged into `origin/main`; `git worktree prune`). Omit it for a
  pure dry-run.
- Every irreversible / outward-facing action (push to main, remote branch
  delete, live worktree remove, `current` repoint, PR close) is written to the
  approval queue at `<runtime_root>/repo-steward/STEWARD_QUEUE.md` and printed —
  the Steward does NOT execute these.

## Hard limits (enforced in the script, restated for the session)

- Do not push, delete remote refs, deploy, touch `.env*`, or edit product code.
- Do not repoint `current` or remove a live worktree autonomously — surface
  them as findings with the suggested command.

## Report back

1. What was auto-applied (reversible).
2. The approval queue (exact commands), grouped by kind.
3. Drift checks (`ruff`, `alembic check`) pass/fail.

Then stop and let the operator approve the queue.
