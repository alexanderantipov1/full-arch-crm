# CLAUDE.md — `packages/integrations/carestack`

CareStack provider plumbing — password-grant token issuer + read-only
REST client. Read `packages/integrations/CLAUDE.md` first for the
cross-cutting rules (auth class hierarchy, audit on every OAuth
state change, no PHI imports). This file documents the CareStack-
specific surface only.

## Phase 1 scope

ENG-124 (sync CareStack locations into `tenant.location`). Today this
package exposes only what that slice needs:

- `CareStackClient` — async REST client, ROPC password grant + 401
  re-issue retry; convenience `list_locations()` for the
  `/api/v1.0/locations` endpoint.
- `CareStackTokens` — frozen dataclass with `access_token`,
  `token_type`, `expires_at`, `account_id`.
- `CareStackNotConnectedError` / `CareStackApiError` — typed
  exceptions.

The `BaseProviderClient` Protocol from `packages/integrations/base.py`
is NOT implemented yet — the unified resource verbs (`list`, `get`,
`create`, …) land when sync-2 needs them.

## Credential storage carve-out

ENG-124 reads credentials from environment variables. ENG-125 will
move them to `tenant.integration_credential` (encrypted-by-convention
via `packages.integrations.crypto.encrypt_str`). The factory
`CareStackClient.from_env()` is the only place that touches env;
swapping it for a `from_credential(cred)` factory in ENG-125 leaves
the rest of the package unchanged.

Required env vars (all required for `from_env`):

- `CARESTACK_IDP_BASE_URL` — token endpoint host (e.g.
  `https://identity.carestack.com`)
- `CARESTACK_API_BASE_URL` — REST host (e.g.
  `https://api.carestack.com`)
- `CARESTACK_CLIENT_ID` / `CARESTACK_CLIENT_SECRET`
- `CARESTACK_VENDOR_KEY` / `CARESTACK_ACCOUNT_KEY`
- `CARESTACK_ACCOUNT_ID`

## Auth flow

Mirrors `apps/web/lib/cs/auth.ts`:

1. POST `application/x-www-form-urlencoded` to
   `{idp_base}/connect/token` with:
   - `grant_type=password`
   - `client_id`, `client_secret`
   - `username = vendor_key`, `password = account_key`
   - `scope = ""`
2. Cache the response in-memory until ~30 s before `expires_in`.
3. On 401 from any API call, drop the cached token and re-issue
   once. A second 401 after re-issue raises
   `CareStackNotConnectedError`.

CareStack does NOT issue refresh tokens — when the access token
expires we run the password grant again with the same credentials.

## Request headers

Every API call sends:

- `Authorization: Bearer <access_token>`
- `VendorKey: <vendor_key>`
- `AccountKey: <account_key>`
- `AccountId: <account_id>`
- `Accept: application/json`

## Endpoints used today

- `GET /api/v1.0/locations` — full list of locations for the account.
  See `docs/integrations/carestack/resources/locations.md` for the
  field shape.
- `GET /api/v1.0/sync/patients` — modified-after patient feed.
- `GET /api/v1.0/sync/appointments` — modified-after appointment feed.
- `GET /api/v1.0/sync/treatment-procedures` — modified-after procedure feed.
- `GET /api/v1.0/sync/invoices` — modified-after invoice feed.
- `GET /api/v1.0/sync/accounting-transactions` — modified-after billing
  ledger feed (partial payments, adjustments, refunds, reversals). The
  spec's `billing/`-prefixed next-page URL is the same endpoint; we
  always issue against the canonical path with `continueToken` as a
  query parameter. See `docs/integrations/carestack/sync/accounting-transactions.md`.
- `GET /api/v1.0/billing/payment-summary/{patientId}` — per-patient
  balances snapshot (no bulk feed). See
  `docs/integrations/carestack/resources/payment-summary.md`.
- `GET /api/v1.0/patients/{patientId}` — full Patient record (inspector use).
- `GET /api/v1.0/patients/{patientId}/treatment-plans` — per-patient treatment
  plans (no bulk feed). Normalised to a list of plan dicts. Drives the
  TreatmentPlan ingest / `treatment_accepted` capture (ENG-511). See
  `docs/integrations/carestack/resources/treatment-plans.md`.
- `GET /api/v1.0/appointments/{appointmentId}` — full Appointment record.
- `GET /api/v1.0/procedure-codes/{id}` — one procedure-code entry by id
  (`get_procedure_code`). ENG-538: the PRIMARY procedure-code catalog
  source — the flat `GET /api/v1.0/procedure-codes` LIST endpoint is broken
  on the real account (returns junk "Other" codes only), so the catalog is
  built by resolving each needed id individually. Read-only; no PHI.

Add a row to this list whenever the client grows a new helper.

## Tests

`tests/integrations/carestack/test_client.py` covers:

- 200 happy path → JSON body returned
- 401 → re-grant succeeds → retry → 200
- 401 → re-grant fails → `CareStackNotConnectedError`
- 5xx → `CareStackApiError`
- token endpoint 4xx → `CareStackNotConnectedError`
- token response missing `access_token` → `CareStackNotConnectedError`

External calls are stubbed with `respx`; no real CareStack traffic.

## Out of scope (later slices)

- DB-backed credential storage (`tenant.integration_credential`) —
  ENG-125.
- Sync APIs polling (`/api/v1.0/sync/*`) — ENG-127+.
- `BaseProviderClient` Protocol implementation — when sync-2 lands.
- Write endpoints (POST/PUT/DELETE) — guard-rail per
  `feedback_production_readonly_pull`. NOT in Phase 1.
