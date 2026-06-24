# ENG-230-VERIFY-SCAN Worker Report

Linear issue: ENG-230
Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-230/harden-tenant-scoped-credential-and-send-repository-reads
Completed at: 2026-05-22T16:15:01Z

## Summary

Verified the first credential-scope patch and found one remaining gap:
`IntegrationCredentialService` still loaded tenant-bound credentials by global
primary key in `read_by_id`, `set_default`, `update_metadata`, and `delete`.
The Orchestrator closed that gap in the same ENG-230 scope by replacing those
loads with a tenant-scoped helper that filters by both `tenant_id` and
`credential_id`.

## Changed Files

- `packages/tenant/credential_service.py`
  - Made `read_by_id` require `tenant_id`.
  - Added `_get_credential_for_tenant`.
  - Replaced global `AsyncSession.get(IntegrationCredential, credential_id)`
    reads in credential service mutation paths.
- `tests/tenant/test_credential_service.py`
  - Added scoped `read_by_id` coverage.
  - Updated credential metadata/default/delete tests for the scoped SQL lookup.
  - Fixed audit secret assertion to use a non-flaky sentinel string.

## Verification

- `.venv/bin/ruff check ...`
  - Passed for ENG-230 touched tenant and tenant-isolation files.
- `.venv/bin/ruff format --check ...`
  - Passed after formatting two files.
- `python -m pytest -q tests/tenant/test_service.py tests/tenant/test_credential_service.py tests/tenant/test_location_import.py`
  - `52 passed`.
- `python -m pytest -q tests/integration/test_tenant_isolation.py::test_repository_read_method_takes_tenant_id tests/integration/test_tenant_isolation.py::test_root_or_global_read_allowlist_is_narrow_and_documented tests/integration/test_tenant_isolation.py::test_emit_repository_inventory`
  - `67 passed`.
- `python -m pytest -q tests/api/test_tenant_credential_routes.py`
  - `6 passed`.
- `python -m pytest -q tests/worker/test_bounce_poll.py tests/outreach/test_unsubscribe.py tests/outreach/test_open_tracking.py`
  - `22 passed`.
- `make lint`
  - Passed.
- `make typecheck`
  - Passed.
- `mypy .`
  - Failed on pre-existing test typing backlog outside ENG-230.
- `alembic check` against the documented local development DB
  - Passed. Exact local connection values are intentionally not recorded in
    the repository report.
- `make verify`
  - Passed: `25 passed`.
- `make test`
  - Failed only on ENG-231 Phase B tenant isolation shim:
    `61 failed, 585 passed`.

## Residual Work

- ENG-231 remains the owner for replacing the live tenant-isolation Phase B
  shim with real two-tenant repository assertions.
- The full `mypy .` test backlog remains outside ENG-230; `make typecheck`
  stays green for application and package code.
