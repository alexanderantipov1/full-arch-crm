# TASK-A–H Worker Report — Tenant Integrations Reconnect / Edit / Disconnect UI

- **Tasks:** TASK-A through TASK-H (combined in-session pass)
- **Linear:** ENG-214
- **Role / agent:** worker / claude-code
- **Branch:** eduardk/eng-214-tenant-integrations-sf-carestack-reconnect-edit-disconnect
- **Worktree:** /Users/eduardkarionov/Desktop/Fusion_crm

## Files created

- `apps/web/components/ui/dialog.tsx` — shadcn Dialog primitive over `@radix-ui/react-dialog` (already in deps).
- `apps/web/components/integrations/CredentialEditModal.tsx` — CareStack
  API-key re-key modal (masked input, calls `useApiKeyConnect`).
- `apps/web/components/integrations/DisconnectConfirmModal.tsx` —
  typed-confirmation disconnect modal (calls `useDisconnect`).
- `apps/web/tests/unit/CredentialEditModal.test.tsx` — 3 tests
  (submit happy path, empty-key guard, masked-input attributes).
- `apps/web/tests/unit/DisconnectConfirmModal.test.tsx` — 3 tests
  (typed-confirm enable/disable, submit calls DELETE, state reset
  on close).

## Files modified

- `apps/web/app/(staff)/settings/tenant/page.tsx`:
  - Imports new modals + `useConnectStart` + `Copy`/`KeyRound`/`Trash2`.
  - `ConnectedCard` rewritten: card now grid-style with the
    actions row, wired to per-provider hooks. SF row gets Reconnect
    + Disconnect + the new `SalesforceCallbackHint` block. CS row
    gets Edit key + Disconnect. Stale `ENG-128` tooltip placeholder
    removed.
  - `SalesforceCallbackHint` component: synthesises the callback URL
    from `NEXT_PUBLIC_OAUTH_REDIRECT_BASE_URL` (fallback to
    `window.location.origin`) and a Copy-to-clipboard control.
  - `refreshed_at` and `expires_at` now render as relative time
    via `formatRelative` with full ISO timestamp in the
    surrounding span's `title=` attribute.

## Diff summary

- Page: +96 / -13 lines.
- New modals + Dialog primitive: ~250 lines.
- Tests: ~180 lines.
- Total: ~520 lines added, ~13 removed.

## Verification commands run

| # | Command | Result |
|---|---|---|
| 1 | `npx tsc --noEmit` | OK (no output) |
| 2 | `npx eslint <new files>` | OK (no output) |
| 3 | `npx vitest run tests/unit/CredentialEditModal.test.tsx tests/unit/DisconnectConfirmModal.test.tsx` | 6 tests passed |
| 4 | `npx vitest run` (full web suite) | 30 tests passed across 7 files |
| 5 | `grep -RIn "Reconnect flow ships with ENG-128" apps/web` | empty (stale placeholder gone) |

## Manual smoke (TASK-H)

Manual browser checks are pending the user's confirmation in the
running Next.js dev server (`http://127.0.0.1:3000/settings/tenant?tab=integrations`):

- Salesforce row: Reconnect opens Google OAuth in a new tab;
  callback URL hint is visible and copy works.
- CareStack row: Edit key opens modal; masked input; save closes
  modal and re-fetches list.
- Either row: Disconnect opens confirmation modal; submit disabled
  until typed name matches (case-insensitive, trimmed); submit
  calls DELETE and modal closes.
- Refreshed / Expires show relative timestamps (or "—" when null).

User reported the dashboard contrast bug separately (light-theme
text was invisible); that is fixed inline in
`.agents/dashboard/static/index.html` but is OUT of ENG-214 scope.
Integrator should decide whether to bundle the fix into this PR or
ship a separate micro-PR.

## Risks / notes

- The `ConnectStartResponseSchema` is a discriminated union with
  `kind: "oauth_redirect" | "api_key_form" | "instant_connected"`.
  My SF Reconnect handler asserts `kind === "oauth_redirect"` and
  surfaces a toast otherwise. If backend ever changes the SF flow
  to `api_key_form` it will toast "unexpected response" — acceptable
  failure mode.
- `Provider` enum in `lib/api/schemas/common.ts` is the legacy 5-value
  set; the page's `ProviderKind` is the broader 20-value union. The
  runtime guards (`isSalesforce` / `isCareStack`) make the cast at
  the call site safe. If we ever add a 3rd OAuth provider that lives
  in the broader enum, the cast will need a generic.
- `useApiKeyConnect` calls `POST /integrations/{provider}/api-key`
  which currently exists for CareStack. If we add a non-OAuth provider
  that this endpoint does not support, the API will 404 — surface via
  toast.
- No backend changes shipped in this scope.
- No new env vars required beyond the optional
  `NEXT_PUBLIC_OAUTH_REDIRECT_BASE_URL` (already documented in the
  callback-hint synthesis).

## Blockers

None.

## Do-not-merge conditions

None automatic. Recommended: manual smoke pass before merge.

## Handoff

Handoff: worker/claude-code -> verifier/claude-code for ENG-214.
TASK-A through TASK-H implementation complete. 30/30 vitest tests
pass. TypeScript + ESLint clean. Stale placeholder removed.
Verifier should run independent test pass + a manual smoke walkthrough
in the running Next.js dev server and either accept or write
`Verification failed:` with concrete reproduction steps.
