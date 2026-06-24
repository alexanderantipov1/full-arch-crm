# Verification

## Recorded Verification

- ENG-227: Alembic current/check passed; targeted backend and frontend checks
  passed. Later full-suite verification exposed unrelated backlog.
- ENG-228: focused ingest metadata, outreach, and bounce clusters passed; the
  tenant-isolation worker correctly blocked instead of weakening the safety net.
- ENG-229: tenant-isolation exception contract was reviewed and narrowed.
- ENG-230: tenant credential reads were hardened; focused suites, `make lint`,
  `make typecheck`, `make verify`, and Alembic check passed. Full `make test`
  still failed only on the ENG-231 Phase B tenant-isolation shim.
- ENG-231: focused tenant isolation passed with 132 tests; `make verify`
  passed with 25 tests; full `make test` passed with 646 tests; Alembic check
  passed.
- ENG-232: `mypy .` passed; focused typing test suite passed with 89 tests;
  `make verify` passed with 25 tests; full `make test` passed with 646 tests;
  `cd packages/db && alembic check` passed.

## Required Before PR

The worktree has later dirty web, strategy, and mission-state changes. Rerun
the full gate after those changes are either isolated or intentionally included:

- `make lint`
- `mypy .`
- `make test`
- `cd packages/db && alembic check`

For the web tail, also run:

- `cd apps/web && npm run lint`
- relevant Playwright smoke coverage

## Fresh Gate — 2026-05-22T20:11:27Z

- `make lint`: passed.
- `mypy .`: passed.
- `make test`: initial run used system Python 3.11 and failed collection on
  missing dev dependencies; rerun as `PATH=.venv/bin:$PATH make test` passed
  with 646 tests.
- `cd packages/db && alembic check`: initial attempts lacked required settings
  and then used the wrong local Postgres port; rerun with local dev values and
  compose ports (`127.0.0.1:5434`, Redis `127.0.0.1:6380`) passed with no new
  upgrade operations.
- `cd apps/web && npm run lint`: passed.
- `cd apps/web && npx playwright test tests/e2e/staff-smoke.spec.ts`: passed
  with 8 tests across desktop Chromium and mobile Chromium.

## Reviewer Follow-Up — 2026-05-22T20:21:47Z

- Linear live state for ENG-227 and ENG-228 was updated to `Done`.
- The Alembic check is reproducible locally only with explicit local dev env
  values and the compose-reported Postgres port. The passing command and
  outcome remain recorded above; no `.env*` file was read or copied into
  mission state.
- Local runtime no longer references missing raw worker log files. The
  sessions were print-mode launches, so reports and `runlog.md` are the
  available execution evidence.
- Stale prompt `ENG-227-VERIFY-SCAN-8d0cfcd6d591.md` was removed.

## ENG-233 / ENG-234 Production Activation — 2026-05-22T23:25:03Z

- GitHub Actions `deploy-prod` run `26314615499` passed, including lint,
  typecheck, tests, Alembic upgrade, API deploy, and API smoke.
- Operator deploy ran the canonical script without `CI_MODE=1`:
  `DEPLOY_ONLY=1 SERVICES=jobs IMAGE_TAG=3073f5aec7b069b57676dd9884f9bddb2c842ebb ./infra/scripts/deploy_cloud_run.sh`.
- Production state check confirmed:
  - `fusion-job-salesforce-token-keepalive`
  - `fusion-sched-salesforce-token-keepalive`
  - `fusion-job-sf-pull`
  - `fusion-job-cs-pull`
- All checked jobs point at image tag
  `3073f5aec7b069b57676dd9884f9bddb2c842ebb`.
- Salesforce scheduled pull execution `fusion-job-sf-pull-27ps9` completed
  successfully and logged `salesforce_ok=1`, `salesforce_failed=0`,
  `tenants=1`.
- Salesforce API calls returned HTTP 200 for production Lead and Event
  queries; the run imported 50 leads and zero events for that window.
- Salesforce token keepalive execution
  `fusion-job-salesforce-token-keepalive-ftdfz` completed successfully and
  logged `refreshed=1`, `failed=0`, `needs_reconnect=0`.
- CareStack scheduled pull execution `fusion-job-cs-pull-sm654` completed
  successfully and logged `carestack_ok=1`, `carestack_failed=0`,
  `tenants=1`; the run imported 80 patients and 69 appointments and saw four
  locations.
