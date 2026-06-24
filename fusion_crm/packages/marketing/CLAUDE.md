# CLAUDE.md — `packages/marketing`

Ad-spend and campaign metrics from external ad platforms. **Strictly
non-PHI, non-person aggregate data.** Read the root `CLAUDE.md` and
`packages/CLAUDE.md` first.

## Why this schema exists

Person-linked marketing signals (leads, calls, SMS, form fills) belong in
`identity` / `ops` / `interaction`. What does NOT fit there is *aggregate*
marketing data — how much was spent on a campaign on a given day. That is
what `marketing` holds: the curated query projection of ad-platform spend,
so dashboards and the lead↔spend attribution join have a typed home instead
of re-reading `ingest.raw_event` JSON.

Full fidelity still lives in `ingest.raw_event` (ENG-425 / ADR-0005). These
tables are a curated projection, not the forensic copy.

## Tables (schema `marketing`)

- **`ad_campaign`** — one row per platform campaign. Idempotent on
  `(tenant_id, provider, external_id)`.
- **`ad_metric_daily`** — daily spend/impressions/clicks/conversions per
  campaign. Idempotent on `(tenant_id, provider, campaign_external_id,
  metric_date)`. Keyed by the campaign's platform `external_id` string (not a
  FK to `ad_campaign`) so a metric row upserts independently of campaign-row
  ordering within one pull.
- **`ad_set`** (ENG-512) — one row per ad set / ad group. Idempotent on
  `(tenant_id, provider, external_id)`; carries `campaign_external_id`.
- **`ad`** (ENG-512) — one row per ad / creative. Idempotent on
  `(tenant_id, provider, external_id)`; carries `adset_external_id` /
  `campaign_external_id` + the platform `name`. The cost-per-lead allocator
  bridges this row to an `attribution.source_node` (level `ad`) by matching the
  node slug against `external_id` (utm=id) OR a slug of `name` (utm=name).
- **`ad_metric_daily_ad`** (ENG-512) — daily ad-level
  spend/impressions/clicks/conversions. Idempotent on `(tenant_id, provider,
  ad_external_id, metric_date)`; denormalises `adset_external_id` /
  `campaign_external_id` so spend rolls up to the campaign tier without a join.
  The campaign-level `ad_metric_daily` stays the authoritative campaign total.
- **`ga_metric_daily`** — daily GA4 property metrics (sessions / total_users /
  new_users / screen_page_views / conversions). Idempotent on
  `(tenant_id, property_id, metric_date)`. Web-analytics, not ad spend — same
  schema because it is the same kind of aggregate non-PHI marketing data.
- **`gsc_query_daily`** — daily Google Search Console rows (one per site × day
  × search query: clicks / impressions / ctr / position). Idempotent on
  `(tenant_id, site_url, metric_date, query_hash)` — `query_hash` (sha256 of
  the raw query) keys the unique constraint because queries can exceed the
  btree index size limit; the verbatim query is kept in `query` (TEXT).

`provider` is constrained to `AD_PROVIDERS = (google_ads, meta_ads,
tiktok_ads)` by a CHECK constraint (model + migration in lock-step). Adding a
fourth platform → widen the tuple AND every ad-table CHECK constraint
(`ad_campaign`, `ad_metric_daily`, `ad_set`, `ad`, `ad_metric_daily_ad`).

## Lead ↔ spend matching

This package does NOT match leads. Leads already carry `utm_*` / `gclid` /
`fbclid` in `ops.lead.extra` (ENG-382) and the ENG-446 attribution resolver.
Joining spend to leads is a read-time join (`marketing.ad_metric_daily` ↔
`ops.lead` on campaign/utm) done by the analytics layer, not a write here.

## Cross-package imports

Allowed: `tenant`, `audit`, `core`. This package owns aggregate data only; it
does not read `identity` / `ops` / `phi`. The ingest connectors that feed it
live in `packages/ingest/*_campaign_service.py` and call `MarketingService`.

## Service surface

`MarketingService.upsert_campaign(tenant_id, AdCampaignUpsertIn) → UpsertResult`
`MarketingService.upsert_metric_daily(tenant_id, AdMetricDailyUpsertIn) → UpsertResult`
`MarketingService.upsert_ad_set(tenant_id, AdSetUpsertIn) → UpsertResult`  (ENG-512)
`MarketingService.upsert_ad(tenant_id, AdUpsertIn) → UpsertResult`  (ENG-512)
`MarketingService.upsert_ad_metric_daily(tenant_id, AdMetricDailyAdUpsertIn) → UpsertResult`  (ENG-512)
`MarketingService.list_ads / list_campaigns / ad_daily_spend / campaign_daily_spend`  (ENG-512 cost-per-lead reads)
`MarketingService.upsert_ga_metric_daily(tenant_id, GaMetricDailyUpsertIn) → UpsertResult`
`MarketingService.upsert_gsc_query_daily(tenant_id, GscQueryDailyUpsertIn) → UpsertResult`
`MarketingService.ad_spend_totals(tenant_id, start_date, end_date, provider?) → AdSpendTotalsOut`

## Hard rules

- **Read-only against the ad platforms.** We never create/edit campaigns
  (the Replit project's campaign-creation path is intentionally NOT ported).
- Repositories/services never commit — only the boundary commits.
- Never log spend tied to a named campaign as PHI — it is not PHI, but keep
  log fields to provider + counts + `tenant_id`, consistent with the rest of
  the platform.
