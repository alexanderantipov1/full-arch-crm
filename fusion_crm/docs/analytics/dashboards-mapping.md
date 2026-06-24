# Analytics Dashboards — Discovery & Data Mapping (ENG-469)

> Discovery + data-mapping doc for the analytics-dashboards epic (ENG-468).
> Maps every dashboard metric from the legacy Replit `DataBase_Fusion`
> project to **our** source-of-truth tables, and flags what we cannot yet
> compute so dashboards render `—` (em dash) instead of fabricating zeros.
>
> Scope: this is a discovery doc only. No code changes. The implementing
> tickets are ENG-470 (marketing), ENG-471 (seo), ENG-472 (full-funnel),
> ENG-473 (sales), ENG-474 (calls).

---

## 1. Overview & dashboard inventory

The Replit app ships ~12 dashboards. We are NOT rebuilding all of them.
The triage below is what this epic covers.

| Replit page | Rebuild? | Ticket | Notes |
|---|---|---|---|
| `marketing-dashboard.tsx` | **Build now** | ENG-470 | Spend / clicks / leads / impressions + UTM attribution. We ingest the data. |
| `seo-dashboard.tsx` | **Build now (subset)** | ENG-471 | GSC + GA4 tiles only. Semrush / Clarity / PageSpeed / crawler are NOT ingested. |
| `full-funnel-report.tsx` | **Build now** | ENG-472 | Channel → consult → surgery → revenue funnel. Reuse our lead-source tree. |
| `sales-dashboard.tsx` | **Build now** | ENG-473 | Pipeline, consultations, TC leaderboard, collected revenue. |
| `call-center-dashboard.tsx` | **Partial** | ENG-474 | Only what `interaction.event` call kinds give us. No RingCentral/CallRail ingest yet. |
| `master-dashboard.tsx` / `executive-dashboard.tsx` | Out of scope | — | Roll-up of the above; revisit after the 5 land. |
| `daily-operations.tsx` | Out of scope | — | Center-bucketed ops feed; partly covered by full-funnel. |
| `ai-call-center-dashboard.tsx`, `management-tv.tsx`, `callcenter-tv.tsx` | Out of scope | — | TV walls / AI call center (Sofia). Not this epic. |
| Excel report (`excel-report.ts`) | Out of scope | — | Export, not a dashboard. |

**Single most important risk (read this first):** the legacy
`classifyLeadSource()` produces five channels — **Google / Meta / Dima /
Implant Engine / Other** — plus center bucketing (Roseville / EDH /
Galleria) and TC→center→per-arch-price logic. **Our shipped attribution
resolver only produces `facebook` / `google` / passthrough** (see §2 and
§6). The Full Funnel and Marketing dashboards CANNOT reproduce the
Replit channel/center breakdown as-is. We either (a) extend the resolver,
or (b) render only the two channels we can classify and mark the rest
`Other`. This is a real product gap, not a wiring detail. Detail in §6.

---

## 2. Our source-of-truth schema (verified)

All names below were read from the actual models on branch
`eng-468-analytics-dashboards`.

### `marketing` schema — `packages/marketing/models.py`
- **`ad_campaign`** (`AdCampaign`): `id`, `tenant_id`, `provider`,
  `external_id`, `name`, `status`, `objective`, `account_id`,
  `raw_event_id`, `extra` (JSONB), `created_at`, `updated_at`.
- **`ad_metric_daily`** (`AdMetricDaily`): `id`, `tenant_id`, `provider`,
  `campaign_external_id`, `metric_date` (Date), `spend` (Numeric 14,2),
  `impressions` (BigInt), `clicks` (BigInt), `conversions` (Numeric 14,2),
  `currency`, `raw_event_id`, `extra`.
- **`gsc_query_daily`** (`GscQueryDaily`): `id`, `tenant_id`, `site_url`,
  `metric_date`, `query`, `query_hash`, `clicks`, `impressions`,
  `ctr` (Numeric 8,6), `position` (Numeric 8,2), `raw_event_id`, `extra`.
