# J1 — Self-service integration credentials UI/API review

## Scope

- Worker implementation for operator-entered provider bootstrap credentials.
- Codex review and verification.
- No production mutation in this workstream.

## Summary

Accepted after one test-harness correction.

The worker added a tenant-scoped metadata-only credentials API and a UI form
on provider cards for storing Salesforce and CareStack bootstrap credentials.
Secret-bearing inputs are accepted only on the write path and persisted through
`IntegrationCredentialService.upsert`, which encrypts payloads. Response DTOs
continue to omit `payload`.

## Files Changed By J1

- `apps/api/routers/tenant.py`
- `packages/tenant/credential_service.py`
- `packages/tenant/schemas.py`
- `tests/tenant/test_credential_service.py`
- `tests/api/test_tenant_credential_routes.py`
- `apps/web/components/integrations/ProviderCard.tsx`
- `apps/web/lib/api/hooks/useCredentials.ts`
- `apps/web/lib/api/schemas/tenant.ts`
- `apps/web/lib/msw/outreachHandlers.ts`
- `apps/web/tests/unit/schemas.test.ts`
- `apps/web/tests/unit/useCredentials.test.tsx`

## Codex Review Note

Initial backend focused tests failed because the unit-test mock for
`AsyncSession.refresh()` did not simulate database-generated UUIDs for newly
inserted credential rows. Codex fixed the mock in
`tests/tenant/test_credential_service.py`; production code did not need a
change for that failure.

## Verification

```text
.venv/bin/python -m pytest tests/core/test_deploy_prod_smoke_logging.py tests/core/test_env_reference_matches_settings.py tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py -q
48 passed in 1.15s

.venv/bin/ruff check apps/api/routers/tenant.py packages/tenant/credential_service.py packages/tenant/schemas.py tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py
All checks passed!

cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run test
4 files, 17 tests passed

cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run typecheck
passed

cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run lint
passed

git diff --check
passed
```

## Residual Risk

- No browser visual smoke was run for the new form in this review pass.
- Full repository verify loop was not run; focused tests covered the changed
  backend/frontend contracts.
