# ENG-228 Tenant Isolation Worker Report

Linear issue: ENG-228
Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-228/triage-and-fix-full-pytest-suite-failures
Task id: ENG-228-TENANT-ISOLATION
Worker role: tenant isolation triage
Status: Blocked for this bounded worker scope

## Summary

I did not make product or test changes. The current tenant isolation failures
cannot be fixed safely by a small edit limited to
`tests/integration/test_tenant_isolation.py`.

There are two separate failure classes:

1. The structural sweep correctly finds repository read methods without a
   `tenant_id` parameter.
2. The Phase B live isolation assertion is still an intentional shim and will
   fail for every structurally compliant read method once tenant schema support
   is active.

Weakening, skipping, or xfail-ing either layer would hide the cross-tenant leak
safety net, so I left the tests unchanged.

## Required Context Read

- `CLAUDE.md`
- `AGENTS.md`
- `tests/integration/test_tenant_isolation.py`
- `tests/conftest.py`
- `tests/_tenant_helpers.py`
- `.agents/CLAUDE.md`
- `.agents/AGENTS.md`
- `.agents/orchestration/CLAUDE.md`
- `.agents/orchestration/AGENTS.md`
- `packages/CLAUDE.md`
- `packages/tenant/CLAUDE.md`
- `packages/outreach/CLAUDE.md`
- `packages/outreach/AGENTS.md`

## Findings

Repository discovery currently reports:

- discovered read methods: 65
- structurally compliant read methods: 60
- read methods missing `tenant_id`: 5

Methods missing `tenant_id`:

- `packages/outreach/repository.py:164` -
  `SendRepository.get_global(send_id)`
- `packages/outreach/repository.py:194` -
  `SendRepository.find_by_message_id_global(message_id)`
- `packages/tenant/repository.py:27` -
  `TenantRepository.get_by_slug(slug)`
- `packages/tenant/repository.py:36` -
  `TenantRepository.list_all()`
- `packages/tenant/repository.py:57` -
  `TenantRepository.get_credential(credential_id)`

The outreach methods are intentionally global today for tracking and bounce
fallback flows, but that conflicts with the current repository safety-net
contract that every repository read method must accept `tenant_id` and filter
on it. Resolving that is not a test-only change; it needs an explicit product
and architecture decision.

The tenant repository methods are mixed:

- `get_by_slug` and `list_all` read the tenant root table itself, so they may
  need a documented global-root exception or a different contract from
  tenant-scoped domain tables.
- `get_credential` reads `tenant.integration_credential` by id and the service
  filters after the read. That is exactly the pattern the safety-net is meant
  to prevent, and should be changed in implementation code to read by
  `(tenant_id, credential_id)`.

The Phase B live assertion is still a hard-failing shim in
`test_repository_read_method_filters_by_tenant_id`. Implementing it properly
requires a method-argument resolver for 60 compliant read methods, seeded row
mapping per domain, and result-id extraction that understands single-row,
list-row, and aggregate-like reads. That is broader than a small safe edit.

## Recommendation

Split ENG-228 into implementation issues rather than making a local test-only
patch:

1. Tenant isolation contract decision
   - Define how the safety-net treats root tenant reads such as
     `TenantRepository.get_by_slug` and `TenantRepository.list_all`.
   - If exceptions are allowed, require a narrow allowlist with written
     justification in the test, not a blanket repository exemption.

2. Tenant credential repository hardening
   - Change `TenantRepository.get_credential` to require `tenant_id` and filter
     by both `IntegrationCredential.id` and `IntegrationCredential.tenant_id`.
   - Update `TenantService.revoke_credential` and any credential service call
     sites to pass tenant context before the row is read.

3. Outreach tracking and bounce global lookup redesign
   - Decide whether global send lookups remain acceptable because HMAC tokens
     or caller-side tenant checks are the security boundary.
   - If acceptable, represent them as explicit, audited safety-net exceptions
     with tests proving token or tenant verification happens before side
     effects.
   - If not acceptable, change token and bounce flows so reads can be scoped by
     tenant before querying `outreach.send`.

4. Phase B live isolation implementation
   - Replace the shim in
     `test_repository_read_method_filters_by_tenant_id` with a real harness.
   - Map each repository read method's required arguments from
     `TwoTenantContext.seeded_ids`.
   - Assert tenant A calls never return tenant B seeded ids, and vice versa.
   - Keep this separate from product repository changes so safety-net defects
     and product isolation defects are reviewable independently.

## Verification

No focused pytest run was executed because no code changes were made, per the
worker instruction to run the focused tenant isolation test only if changes are
made.

Read-only commands used:

- `git status --short`
- `git diff -- tests/integration/test_tenant_isolation.py tests/conftest.py tests/_tenant_helpers.py`
- repository discovery via `PYTHONPATH=tests:. python - <<'PY' ...`
- `python3 .agents/skills/agent-orchestrator/scripts/status_wave.py --mission .agents/orchestration/current`

## Changed Files

- `.agents/orchestration/current/reports/ENG-228-TENANT-ISOLATION-worker-report.md`

## Residual Risk

The full pytest suite will continue to fail on tenant isolation until the
structural product issues and Phase B live harness are addressed. Treat this as
a blocker for claiming full-suite green, not as a reason to weaken the
tenant-isolation safety net.