- **`ga_metric_daily`** (`GaMetricDaily`): `id`, `tenant_id`,
  `property_id`, `metric_date`, `sessions`, `total_users`, `new_users`,
  `screen_page_views`, `conversions`, `raw_event_id`, `extra`.

Service surface (`packages/marketing/service.py`):
`ad_spend_totals(tenant_id, *, start_date, end_date, provider=None)
→ AdSpendTotalsOut(spend, impressions, clicks, conversions, rows[])`.
Each row: `provider, campaign_external_id, campaign_name?, spend,
impressions, clicks, conversions`. Plus upsert methods for each table.
Repository exposes `aggregate_spend(...)` (group by provider/campaign).
**There is no read method for GSC or GA aggregation yet** — only upserts
and single-row lookups exist; ENG-471 must add aggregation reads.

### `ops` schema — `packages/ops/models.py`
- **`lead`** (`Lead`): `id`, `tenant_id`, `person_uid`, `source`,
  `status` (enum `new|qualified|contacted|booked|lost`), `notes`,
  `extra` (JSONB). **All UTM / gclid / fbclid / lead_source / owner
  attribution lives in `lead.extra`** (ENG-382). Keys observed:
  `lead_source`, `hubspot_lead_source`, `utm_source`, `utm_medium`,
  `utm_campaign`, `utm_content`, `utm_term`, `gclid`, `fbclid`,
  `landing_page`, plus SF `CreatedBy.Name` mirror.
- **`opportunity`** (`Opportunity`): `id`, `tenant_id`, `person_uid`,
  `source_provider`, `external_id`, `name`, `stage` (String, free-form),
  `amount` (Numeric 14,2), `close_date` (tz), `provider_created_at`,
  `raw_event_id`, `extra` (JSONB). **Owner is NOT a column — it lives in
  `opportunity.extra`**: `owner_id`, `owner_name`, `opportunity_stage`,
  `opportunity_type`, `lead_source`, `is_closed`, `is_won`, `probability`.
- **`consultation`** (`Consultation`): `id`, `tenant_id`, `person_uid`,
  `source_provider`, `external_id`, `scheduled_at` (tz, NOT NULL — the
  booking time), `duration_minutes`, `status`
  (enum `scheduled|completed|cancelled|rescheduled|no_show` — **this is
  the show/no-show signal; there is no separate `showed` column**),
  `consultation_kind`, `location_id`, `provider_clinician_name`,
  `provider_created_at`, `raw_event_id`, `covering_opportunity_id`
  (FK → `ops.opportunity.id`, used for carryover).
- **`account`**, **`followup_task`**, **`person_location_profile`** —
  follow-up counts (call/text/email) and location relationship.

### `interaction` schema — `packages/interaction/models.py`
- **`event`** (`Event`): `id`, `tenant_id`, `person_uid`, `kind`
  (String 48), `source_provider`, `source_external_id`, `data_class`,
  `source_kind`, `occurred_at` (tz — when it happened),
  `summary` (PHI-free), `payload` (JSONB, PHI-free), `created_at`.
- Relevant `kind` values: `call_logged`, `call_reference_found`,
  `consultation_scheduled|completed|cancelled|no_show`,
  `opportunity_created|won|lost|stage_changed`, and the **payment**
  kinds: `payment_recorded`, `payment_applied`, `payment_refunded`,
  `payment_reversed`.
- **Payment dollar amount lives in `event.payload["amount"]`** (decimal
  string), date in `event.occurred_at`. Collected revenue =
  Σ`payment_recorded.amount` − Σ`payment_refunded` − Σ`payment_reversed`
  (exclude `payment_applied` allocation legs). Read it via
  `InteractionService.get_treatment_payment_aggregate()` /
  `list_payment_events_for_dashboard()` — **do not query `payload` JSON
  from a dashboard router directly; go through the service.**

