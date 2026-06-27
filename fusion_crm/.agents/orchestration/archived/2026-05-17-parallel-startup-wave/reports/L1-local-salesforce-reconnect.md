# L1 — Local Salesforce reconnect loop

## Scope

- Fix localhost behavior after Salesforce refresh-token expiry.
- No production mutation.
- No secret or `.env*` edits.

## Findings

1. Local pull failed exactly on the Salesforce refresh path:

```text
SOQL -> 401
refresh token -> 400 invalid_grant: expired access/refresh token
```

2. The expired `salesforce / oauth_token` row stayed `active`, so
   `/integrations` kept reporting Salesforce as connected and the UI kept
   offering pull/sync against a dead refresh token.

3. The localhost Salesforce callback page discarded the real Salesforce
   `code/state` query and called the mock callback. That made local reconnect
   look complete while the FastAPI OAuth callback never persisted a fresh
   token.

## Changes

- `apps/web/app/(staff)/integrations/salesforce/callback/page.tsx`
  forwards the browser to `/api/integrations/salesforce/callback` with the
  original query string, preserving PKCE cookies and real `code/state`.
- `packages/tenant/credential_service.py` now has `expire_active_for(...)` to
  mark active provider credentials as `expired` without touching payloads.
- `apps/api/routers/integrations.py` catches reconnect-required
  `SfNotConnectedError` from pull/sync/raw lead paths, expires active
  Salesforce OAuth credentials, and returns the standard error envelope.
- `packages/integrations/salesforce/client.py` tags no-refresh-token and
  post-refresh-401 failures with `details.action = reconnect`.
- `apps/web/lib/api/hooks/useSfLeads.ts` invalidates the integrations query
  on pull errors so the card refreshes after backend expiry.
- `apps/web/components/integrations/SfLeadsPanel.tsx` disables manual pull
  while Salesforce is not connected.
- `apps/web/lib/msw/init.tsx` unregisters the old MSW service worker when
  `NEXT_PUBLIC_API_MOCKING=disabled`, preventing stale browser mocks from
  reporting a fake connected state.

## Verification

- `.venv/bin/ruff check apps/api/routers/integrations.py packages/integrations/salesforce/client.py packages/tenant/credential_service.py tests/api/test_integrations_salesforce.py tests/tenant/test_credential_service.py`
- `.venv/bin/python -m pytest tests/api/test_integrations_salesforce.py tests/tenant/test_credential_service.py tests/integrations/test_sf_client.py -q`
  - `49 passed`
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run typecheck`
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run lint`
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run test`
  - `17 passed`
- `git diff --check`
- Restarted `apps/web` dev server on `http://localhost:3000` so it loads
  current `.env.local` (`NEXT_PUBLIC_API_MOCKING=disabled`,
  `NEXT_PUBLIC_USE_REAL_SF=true`).
- Local API:
  - `POST /integrations/salesforce/pull-recent?limit=5` returns `409 sf_not_connected`.
  - The stale local `salesforce / oauth_token` row is now `expired`.
  - `GET /integrations` returns Salesforce as `disconnected`.
- Local UI screenshot verified the Salesforce card shows `Not connected` with
  a `Connect` button.

## Follow-Up

- Complete the real Salesforce browser consent flow from localhost or prod.
- After consent returns, run `Pull 5 latest Leads` again.
