# ENG-233 Worker Report

## Summary

Implemented Salesforce OAuth token keepalive for local arq worker runtime. The
change adds a proactive refresh path that uses the existing Salesforce
refresh-token grant and credential persistence callback, marks dead refresh
tokens as expired, and surfaces expired usable credentials as
`needs_reconnect` in the integrations API and web UI. Successful keepalive
refreshes also update credential `last_refreshed_at`.

Production scheduler wiring was intentionally not changed in this slice because
Cloud Scheduler / Cloud Run job changes require an explicit deployment scope
review under `docs/DEPLOYMENT_RULES.md`.

## Changed Files

- `packages/integrations/salesforce/client.py`
- `apps/worker/jobs/salesforce_token_keepalive.py`
- `apps/worker/main.py`
- `apps/api/routers/integrations_list.py`
- `apps/web/lib/api/schemas/integrations.ts`
- `apps/web/components/integrations/ProviderCard.tsx`
- `apps/web/components/integrations/SfLeadsPanel.tsx`
- `tests/integrations/test_sf_client.py`
- `tests/worker/test_ingest_scheduled.py`
- `tests/api/test_integrations_list.py`
- `apps/web/tests/unit/schemas.test.ts`

## Verification

- `make lint` passed.
- `.venv/bin/mypy .` passed.
- `PATH=.venv/bin:$PATH make test` passed: 654 tests.
- `cd packages/db && set -a; source ../../.env; set +a; PATH=../../.venv/bin:$PATH alembic check` passed: no new upgrade operations detected.
- `cd apps/web && npm run lint` passed.
- `cd apps/web && npm run typecheck` passed.
- `cd apps/web && npm run test -- --run tests/unit/schemas.test.ts` passed: 10 tests.
- `cd apps/web && npm run e2e -- tests/e2e/staff-smoke.spec.ts` passed: 8 tests across desktop and mobile Chromium.
- `set -a; source .env; set +a; PATH=.venv/bin:$PATH arq --check apps.worker.main.WorkerSettings` passed.
- Manual local keepalive run returned `{'tenants': 1, 'refreshed': 0, 'skipped': 1, 'needs_reconnect': 0, 'failed': 0}` because there is no active Salesforce OAuth token locally.

## Notes

- Direct `make test` without `.venv` still fails on collection because the
  shell resolves system Python 3.11 without project dev dependencies. The
  project virtualenv run passed.
- Direct `alembic check` without env vars still fails because `SECRET_KEY`,
  `DATABASE_URL`, and `REDIS_URL` are required. The `.env`-backed run passed.
- This can be implemented and verified before the user reconnects Salesforce.
  It cannot refresh Salesforce in runtime until an active OAuth credential with
  a valid `refresh_token` exists.