### Existing dashboard router — `apps/api/routers/dashboard.py`
Prefix `/dashboard`. Existing endpoints: `/dashboard/summary`,
`/dashboard/pm`, `/dashboard/pm/lead-sources`, `/dashboard/pm/leads`,
`/dashboard/pm/payments`, `/dashboard/pm/payments/groups`,
`/dashboard/pm/payments/summary`. Each is a thin composer over domain
services (no business logic in the route).

---

## 3. Per-dashboard mapping

Status legend: **OK** = computable now from listed source ·
**PARTIAL** = computable but degraded / needs new read method ·
**BLOCKED** = source not ingested, render `—`.

### 3.1 Marketing dashboard — ENG-470

| Replit metric | Our source | Computation recipe | Status |
|---|---|---|---|
| Total Spend | `marketing.ad_metric_daily.spend` | `ad_spend_totals(start,end).spend` | **OK** |
| Total Clicks | `ad_metric_daily.clicks` | `ad_spend_totals(...).clicks` | **OK** |
| Total Leads | `ops.lead` (count in window) | count `lead` where created in window; needs new ops read | **OK** |
| Impressions | `ad_metric_daily.impressions` | `ad_spend_totals(...).impressions` | **OK** |
| CPL (cost/lead) | spend ÷ leads | spend / lead count | **OK** |
| CTR | clicks ÷ impressions | derived | **OK** |
| Daily spend by provider (google/meta) | `ad_metric_daily` grouped by `provider`, `metric_date` | new repo group-by; providers present = whatever was ingested (Google Ads + Meta done; TikTok pending tokens) | **OK** (only ingested providers) |
| Leads over time (total/meta/google/direct) | `ops.lead.extra` UTM | bucket leads by resolved channel per day | **PARTIAL** — only google/facebook classify; Dima/IE collapse to `Other` (see §6) |
| Campaign performance table | `ad_metric_daily` joined `ad_campaign.name` | `ad_spend_totals(...).rows` | **OK** |
| Lead attribution by source/medium/campaign/location | `ops.lead.extra` (`utm_*`) | reuse `OpsService.get_lead_source_tree()` / `get_lead_source_counts()` | **OK** (raw UTM strings) |
| Attribution by Search Term / Ad Group / Creative | `ops.lead.extra` (`utm_term`, `utm_content`) + ad-group/creative | `utm_term`/`utm_content` exist; ad-group/creative dimension **verify** in `extra` — likely absent | **PARTIAL** |

### 3.2 SEO dashboard — ENG-471

| Replit metric | Our source | Computation recipe | Status |
|---|---|---|---|
| GSC total clicks / impressions | `marketing.gsc_query_daily.clicks/impressions` | SUM over window; needs new aggregation read | **OK** |
| GSC avg CTR | `gsc_query_daily.ctr` | impression-weighted avg (or SUM(clicks)/SUM(impressions)) | **OK** |
| GSC avg position | `gsc_query_daily.position` | impression-weighted avg | **OK** |
| GSC unique queries | `gsc_query_daily.query_hash` | COUNT DISTINCT in window | **OK** |
| GSC change vs prior period | same table, two windows | compute both windows, delta | **OK** |
| Top queries / top pages tables | `gsc_query_daily` (query). **Page-level**: `extra` only — `page` is NOT a top-level column | top queries OK; **top pages PARTIAL** (page in `extra`, verify) | **PARTIAL** |
| GA4 sessions / users / pageviews | `marketing.ga_metric_daily.sessions/total_users/screen_page_views` | SUM over window | **OK** |
| GA4 new users | `ga_metric_daily.new_users` | SUM | **OK** |
| GA4 conversions | `ga_metric_daily.conversions` | SUM | **OK** |
| GA4 bounce rate / engagement rate | — | **NOT ingested** (no column; check `extra`) | **BLOCKED / verify** |
| GA4 avg session duration / pages-per-session | — | not stored as columns | **BLOCKED / verify** |
| GA4 top pages | — | not stored (GA we keep property-day rollup, not page rows) | **BLOCKED** |
| Semrush: health score, tracked keywords, keyword rankings, gaps, site audit issues | — | **Semrush not ingested at all** | **BLOCKED** |
| PageSpeed: perf/a11y/SEO scores, Core Web Vitals (FCP/LCP/TBT/CLS/SI/TTI) | — | **PageSpeed not ingested** | **BLOCKED** |
| Clarity: dead/rage clicks, scroll depth, device/browser/country breakdowns | — | **Clarity not ingested** | **BLOCKED** |
| Site crawler results / issues | — | **crawler not ported** | **BLOCKED** |

