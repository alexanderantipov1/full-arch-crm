# CLAUDE.md — `packages/integrations/salesforce`

Salesforce provider plumbing — SOQL client + OAuth token refresh.

Read `packages/integrations/CLAUDE.md` first for the cross-cutting rules
(`base.py` auth hierarchy, audit row on every OAuth state change, no PHI
imports, etc.). This file documents the Salesforce-specific surface only.

## Current scope

The slim ENG-100 slice 1 (manual SF Lead pull button) has grown into the
runtime Salesforce OAuth surface for the staff UI. Today this package exposes:

- `SfClient` — async REST client, `soql(query)` + auto-refresh on 401
- `SfTokens` — frozen dataclass holding access/refresh tokens + instance_url
- `SfClient.from_credential()` — DB-backed runtime constructor
- `read_dev_tokens()` / `SfClient.from_dev_file()` — legacy local helper only
- `SfNotConnectedError` / `SfApiError` — typed exceptions

The full `BaseAuth` + `BaseProviderClient` integration (per ENG-87 / FUS-22)
lands when slice 2 (cron polling) needs `IntegrationsService.open_sync_run`
+ the full provider sync ledger.

## Runtime token storage

Runtime API paths MUST read Salesforce OAuth tokens from
`tenant.integration_credential` under:

- `provider_kind = "salesforce"`
- `credential_kind = "oauth_token"`

The companion `salesforce / api_key` row supplies `client_id`,
`client_secret`, `domain`, and `callback_url`. OAuth connect writes the
`oauth_token` row. `SfClient` refresh writes the rotated access token back to
the same DB-backed credential row through its `on_refresh` callback.

`apps/web/.sf-tokens.json` is legacy local bootstrap/migration tooling only.
FastAPI runtime dependencies and routes MUST NOT fall back to it. A file
fallback can make the UI report "connected" from stale local state while raw
Lead / pull requests use DB credentials, which creates an operator-visible
reconnect loop.

## OAuth refresh flow

On 401 from a SOQL call, `SfClient`:

1. POSTs `grant_type=refresh_token` to `<instance_url>/services/oauth2/token`
   with the stored `refresh_token` + client credentials resolved from the
   DB-backed `salesforce / api_key` row, falling back to env only for local
   bootstrap/dev.
2. Persists the new `access_token` (preserving the existing
   `refresh_token` and `instance_url`) back to the DB credential row.
3. Retries the original SOQL request **once**.
4. If the retry is still 401 → `SfNotConnectedError`. The API translates
   that to HTTP 409 so the operator UI prompts a reconnect.

OAuth connect uses `prompt=consent` so Salesforce re-issues a refresh token on
reconnect. If Salesforce still returns no `refresh_token`, fail the callback
loudly and ask the operator to fix the Connected App OAuth scopes / refresh
token policy before reconnecting.

A 4xx (other than 401) or 5xx surfaces as `SfApiError` (HTTP 502).

## SOQL API version

`API_VERSION = "v60.0"` — Winter '24 GA. Bump only when a feature requires
it; document the reason in this file.

## Tests

`tests/integrations/test_sf_client.py` covers:

- 200 happy path → records parsed
- 401 → refresh succeeds → retry → 200
- 401 → refresh fails → `SfNotConnectedError`
- 401 with no refresh_token → `SfNotConnectedError`
- 5xx → `SfApiError`
- DB credential payload missing required fields → `SfNotConnectedError`
- legacy dev token file missing / malformed / incomplete → `SfNotConnectedError`

`tests/api/test_integrations_salesforce.py` covers the FastAPI runtime
dependency contract: missing DB OAuth tokens must surface as `sf_not_connected`
and must not fall back to the legacy dev token file.

External calls are stubbed with `respx`; no real Salesforce traffic. The
real-SF smoke test lives in ENG-105 (slice-1 smoke) and is run by hand.

## Out of scope (slice 2+)

- Salesforce CDC streaming (CometD over `/data/LeadChangeEvent`) — slice 3.
- Outbound Message receiver — later.
- Bulk API 2.0 — only when SOQL volume exceeds 100k/run.
