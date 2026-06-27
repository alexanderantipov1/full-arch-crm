# CLAUDE.md — `packages/integrations/google_search_console`

Google Search Console provider plumbing — read-only Webmasters API v3 client.
Read `packages/integrations/CLAUDE.md` first for the cross-cutting rules.

## Phase 2 scope

Pull daily organic-search performance (query × date):

- `GoogleSearchConsoleClient.from_env()` — build from `Settings`.
- `list_sites()` — `GET /sites` (verified properties).
- `resolve_site_url()` — returns `GSC_SITE_URL` if set, else auto-discovers the
  best verified property (prefers a `sc-domain:` entry). Raises
  `GoogleSearchConsoleNotConnectedError` when none is verified.
- `get_query_metrics(site_url, start_date, end_date)` —
  `searchAnalytics.query` with dimensions `[date, query]`, paginated via
  `startRow` (`rowLimit` 25000). Returns one dict per (day, query):
  `{date, query, clicks, impressions, ctr, position}`.

## Auth

OAuth refresh-token flow against `https://oauth2.googleapis.com/token`. The GSC
refresh token (`GSC_REFRESH_TOKEN`) is exchanged using the **Google Ads OAuth
client** (`GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET`) — the account
has no separate GSC OAuth client creds (mirrors GA4). 401 → refresh once →
retry, then raise.

DB-backed per-tenant credentials (`tenant.integration_credential`) are the
preferred source as of ENG-490:
`GoogleSearchConsoleClient.from_credential(payload)` validates against
`packages.tenant.schemas.GoogleSearchConsoleCredentialPayload` (self-contained;
optional `site_url`) and builds the same client `from_env()` does. The worker
`pull_gsc_for_tenant` reads the tenant credential first and falls back to
`from_env()` only when no DB row exists.

Required env vars (for the `from_env` fallback): `GSC_REFRESH_TOKEN`,
`GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`. Optional: `GSC_SITE_URL`
(auto-discovered if unset).

## Endpoints used today

- `GET  /webmasters/v3/sites`
- `POST /webmasters/v3/sites/{siteUrl}/searchAnalytics/query`

The `{siteUrl}` path segment is URL-encoded (covers `sc-domain:` and
`https://…/` forms).

## Hard rules

- **Read-only.** `sites.list` + `searchAnalytics.query` only. No sitemaps
  submit / URL-inspection write endpoints.
- Tokens in-memory only — never on disk, never in logs.
- Credentials from env via `Settings`, never raw `os.environ`.
- Numeric coercion + query hashing happen in the ingest mapper
  (`packages/ingest/gsc_query_service.py`).
