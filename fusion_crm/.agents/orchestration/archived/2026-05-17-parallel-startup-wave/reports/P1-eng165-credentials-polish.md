# P1 ENG-165 Credentials Polish Report

Task ID: P1
Linear issue: ENG-165
Agent role: implementation worker + Codex controller review
Status: complete

## Summary

Self-service provider credentials were polished in the existing
tenant-owned credential surface.

Implemented:

- `App credentials` is only shown for supported bootstrap providers:
  `salesforce` and `carestack`.
- Provider-specific field labels for Salesforce Connected App credentials and
  CareStack password-grant credentials.
- Explicit saved state after successful credential save.
- Error state reset when the operator edits or cancels the form.
- Frontend bootstrap schema is strict and rejects cross-provider fields.
- MSW validates `/api/tenant/credentials` with the same Zod schema and returns
  an API error envelope for invalid payloads.
- Hook tests prove unsupported providers do not issue `fetch`, and secret /
  payload fields from a mocked response do not flow into parsed hook data.
- Codex added the matching backend Pydantic guard so production API also
  rejects cross-provider bootstrap fields instead of silently ignoring them.

## Files Changed

- `apps/web/components/integrations/ProviderCard.tsx`
- `apps/web/lib/api/schemas/tenant.ts`
- `apps/web/lib/msw/outreachHandlers.ts`
- `apps/web/tests/unit/schemas.test.ts`
- `apps/web/tests/unit/useCredentials.test.tsx`
- `packages/tenant/schemas.py`
- `tests/api/test_tenant_credential_routes.py`

## Verification

- `.venv/bin/python -m pytest tests/api/test_tenant_credential_routes.py tests/tenant/test_credential_service.py -q` => 30 passed.
- `npm run --prefix apps/web test -- --run tests/unit/schemas.test.ts tests/unit/useCredentials.test.tsx` => 10 passed.
- `npm run --prefix apps/web typecheck` => passed.
- `npm run --prefix apps/web lint` => passed.
- `make lint` => passed.
- `make verify` => passed.
- `git diff --check` => passed.

## Notes

- Direct system `pytest` may fail without the project virtualenv because the
  system interpreter lacks project dependencies.
- The worker reported older local Node path friction; the main workspace
  `npm run --prefix apps/web lint` passed without extra PATH changes.

