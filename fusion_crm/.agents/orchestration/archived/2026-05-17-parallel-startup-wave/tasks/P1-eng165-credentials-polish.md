# Task P1 — ENG-165 Credentials Polish

## Role

Implementation worker.

## Goal

Polish the tenant-owned provider credential UI/API path so operators can enter Salesforce and CareStack app credentials from the production settings surface with clear state and errors.

## Linear

- ENG-165

## Owned Write Scope

- `apps/web/components/integrations/ProviderCard.tsx`
- `apps/web/lib/api/hooks/useCredentials.ts`
- `apps/web/lib/api/schemas/tenant.ts`
- `apps/web/lib/msw/outreachHandlers.ts`
- `apps/web/tests/unit/schemas.test.ts`
- `apps/web/tests/unit/useCredentials.test.tsx`
- `tests/api/test_tenant_credential_routes.py`
- `tests/tenant/test_credential_service.py`

## Out Of Scope

- Deployment scripts, GitHub Actions, Cloud Run, env vars.
- New DB migrations.
- Salesforce OAuth route behavior except through existing credential metadata contracts.
- Commits, pushes, deploys, destructive git commands.

## Acceptance

- Credential form has production-usable labels, saved/error states, and no misleading mock/real mismatch.
- Secret values are never echoed back into UI state after save.
- Focused frontend/backend tests cover changed behavior.
- Final report lists changed files, commands, results, and blockers.