ENG-471 ships GSC + GA4 tiles only. Everything else renders `—` with a
"source not connected" note.

### 3.3 Full Funnel report — ENG-472

The legacy report bins by **channel** and **center** per month, with TC
attribution and revenue. Our `OpsService.get_lead_source_tree()` already
computes, per channel→source→medium→campaign node: `leads`,
`consults_scheduled`, `consults_attended`, `collected_amount`. **Reuse it.**

| Replit metric | Our source | Computation recipe | Status |
|---|---|---|---|
| Funnel stages (Consult Completed → Surgery Sched → Surgery Done → Finals Sched → Finals Done → Closed Won/Lost) | `ops.opportunity.stage` + `extra.opportunity_stage` | count opportunities per stage string; **stage strings are free-form** — verify the actual distinct values in prod before hardcoding the ladder | **PARTIAL** |
| Leads → Consults scheduled → attended → Collected, by channel | `OpsService.get_lead_source_tree()` | reuse directly | **OK** (channels limited, §6) |
| Channel classification (Google/Meta/Dima/Implant Engine/Other) | `_channel_of_source()` (resolver) | **only google/facebook today** | **PARTIAL → BLOCKED for Dima/IE** (§6) |
| Center bucketing (Roseville / EDH / Galleria) | `consultation.location_id`; legacy used `utm_location` + campaign-name regex + TC→center map | we have `location_id` on consultation but **no TC→center map and `utm_location` is not a parsed field** | **PARTIAL — verify location_id coverage** |
| TC attribution (Owner.Name → TC → center, per-arch price) | `opportunity.extra.owner_name` | owner_name present; **TC→center map + per-arch price tables are app config, not in DB** (legacy hardcoded: Marina Godin/Makala Colburn $15k, Yelena Myalik/Olga Kolomyza $9k) | **PARTIAL** (needs a config table/const port) |
| Carryover (closed-in-month, consult outside month) | `opportunity.close_date` + `consultation.scheduled_at` via `consultation.covering_opportunity_id` | join consultation→covering opportunity; closed in month AND consult `scheduled_at` outside month | **OK** (structurally supported) |
| Retainer configs (Dima $12k, Implant Engine $14.5k) | — | legacy hardcoded constants | **PARTIAL** (port as config, not data) |
| Revenue per channel/month | `interaction.event` payment kinds | `get_treatment_payment_aggregate()` per person, attribute via lead channel | **OK** |

### 3.4 Sales dashboard — ENG-473

| Replit metric | Our source | Computation recipe | Status |
|---|---|---|---|
| Pipeline value | `ops.opportunity.amount` where not closed | SUM amount where `extra.is_closed` false | **OK** |
| Active opps count | `ops.opportunity` | COUNT where not closed | **OK** |
| Avg close rate | `opportunity.extra.is_won/is_closed` | won / closed | **OK** |
| Won revenue | `opportunity.amount` where `is_won` | SUM | **OK** |
| Total paid / collected | `interaction.event` payment kinds | `get_treatment_payment_aggregate()` | **OK** |
| Pipeline stages (6 buckets) | `opportunity.stage` | group by stage; **verify distinct stage strings** | **PARTIAL** |
| Consultations table (patient, TC, stage, value, paid, balance, close date) | `ops.consultation` + `opportunity` + payments + `identity.person` | join; patient name from identity (PHI ok per dev-phase policy) | **OK** |
| TC leaderboard (opps, won, lost, close rate, value, revenue, paid) | `opportunity.extra.owner_name` | group by owner_name | **OK** |
| Patient breakdown (follow-up calls/texts/emails, touches, last touch) | `ops.followup_task` + `interaction.event` | count by kind per person | **PARTIAL** — call/text/email split depends on event kinds present; **verify** SMS/email event kinds are ingested |

