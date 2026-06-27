# ENG-209 Worker Report

## Linear

- linear_issue_id: ENG-209
- linear_status: In Progress
- linear_title: Full verify cleanup: make Alembic check runnable in supported local env

## Summary

Alembic no longer instantiates full runtime `Settings` during metadata
comparison. It now reads only `DATABASE_URL_SYNC` or, when that is absent,
`DATABASE_URL`, while preserving the full runtime requirements for
`SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL`.

## Changes

- Added `AlembicDatabaseSettings` and `get_alembic_database_url()` in
  `packages/core/config.py`.
- Kept Secret Manager URL resolution in the narrow Alembic settings path by
  reusing the existing `resolve_mapping()` validator pattern.
- Allowed Alembic to use `DATABASE_URL_SYNC` without requiring
  `DATABASE_URL`, and to fall back to `DATABASE_URL` when no sync URL is set.
- Preserved the existing async-to-sync driver conversion from `+asyncpg` to
  `+psycopg`.
- Updated `packages/db/alembic/env.py` to call the narrow helper instead of
  `get_settings()`.
- Added focused tests in `tests/core/test_alembic_database_url.py`.

## Verification

- `PYTHONPATH=. pytest tests/core/test_alembic_database_url.py -q` - passed,
  4 tests.
- `PYTHONPATH=. ruff check packages/core/config.py packages/db/alembic/env.py tests/core/test_alembic_database_url.py` - passed.
- `PYTHONPATH=. mypy packages/core/config.py tests/core/test_alembic_database_url.py` - passed.
- `env -u SECRET_KEY -u REDIS_URL DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/fusion_crm PYTHONPATH=../.. alembic check`
  from `packages/db` - progressed past the previous missing
  `SECRET_KEY` / `REDIS_URL` validation blocker. It stopped at local DB
  availability:
  `psycopg.OperationalError: connection failed: connection to server at "127.0.0.1", port 5432 failed: FATAL: database "fusion_crm" does not exist`.

## Changed Files

- `packages/core/config.py`
- `packages/db/alembic/env.py`
- `tests/core/test_alembic_database_url.py`
- `.agents/orchestration/current/reports/ENG-209-worker-report.md`

## Remaining Blockers

- Full `alembic check` still needs a local PostgreSQL database named
  `fusion_crm` reachable at `127.0.0.1:5432` for the verification URL used
  above.
- No deployment scripts, `.env*` files, shipped Alembic revision files, board,
  runtime, runlog, or linear-sync files were changed.
