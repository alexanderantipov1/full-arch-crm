# Lessons

## L-001: except Exception, never except BaseException in service/route code

Workers generated `except BaseException as exc` in 5 `_run_*` functions
in `apps/api/routers/backfill.py`. This swallows `asyncio.CancelledError`,
`KeyboardInterrupt`, and `SystemExit`, preventing clean shutdown on HTTP
cancel or Cloud Run scale-down. User caught this post-merge and hotfixed
directly on main (e20c23e). Rule: only infrastructure-level handlers
(process supervisors, signal handlers) may catch `BaseException`. Service
and route code must use `except Exception`.

## L-002: Worker prompts must include explicit commit instruction

Multiple workers completed implementation work but did not run `git commit`
until the orchestrator follow-up noticed uncommitted changes. Worker
prompts must include "YOU MUST commit your changes before reporting done"
as an explicit instruction, not rely on implicit expectation.

## L-003: Migration down_revision conflicts in parallel branches

When multiple workers create Alembic migrations on parallel branches,
they share the same `down_revision` (head at branch time). Merging the
first branch shifts head; the second branch's migration has a stale
`down_revision`. Solution: the integrator must run `alembic check` after
every merge and create a merge migration if needed. Worker prompts should
warn about this when parallel migration work is planned.

## L-004: Worktree workers need env setup preamble

Workers launched in git worktrees lack the venv, `.env`, and database
roles present in the main checkout. ENG-236 verification failed because
`SECRET_KEY`, `DATABASE_URL`, `REDIS_URL` were unset and local Postgres
lacked test roles. Worker prompts for worktree execution should include
env setup steps or reference a shared `.env.test` bootstrap.

## L-005: Solo dev coordination gap is normal but must be recorded

User made 2 direct operations between orchestrator turns: hotfix e20c23e
(no PR ceremony) and full ENG-248 cycle (implementation + PR #101 + merge
without orchestrator handoff). This is valid solo dev workflow but creates
a coordination gap — the orchestrator must check recent git history at
session start to avoid duplicating or conflicting with direct work.

