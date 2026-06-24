# ENG-231-METHOD-MAP Worker Report

Linear issue: ENG-231
Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-231/implement-phase-b-live-tenant-isolation-harness
Completed at: 2026-05-22T16:25:15Z

## Summary

Mapped repository read methods discovered by
`tests/integration/test_tenant_isolation.py` to their required non-tenant
arguments, seeded row keys, and return shapes. The map was consumed by the
Orchestrator when replacing the Phase B shim with method-specific argument
resolvers.

## Findings Used

- Point reads must be tested with negative cross-lookups, not only same-tenant
  ids. Calling tenant A with tenant A row ids would not expose many missing
  tenant filters.
- `IdentityRepository.list_source_providers_for` echoes input UUID keys in its
  dict result, so the harness must not treat dict keys as leaked row ids.
- Tuple/list results such as `IngestRepository.list_source_records` require
  recursive result-id extraction.

## Changed Files

None by this worker. The Orchestrator implemented the final patch.

## Verification

Read-only mapping only. Final verification is recorded in the ENG-231
Orchestrator completion state.

## Risks

New repository read methods with `tenant_id` must add a Phase B argument
resolver. The harness now fails explicitly when a resolver is missing.
