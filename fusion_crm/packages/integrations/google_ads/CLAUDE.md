# CLAUDE.md — `packages/integrations/google_ads`

Google Ads provider plumbing — OAuth-refresh token issuer + read-only REST
client (API v23). Read `packages/integrations/CLAUDE.md` first for the
cross-cutting rules. This file documents the Google-Ads-specific surface.

## Phase 1 scope

Pull campaign + daily spend metrics for the lead↔spend join. The client
exposes only:

- `GoogleAdsClient.from_env()` — build from `Settings`.
- `customer_ids` — parsed digit-only ids from `GOOGLE_ADS_CUSTOMER_ID`
  (comma-separated; the account spans multiple child accounts under one
  manager).
- `search(customer_id, query)` — GAQL `:search` with `nextPageToken`
  pagination; returns verbatim result rows.
- `search_campaign_metrics(customer_id, start_date, end_date)` — the Phase 1
  GAQL query (campaign + cost_micros/impressions/clicks/conversions by day).

## Credential storage carve-out

DB-backed per-tenant credentials (`tenant.integration_credential`) are the
preferred source as of ENG-490: `GoogleAdsClient.from_credential(payload)`
validates the decrypted payload against
`packages.tenant.schemas.GoogleAdsCredentialPayload` and builds the same
client `from_env()` does. The worker `pull_google_ads_for_tenant` reads the
tenant credential first and only falls back to `from_env()` when no DB row
exists. `from_env()` stays as the transition fallback.

Required env vars (all required for the `from_env` fallback):

- `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_CUSTOMER_ID` (one id or comma-separated list)
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (optional — manager account header)

## Auth flow

1. POST `application/x-www-form-urlencoded` to
   `https://oauth2.googleapis.com/token` with `grant_type=refresh_token`,
   `client_id`, `client_secret`, `refresh_token`.
2. Cache the access token in-memory until ~60 s before `expires_in`.
3. On 401 from a `:search` call, drop the cached token and refresh once. A
   second 401 raises `GoogleAdsNotConnectedError`.

## Request headers (`:search`)

- `Authorization: Bearer <access_token>`
- `developer-token: <developer_token>`
- `login-customer-id: <digits>` (only when a manager id is configured)
- `Content-Type: application/json`

## Endpoints used today

- `POST /v23/customers/{customerId}/googleAds:search` — GAQL query, paginated
  via `pageToken` / `nextPageToken`.

Add a row here whenever the client grows a new helper.

## GAQL (Phase 1)

```
SELECT campaign.id, campaign.name, campaign.status,
       campaign.advertising_channel_type,
       metrics.cost_micros, metrics.impressions, metrics.clicks,
       metrics.conversions, segments.date
FROM campaign
WHERE segments.date BETWEEN '<start>' AND '<end>'
```

`metrics.cost_micros / 1_000_000` = spend in the account currency.

## Hard rules

- **Read-only.** Only `:search`. No campaign mutate endpoints — the Replit
  project's campaign-creation path is intentionally NOT ported.
- Tokens are in-memory only — never on disk, never in logs.
- Credentials come from env via `Settings`, never raw `os.environ`.
- The 401 retry path bottoms out (single refresh, then raise).
