# ENG-207 Worker Report

## Summary

Verified the current ENG-204 / ENG-205 / ENG-206 source-data wave as an
integration pass without changing implementation code.

The focused wave checks are healthy:

- ENG-204 source-data backend route, service projection, schemas, frontend hook,
  page, and focused tests are present.
- ENG-205 legacy integrations UI move is represented by a redirect from
  `/integrations` to `/settings/tenant?tab=integrations`, tenant-settings tab
  query handling, and removed legacy Salesforce Lead UI files.
- ENG-206 people search now has a local-dev source-data fallback that maps
  imported Salesforce and CareStack records into the existing provider match
  shapes.
- Focused backend tests, focused Python lint/typecheck, and web
  lint/typecheck/tests passed.

Repository-wide standard verification is not clean yet. The blockers are not
fixed here because this worker is report-only and the failures are either
outside the source-data wave scope or environment/toolchain related.

## Commands

- `make lint` - failed.
  - Root-cause evidence: `ruff check .` stops on `.agents/dashboard/server.py`.
  - Representative findings:
    - `I001` import block unsorted at `.agents/dashboard/server.py:4`
    - `F401` unused `os` at `.agents/dashboard/server.py:8`
    - `UP017` prefers `datetime.UTC` over `timezone.utc`
    - `S603` / `S607` on `subprocess.run(["git", *args], ...)`

- `mypy .` - failed.
  - Root-cause evidence: 49 errors in existing tests, including:
    - SQLAlchemy `quoted_name | None` dictionary key typing in
      `tests/interaction/test_models.py` and `tests/identity/test_models.py`
    - method monkeypatch assignment errors in interaction/outreach tests
    - `UUID` vs `TenantId` NewType mismatches in integration/worker tests
    - `bytes | memoryview[int]` union handling in outreach tests

- `make test` - failed.
  - Root-cause evidence: `python -m pytest -q` uses the system Python 3.11
    environment and fails during collection.
  - Representative missing dependencies:
    - `ModuleNotFoundError: No module named 'structlog'`
    - `ModuleNotFoundError: No module named 'respx'`
    - `ModuleNotFoundError: No module named 'chevron'`

- `cd packages/db && alembic check` - failed.
  - Root-cause evidence: Alembic uses the system Python 3.11 environment and
    fails before metadata comparison while loading `Settings`.
  - Missing required env vars:
    - `SECRET_KEY`
    - `DATABASE_URL`
    - `REDIS_URL`

- `uv run pytest tests/api/test_dev_source_data.py tests/ingest/test_dev_source_data_service.py tests/api/test_integrations_carestack_import.py tests/ingest/test_carestack_patient_service.py -q` - passed.
  - Result: `8 passed in 0.64s`

- `uv run ruff check apps/api/routers/dev.py packages/ingest/repository.py packages/ingest/schemas.py packages/ingest/service.py packages/ingest/carestack_patient_service.py tests/api/test_dev_source_data.py tests/api/test_integrations_carestack_import.py tests/ingest/test_dev_source_data_service.py tests/ingest/test_carestack_patient_service.py` - passed.
  - Result: `All checks passed!`

- `uv run mypy apps/api/routers/dev.py packages/ingest/repository.py packages/ingest/schemas.py packages/ingest/service.py packages/ingest/carestack_patient_service.py tests/api/test_dev_source_data.py tests/api/test_integrations_carestack_import.py tests/ingest/test_dev_source_data_service.py tests/ingest/test_carestack_patient_service.py` - passed.
  - Result: `Success: no issues found in 9 source files`

- `cd apps/web && npm run typecheck` - passed.
  - Result: `tsc --noEmit` completed with exit code 0.

- `cd apps/web && npm run lint` - passed.
  - Result: `No ESLint warnings or errors`

- `cd apps/web && npm run test` - passed.
  - Result: 5 files / 24 tests passed.

## Findings

- ENG-204's FastAPI `/dev/source-data` route is production-disabled via
  `require_dev_surface()` and delegates to `IngestService.list_dev_source_data`.
- The source-data service returns an allow-listed payload projection rather than
  verbatim `ingest.raw_event.payload`; focused tests cover withholding email,
  phone, birthdate, and clinical-note fields from the payload projection.
- CareStack Patient import follows the intended capture path:
  raw event capture, normalized person hint capture, then
  `IdentityService.resolve_or_create_from_hint`.
- ENG-206's local source-data people-search fallback is local-dev gated with
  `NEXT_PUBLIC_ENVIRONMENT === "local"` and preserves provider warning behavior
  when no imported local match exists.
- The current worktree contains many unrelated modified/untracked files. This
  worker inspected them only and did not revert or edit them.

## Blockers

- Repository-wide `make lint` is blocked by `.agents/dashboard/server.py`.
- Repository-wide `mypy .` is blocked by existing test typing issues outside
  the focused source-data wave files.
- Repository-wide `make test` is blocked by the active `python` resolving to a
  system Python 3.11 environment missing project/dev dependencies.
- `cd packages/db && alembic check` is blocked before migration comparison by
  missing required environment variables in the active shell.

## Ready/Not Ready Recommendation

Not ready for merge as a repository-wide gate, because the required standard
verification loop does not pass.

The ENG-204 / ENG-205 / ENG-206 wave itself is conditionally ready from this
integration pass: focused Python checks, focused backend tests, and web
lint/typecheck/tests pass. Re-run the full standard loop after the `.agents`
lint issue, test typing debt, Python environment selection, and Alembic env
configuration are resolved.

## Changed Files

- `.agents/orchestration/current/reports/ENG-207-worker-report.md`
