# CLAUDE.md — `packages/integrations/google_analytics`

GA4 provider plumbing — read-only Data API client (v1beta). Read
`packages/integrations/CLAUDE.md` first for the cross-cutting rules.

## Phase 2 scope

Pull daily property metrics for the funnel top (traffic → leads):

- `GoogleAnalyticsClient.from_env()` — build from `Settings`.
- `property_id` — the GA4 property (`GA_PROPERTY_ID`).
- `run_report(start_date, end_date, dimensions, metrics, limit=…)` — the
  generic read-only `:runReport` core. Returns one self-describing dict per row
  with **every** requested dimension and metric zipped by its GA4 id (header/
  value arrays). The typed helpers below delegate to it.
- `get_daily_metrics(start_date, end_date)` — `date` dimension + metrics
  `sessions`, `totalUsers`, `newUsers`, `screenPageViews`, `conversions` plus
  the additive engagement metrics `engagedSessions`, `engagementRate`,
  `averageSessionDuration`, `bounceRate`, `eventCount` (ENG-478). One dict/day.
- `get_daily_channel_metrics(...)` — `date × sessionDefaultChannelGroup` (the
  organic / paid / direct split), core five metrics.
- `get_daily_host_metrics(...)` — `date × hostName` (per-site), core metrics.
- `get_daily_landing_page_metrics(...)` — `date × landingPage` (top pages),
  core metrics.

## Auth

OAuth refresh-token flow against `https://oauth2.googleapis.com/token`. The
GA4 refresh token (`GA_REFRESH_TOKEN`) is exchanged using the **Google Ads
OAuth client** (`GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET`) — the
account does not provision separate GA OAuth client creds (mirrors the Replit
fallback). Access token cached in-memory until ~60 s before expiry; 401 →
refresh once → retry, then raise `GoogleAnalyticsNotConnectedError`.

DB-backed per-tenant credentials (`tenant.integration_credential`) are the
preferred source as of ENG-490: `GoogleAnalyticsClient.from_credential(payload)`
validates against `packages.tenant.schemas.GoogleAnalyticsCredentialPayload`
(self-contained — the OAuth client lives inside the payload per provider) and
builds the same client `from_env()` does. The worker `pull_ga4_for_tenant`
reads the tenant credential first and falls back to `from_env()` only when no
DB row exists.

Required env vars (for the `from_env` fallback): `GA_PROPERTY_ID`,
`GA_REFRESH_TOKEN`, `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`.

## Endpoints used today

- `POST /v1beta/properties/{propertyId}:runReport`

## Hard rules

- **Read-only.** Only `:runReport`. No GA Admin / write endpoints.
- Tokens in-memory only — never on disk, never in logs.
- Credentials from env via `Settings`, never raw `os.environ`.
- The client returns verbatim (header-zipped) rows; numeric coercion happens
  in the ingest mapper (`packages/ingest/ga4_metric_service.py`).