Note: legacy `stage` vs `sfStage` distinction — we keep raw `stage` plus
`extra.opportunity_stage`. Pick one canonical, expose the raw as detail.

### 3.5 Call center dashboard — ENG-474 (PARTIAL)

We do **not** ingest RingCentral or CallRail. The only call signal is
`interaction.event` kinds `call_logged` / `call_reference_found`, whose
PHI-free `payload` carries limited fields.

| Replit metric | Our source | Computation recipe | Status |
|---|---|---|---|
| Total calls | `interaction.event` kind `call_logged` | COUNT in window | **PARTIAL** — only as many as W1 logs; not a true telephony feed |
| Avg call duration | `event.payload` duration | **verify** payload carries `duration` | **BLOCKED / verify** |
| Booking rate (consults booked / calls) | calls vs `consultation_scheduled` | ratio | **PARTIAL** |
| Avg QA score | — | **no transcription/scoring pipeline ingested** | **BLOCKED** |
| Agent performance (connected/voicemail/missed, score) | — | RingCentral/CallRail not ingested | **BLOCKED** |
| Recent calls + recording player + transcript + sentiment | `call_reference_found` (reference URL only) | reference may exist; recordings/transcripts/sentiment not stored | **BLOCKED** |
| Backfill/transcription stats | — | no transcription pipeline | **BLOCKED** |

ENG-474 should ship a minimal "call volume + booking rate from logged
events" tile and clearly mark the agent/QA/recording sections as
"telephony not connected".

---

## 4. Cannot compute yet (blocked — render `—`, never fake zeros)

Every metric below has **no ingested source**. Dashboards must show an
em dash + a short "source not connected" affordance, not `0`.

- **Telephony (RingCentral / CallRail):** call duration, connected /
  voicemail / missed counts, per-agent performance, recordings,
  transcripts, sentiment, QA scores, backfill stats. (Comms ingest is
  the unbuilt "Phase 3".)
- **Semrush:** keyword rankings, position changes, search volume,
  difficulty, keyword gaps, site-audit health score, errors/warnings.
- **Microsoft Clarity:** dead clicks, rage clicks, scroll depth, quick
  backs, device/browser/country breakdowns.
- **PageSpeed / Lighthouse:** performance / accessibility / best-practices
  / SEO scores, Core Web Vitals (FCP, LCP, TBT, CLS, SI, TTI),
  optimization opportunities.
- **Site crawler:** crawled URLs, status codes, on-page issues, diffs.
- **GA4 engagement fields:** bounce rate, engagement rate, avg session
  duration, pages-per-session, GA4 top-pages — our `ga_metric_daily`
  rollup keeps sessions/users/pageviews/new_users/conversions only
  (verify nothing extra hides in `extra`).
- **Backlinks / competitor intel / organic social:** legacy pages exist;
  no source ingested.

Channel-classification gap (Dima / Implant Engine / center / TC pricing)
is tracked separately in §6 — it is degraded, not fully blocked.

---

## 5. Recommendations for the build

**(a) Endpoint prefix — extend `/dashboard` with an `/analytics`
sub-tree.** Add the new reads under
`apps/api/routers/dashboard.py` (or a sibling router mounted at the
same prefix) as `/dashboard/analytics/marketing`,
`/dashboard/analytics/seo`, `/dashboard/analytics/full-funnel`,
`/dashboard/analytics/sales`, `/dashboard/analytics/calls`. Rationale:
these are staff dashboard reads in the same family as the existing
`/dashboard/pm/*` endpoints, the router pattern (thin composer over
services) already fits, and a flat new top-level `/analytics` router
would fragment the dashboard surface. Reserve a standalone `/analytics`
prefix only if/when we expose a non-dashboard semantic-query API.

