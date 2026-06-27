# ENG-230-CREDENTIAL-SCOPE Worker Report

Linear issue: ENG-230
Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-230/harden-tenant-scoped-credential-and-send-repository-reads
Completed at: 2026-05-22T16:10:06Z

## Summary

Implemented tenant-scoped credential reads for the legacy
`TenantRepository.get_credential` path. The repository method now requires
`tenant_id` and filters by both `tenant_id` and `credential_id` in SQL.
`TenantService.revoke_credential` now calls the scoped repository method
instead of fetching by primary key and checking tenant ownership after the
read.

## Changed Files

- `packages/tenant/repository.py`
  - Changed `TenantRepository.get_credential` signature to
    `(tenant_id, credential_id)`.
  - Replaced `AsyncSession.get()` with a `SELECT` constrained by
    `IntegrationCredential.tenant_id` and `IntegrationCredential.id`.
- `packages/tenant/service.py`
  - Updated `TenantService.revoke_credential` to use the scoped repository
    lookup.
- `tests/tenant/test_service.py`
  - Added service regression coverage for the scoped revoke lookup.
  - Added repository regression coverage that the generated statement includes
    both tenant and credential filters.

Read-only / verified:

- `tests/integration/test_tenant_isolation.py`
  - No allowlist changes were made by this worker.
  - Focused structural tenant isolation now passes with
    `TenantRepository.get_credential` no longer missing `tenant_id`.

## Commands Run

- `.venv/bin/ruff check packages/tenant/repository.py packages/tenant/service.py tests/tenant/test_service.py tests/integration/test_tenant_isolation.py`
  - Initial result: failed on import order in `tests/tenant/test_service.py`.
- `.venv/bin/ruff format --check packages/tenant/repository.py packages/tenant/service.py tests/tenant/test_service.py tests/integration/test_tenant_isolation.py`
  - Initial result: failed; `tests/tenant/test_service.py` needed formatting.
- `.venv/bin/python -m pytest -q tests/tenant/test_service.py tests/tenant/test_credential_service.py tests/tenant/test_location_import.py`
  - Result: `50 passed`.
- `.venv/bin/python -m pytest -q tests/integration/test_tenant_isolation.py::test_repository_read_method_takes_tenant_id tests/integration/test_tenant_isolation.py::test_root_or_global_read_allowlist_is_narrow_and_documented tests/integration/test_tenant_isolation.py::test_emit_repository_inventory`
  - Result: `67 passed`.
- `.venv/bin/ruff check --fix packages/tenant/repository.py packages/tenant/service.py tests/tenant/test_service.py tests/integration/test_tenant_isolation.py && .venv/bin/ruff format packages/tenant/repository.py packages/tenant/service.py tests/tenant/test_service.py tests/integration/test_tenant_isolation.py`
  - Result: import order fixed and one file reformatted.
- `.venv/bin/ruff check packages/tenant/repository.py packages/tenant/service.py tests/tenant/test_service.py tests/integration/test_tenant_isolation.py`
  - Result: passed.
- `.venv/bin/ruff format --check packages/tenant/repository.py packages/tenant/service.py tests/tenant/test_service.py tests/integration/test_tenant_isolation.py`
  - Result: passed.
- `.venv/bin/python -m pytest -q tests/tenant/test_service.py tests/tenant/test_credential_service.py tests/tenant/test_location_import.py`
  - Result: `50 passed`.
- `.venv/bin/python -m pytest -q tests/integration/test_tenant_isolation.py::test_repository_read_method_takes_tenant_id tests/integration/test_tenant_isolation.py::test_root_or_global_read_allowlist_is_narrow_and_documented tests/integration/test_tenant_isolation.py::test_emit_repository_inventory`
  - Result: `67 passed`.

## Residual Failures

No residual failures in the ENG-230 focused scope.

Orchestrator follow-up verification after the verifier gap was closed:

- `make lint`: passed.
- `make typecheck`: passed.
- Alembic check against local DB: passed.
- `make verify`: passed.
- Full `make test`: failed only on ENG-231 Phase B tenant-isolation shim
  (`61 failed, 585 passed`).
- Full `mypy .`: failed on the existing test typing backlog outside ENG-230.

## Risks

- The repository SQL-shape test verifies the generated statement contains both
  credential and tenant columns, but it remains a unit-level assertion with a
  mocked session, not a live database isolation test.
- Full live tenant isolation remains covered by the ENG-231 follow-up.
- The checkout had pre-existing modified files before this worker started;
  this worker did not revert or normalize unrelated changes.

## Do Not Merge Conditions

- Do not merge ENG-230 as a complete tenant-isolation program without the
  planned ENG-231 live Phase B harness.
- Do not merge if later integration changes reintroduce an unscoped
  `TenantRepository.get_credential` call or add it to the ENG-229 allowlist.
