# ENG-190 Worker Report

## Summary

Implemented first-class `source_instance` scoping for provider/import external IDs.

The source-link uniqueness contract is now:

```text
tenant_id + source_system + source_instance + source_kind + source_id
```

when `source_id IS NOT NULL`.

## Changed files

- `packages/identity/models.py`
- `packages/identity/repository.py`
- `packages/identity/schemas.py`
- `packages/identity/service.py`
- `packages/identity/CLAUDE.md`
- `packages/ingest/models.py`
- `packages/ingest/schemas.py`
- `packages/ingest/service.py`
- `packages/ingest/sf_lead_service.py`
- `packages/ingest/carestack_patient_service.py`
- `packages/db/alembic/versions/20260520_0500_d1e2f3a4b5c6_source_instance_scoped_source_links.py`
- `apps/web/lib/api/schemas/sourceData.ts`
- `docs/architecture/IDENTITY_RELATIONSHIP_GRAPH.md`
- `docs/data-model/CATALOG.md`
- `tests/conftest.py`
- `tests/identity/test_models.py`
- `tests/identity/test_service.py`
- `tests/identity/test_resolve_or_create_from_hint.py`
- `tests/ingest/test_normalized_person_hint_model.py`
- `tests/ingest/test_normalized_person_hint_service.py`
- `tests/ingest/test_dev_source_data_service.py`
- `tests/ingest/test_sf_lead_service.py`
- `tests/ingest/test_carestack_patient_service.py`
- `tests/integration/test_tenant_isolation.py`

## Verification

- `uv run pytest tests/identity/test_service.py tests/identity/test_resolve_or_create_from_hint.py tests/identity/test_models.py tests/ingest/test_normalized_person_hint_model.py tests/ingest/test_normalized_person_hint_service.py tests/ingest/test_dev_source_data_service.py tests/ingest/test_sf_lead_service.py tests/ingest/test_carestack_patient_service.py -q`
  - Passed: `80 passed`
- `make lint`
  - Passed
- `uv run mypy .`
  - Passed: `Success: no issues found in 223 source files`
- Initial `make test`
  - Failed before migration because the local DB did not yet have `identity.source_link.source_instance`.
- `cd packages/db && env -u SECRET_KEY -u REDIS_URL DATABASE_URL_SYNC=postgresql+psycopg://fusion:fusion@127.0.0.1:5434/fusion PYTHONPATH=../.. uv run alembic upgrade head`
  - Passed: applied `c7d8e9f1a2b3 -> d1e2f3a4b5c6`
- `make test`
  - Passed: `568 passed, 10 skipped`
- `cd packages/db && env -u SECRET_KEY -u REDIS_URL DATABASE_URL_SYNC=postgresql+psycopg://fusion:fusion@127.0.0.1:5434/fusion PYTHONPATH=../.. uv run alembic check`
  - Passed: `No new upgrade operations detected.`
- `git diff --check`
  - Passed

## Risks and blockers

- The local verification database was upgraded to the new ENG-190 Alembic head for the full test run.
- Background worker launch failed because the local `codex exec` CLI rejected the launcher contract. Foreground execution completed the code work, and this report was written by the Orchestrator after the worker could not write `.agents` state directly.

## Do-not-merge conditions

- None from ENG-190 verification.

ENG-183 remains blocked until product starts it explicitly after this source-instance scoping work is accepted.
