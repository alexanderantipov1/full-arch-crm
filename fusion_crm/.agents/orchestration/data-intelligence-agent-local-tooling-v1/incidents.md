# Incidents

## 2026-06-01 — Stale MSW Handler Blocker Cleared

The isolated ENG-286 worktree inherited stale frontend MSW dashboard/payment
handlers from `origin/main`. Those handlers referenced deleted payment
fixtures and blocked frontend typecheck/dev-route verification before the Data
Intelligence slice could be verified.

Resolution:

- Removed the stale dashboard, project-manager, payments, and inspector MSW
  fallback handlers from the ENG-286 branch.
- Preserved auth, health, tenant, integration/person fallback, and outreach
  handlers.
- Added the missing `carestack_origin: []` fields required by current web
  schemas.

Status: resolved in this branch.

No incidents recorded.

## 2026-06-01 — Repo-Wide Lint Gate Blocked Outside ENG-286 Scope

During ENG-299 production review, full `make lint` was executed and failed on
unrelated Ruff findings outside the Data Intelligence mission:

- `packages/ingest/repository.py`
- `tests/ingest/test_carestack_patients_with_payments_sql.py`

The ENG-286 focused Ruff checks over changed mission code passed, and full
pytest, Mypy, Alembic check, web lint/typecheck, browser smoke, and
`git diff --check` passed after the tenant-isolation resolver update.

Status: resolved in this branch. After fast-forwarding to latest `origin/main`,
the remaining Ruff findings were fixed in the ingest-owned files and full
`make lint` passed. Full pytest, Mypy, Alembic check, web lint/typecheck,
browser smoke, and `git diff --check` were rerun on the updated base.
