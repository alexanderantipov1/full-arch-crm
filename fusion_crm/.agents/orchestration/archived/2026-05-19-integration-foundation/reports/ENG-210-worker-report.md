# ENG-210 Worker Report

## Scope

Implemented the Phase B `two_tenant_db` fixture path and replaced the live
tenant-isolation shim in `tests/integration/test_tenant_isolation.py`.

Owned files changed:

- `tests/conftest.py`
- `tests/integration/test_tenant_isolation.py`
- `.agents/orchestration/current/reports/ENG-210-worker-report.md`

## Changes

- Replaced the `two_tenant_db` Phase B `RuntimeError` placeholder with real
  rollback-only seeding.
- The fixture now creates two `tenant.tenant` rows and tenant-scoped rows for
  identity, ops, actor, auth, interaction, audit, ingest, integrations, phi,
  and tenant configuration tables needed by the live sweep.
- The fixture records seeded IDs in `TwoTenantContext.seeded_ids`, rolls back
  after each test, closes the session, and disposes the async engine to avoid
  asyncpg connection reuse across pytest event loops.
- Replaced the live-isolation test shim with a generic assertion that calls
  each supported repository method as tenant A with tenant B lookup arguments,
  and vice versa. Returned IDs are checked against the opposite tenant's seeded
  IDs.
- Added documented method-level exemptions for reads that are intentionally
  global:
  - `TenantRepository.get_by_slug`
  - `TenantRepository.list_all`
  - `TenantRepository.get_credential`
  - `SendRepository.find_by_message_id_global`
  - `SendRepository.get_global`
- Kept outreach live-row seeding out of this task because ENG-211 owns outreach
  tests. Outreach methods that already satisfy the structural `tenant_id`
  contract are skipped only in the live seeded-row sweep with an explicit skip
  reason.

## Verification

- Initial reproduction:
  - `uv run pytest tests/integration/test_tenant_isolation.py -q`
  - Result: failed with `two_tenant_db Phase B body not yet implemented` errors,
    plus structural failures for intentionally global reads.
- Focused test after changes:
  - `uv run pytest tests/integration/test_tenant_isolation.py -q`
  - Result: `105 passed, 10 skipped`
- Lint on changed files:
  - `uv run ruff check tests/conftest.py tests/integration/test_tenant_isolation.py`
  - Result: passed
- Full test suite:
  - `make test`
  - Result: `566 passed, 10 skipped`
- Repository lint:
  - `make lint`
  - Result: passed
- Type check:
  - `mypy .`
  - Result: passed
- Diff whitespace:
  - `git diff --check -- tests/conftest.py tests/integration/test_tenant_isolation.py`
  - Result: passed

## Remaining Blockers

- `cd packages/db && alembic check` could not run in this shell because neither
  `DATABASE_URL_SYNC` nor `DATABASE_URL` is set.
- Retried with `uv run alembic check` from `packages/db`; it failed with the
  same missing Alembic database URL configuration.
- Per repo rules, no `.env*` files were edited.
