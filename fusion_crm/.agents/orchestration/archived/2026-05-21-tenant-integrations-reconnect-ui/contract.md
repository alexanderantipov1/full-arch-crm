# Contract

## Scope (allowed files)

- `apps/web/app/(staff)/settings/tenant/page.tsx`
- `apps/web/lib/api/hooks/useTenantCredentials.ts` (or new file under
  `apps/web/lib/api/hooks/` if a fresh hook module is cleaner)
- New `apps/web/components/integrations/CredentialEditModal.tsx`
- New `apps/web/components/integrations/DisconnectConfirmModal.tsx`
- Optional helper: `apps/web/lib/utils/relativeTime.ts` (or
  co-located with one of the modals)
- Vitest files under `apps/web/__tests__/` mirroring the existing
  pattern.
- `.agents/orchestration/tenant-integrations-reconnect-ui/incidents.md`
  for any unexpected behavior found during the smoke pass.

## Out of scope

- Any backend changes (`apps/api/`, `packages/`, alembic).
- "Test connection" button (sibling issue if needed later).
- i18n / Russian localization.
- Provider rows other than Salesforce and CareStack (Vapi / OpenAI /
  Twilio etc. are covered by ENG-198).
- Multi-credential rows per provider (current UI shows one row per
  provider; multi-cred is a future concern).

## Boundaries

- Never echo stored secret values back to the DOM after save.
- Disconnect requires a typed confirmation matching the provider name
  (case-insensitive, trimmed).
- No PHI, no secrets in logs.
- No `git commit`, `git push`, or destructive ops from Worker.
- No skipping hooks (`--no-verify`) or signing.
