# CLAUDE.md — `packages/integrations/meta_ads`

Meta (Facebook) Ads provider plumbing — read-only Graph API client (v21.0).
Read `packages/integrations/CLAUDE.md` first for the cross-cutting rules.

## Phase 1 scope

Pull campaign metadata + daily spend insights for the lead↔spend join:

- `MetaAdsClient.from_env()` — build from `Settings`.
- `ad_account_ids` — parsed digit-only ids from `META_ADS_AD_ACCOUNT_ID`
  (comma-separated `act=<id>` entries; the account spans several ad accounts).
- `list_campaigns(account_id)` — `act_{id}/campaigns` (id, name, status,
  objective), `paging.next` followed to completion.
- `get_campaign_insights(account_id, start_date, end_date)` —
  `act_{id}/insights` with `level=campaign`, `time_increment=1` (one row per
  campaign per day), verbatim rows.
- `get_ad_insights(account_id, start_date, end_date)` (ENG-512) —
  `act_{id}/insights` with `level=ad`, `time_increment=1` (one row per ad per
  day). Fields `ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,
  spend,impressions,clicks,actions`. Feeds the ad-level cost-per-lead allocator
  via `packages/ingest/meta_ads_ad_service.py`. Verbatim rows.

## Token model (important)

The configured token is a **SYSTEM_USER token that does not expire**
(`debug_token` → `expires_at: 0`, scopes include `ads_read` / `read_insights`).
So the read path needs **no refresh**. For the future case of a 60-day user
token, Meta's keep-alive is `grant_type=fb_exchange_token` (app_id +
app_secret + current token) — exposed as `exchange_long_lived_token()` but NOT
called automatically. This mirrors how the Replit `DataBase_Fusion` project
kept its token alive (`server/meta-ads.ts::refreshToken`).

## Credential storage carve-out

DB-backed per-tenant credentials (`tenant.integration_credential`) are the
preferred source as of ENG-490: `MetaAdsClient.from_credential(payload)`
validates the decrypted payload against
`packages.tenant.schemas.MetaAdsCredentialPayload` and builds the same client
`from_env()` does. The worker `pull_meta_ads_for_tenant` reads the tenant
credential first and only falls back to `from_env()` when no DB row exists.
`from_env()` stays as the transition fallback. Required env vars (for the
fallback):

- `META_ADS_ACCESS_TOKEN` (long-lived / system-user)
- `META_ADS_AD_ACCOUNT_ID` (one or comma-separated `act=<id>` list)
- `META_ADS_APP_ID` / `META_ADS_APP_SECRET` (only for the optional token
  exchange; not needed for reads with a non-expiring token)

## Endpoints used today

- `GET /v21.0/act_{id}/campaigns` — campaign metadata, paginated.
- `GET /v21.0/act_{id}/insights` (`level=campaign`) — daily campaign insights.
- `GET /v21.0/act_{id}/insights` (`level=ad`) — daily ad-level insights (ENG-512).
- `GET /v21.0/oauth/access_token` — optional `fb_exchange_token` keep-alive.

Add a row here whenever the client grows a new helper.

## Hard rules

- **Read-only.** Insights + campaign metadata GETs only. No campaign mutate
  endpoints — the Replit project's create/duplicate path is intentionally NOT
  ported.
- Token is read from env via `Settings`, never raw `os.environ`; never logged.
- `spend` arrives as a string; `actions` is a list of `{action_type, value}` —
  the ingest mapper converts (see `packages/ingest/meta_ads_campaign_service.py`).