**(b) Read layer — new `packages/analytics/` package, service-only.**
Do **not** extend `insight` (that package is the semantic-catalog
proposal/version store, imports only `core`, and is the wrong shape).
Create `packages/analytics/` as a read-only composition layer:
`AnalyticsService` calls the existing domain services
(`MarketingService`, `OpsService`, `InteractionService`) and assembles
dashboard DTOs. It must NOT touch repositories of other domains or the
DB directly (cross-domain crossings via services only, per
`packages/CLAUDE.md`). This keeps business logic out of routes and
respects the import matrix. New aggregation **reads** that don't yet
exist (GSC/GA window rollups, lead-count-per-day, opportunity stage
counts) should be added to the owning domain's service/repository
(marketing, ops), not reimplemented in `analytics`.

**(c) Full Funnel must reuse `OpsService.get_lead_source_tree()`** for
the channel funnel (it already returns leads → consults_scheduled →
consults_attended → collected_amount per node) and the ENG-446/ENG-394
`_channel_of_source()` resolver for channel labels — **do not re-port
`classifyLeadSource()`**. If richer channels are needed, fix the
resolver (§6) so every dashboard benefits, rather than forking the logic
into the funnel page.

---

## 6. The channel-classification gap (most important caveat)

Legacy `classifyLeadSource()` (in `full-funnel-report.ts`) reads
`utm_campaign` / `utm_source` / `utm_medium` and returns one of:

- **Implant Engine** — campaign contains `implant_engine` / `implant engine` / `the implant machine`
- **Google** — source `google` + medium `cpc|paid_search`, or campaign `google ads|google business|sem_*`, or source `google`
- **Dima** — campaign contains `dima` / `afisha` AND not paid
- **Meta** — source `facebook|instagram` or medium `paid_social`, or campaign `lead gen fusion|lead_gen|…`
- **Other** — billboard / offline / tv / tiktok / unmapped

Our resolver `_channel_of_source()` (`packages/ops/service.py:219`,
SQL mirror in `repository.py`) only matches:

```
("facebook", ("facebook", "fb")),
("google",   ("google", "adwords", "youtube")),
```

and returns the raw label otherwise. So **Dima, Implant Engine, Meta-via-
campaign-name, and the paid-vs-organic split all collapse to passthrough/
Other** in our dashboards today. Also missing entirely on our side:

- **Center bucketing** (Roseville / EDH / Galleria) — legacy uses
  `utm_location` + campaign-name regex + a TC→center map. We have
  `consultation.location_id` but no parsed `utm_location` field and no
  TC→center map.
- **TC→center map and per-arch pricing** — legacy hardcodes
  `Marina Godin/Makala Colburn → $15k`, `Yelena Myalik/Olga Kolomyza →
  $9k`, retainers Dima `$12k` / Implant Engine `$14.5k`, and arch count
  = `amount < price ? 0 : amount < 2*price ? 1 : 2`. None of this exists
  in our schema; `opportunity.extra.owner_name` is the only input we have.

**Decision needed from the orchestrator before ENG-470/472 build:** either
(1) extend `_channel_of_source()` + add a center/TC config table (a real
sub-task, keeps one canonical resolver), or (2) ship the dashboards with
google/facebook/Other channels and no center/TC breakdown, with the gap
documented in the UI. Recommendation: option (1) for Full Funnel parity,
scoped as a small additive ticket so the resolver stays the single source
of channel truth.

---

## 7. Verify-before-build checklist

Items to confirm against **real prod data** before hardcoding (per the
"verify with real data before merge" rule):

- Distinct `ops.opportunity.stage` / `extra.opportunity_stage` strings —
  before building the funnel stage ladder.
- Whether `gsc_query_daily` page-level data lives in `extra` (top-pages).
- Whether `ga_metric_daily.extra` carries bounce/engagement/duration.
- Whether `call_logged` `event.payload` carries `duration` / outcome.
- Which event kinds back the patient follow-up call/text/email split.
- `consultation.location_id` coverage (% non-null) for center bucketing.
- Ad-group / creative dimension presence in `lead.extra` for marketing
  attribution detail tab.
