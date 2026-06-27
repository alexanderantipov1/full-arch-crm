# Incidents — revenue-intelligence-analytics-v1 (ENG-504)

## 2026-06-17 — Blocked: worktree launch refused, canonical checkout dirty
`launch_worker.py --workspace worktree --branch-base main` pre-flight rejected
the launch: the canonical checkout `/Users/eduardkarionov/Desktop/Fusion_crm` has
uncommitted changes. The dirty set is a mix of (a) this session's mission
artifacts + strategy edits and (b) **other sessions' uncommitted work**
(`.agents/orchestration/eng-503-find-person-link-v1/`, `ga4-dimensions-v1/`,
`lead-attribution-v1/`, `mattermost-prod-bringup-v1/`, several
`interactive-messenger-layer-v1/*` files) and junk duplicates (`* 2.md`,
`test_log_secret_redaction 2.py`).

Per `PARALLEL_WORK_POLICY.md`, the Orchestrator must NOT `git add -A`, commit, or
stash files it did not create (other sessions may be mid-edit). Committing only
this session's files does not clean the tree because the other sessions' untracked
files remain, so the launcher pre-flight still fails.

`Needs decision:` how to obtain a clean base for the isolated worktree without
disturbing other sessions' work. Escalated to operator.

## 2026-06-18 — B0 done; PR #185 CI red due to GitHub Actions BILLING (not code)
B0 foundation worker (session 3f5d89cd5223, pid 87043) completed and exited; draft
PR #185 opened with 3 commits (ENG-505/506/507) + report. CI on #185 shows FAILURE
on both `Web — eslint+tsc+vitest` and `Lint + typecheck + tests`, but the GitHub
annotation is: "The job was not started because recent account payments have failed
or your spending limit needs to be increased." So the red CI is an **account
billing block**, not a code defect — the jobs never started. Worker's local
verification (ruff + mypy + alembic check + 60+ unit / 4 integration tests on a
scratch Postgres) was clean. `Needs approval:` operator to resolve GitHub Actions
billing (or accept local + Codex cross-runtime review as the verification gate).
Do-not-merge conditions from the worker report still stand (real-data backfill,
`infra/docker/init-schemas.sql` analytics line, web tsc, Codex review).
