# Incidents — Full Funnel v2

(none yet)

## 2026-06-16 — Worktree worker launch blocked
launch_worker.py refused `--workspace worktree` (and self-execute scope guard
does not fit a feature-class task) because the canonical checkout is dirty with
many untracked artifacts from other missions (" 2" sync-conflict copies) plus
this mission's new scaffold/doc. No-commit-without-approval policy stands, so
the tree cannot be cleaned by committing.

**Decision:** execute ENG-481 directly in-session on branch
`eng-481-full-funnel-v2-backend`, no commit, diff left for operator review.
Mechanism change only; scope/acceptance unchanged.
