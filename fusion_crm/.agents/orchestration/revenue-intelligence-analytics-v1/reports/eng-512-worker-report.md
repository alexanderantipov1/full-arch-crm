# Worker Report — ENG-512 (Phase 1): ad-level Meta ingest + cost-per-lead allocator

- **Task id:** eng-512
- **Linear:** ENG-512 — B1.4 — ad-level `marketing_cost_allocated` (cost-per-lead)
  <https://linear.app/fusion-dental-implants/issue/ENG-512/b14-marketing-cost-allocated-spend-lead-attribution-join>
- **Role / agent:** worker / claude-code (Opus 4.8)
- **Branch / worktree:** `eng-512-eng-512` /
  `…/revenue-intelligence-analytics-v1/worktrees/eng-512` (base `main`)
- **Mission:** revenue-intelligence-analytics-v1 (epic ENG-504)
- **Class:** `contract_change` (new `marketing.*` tables + new Alembic revision)
- **Mode:** build only — **NOT committed/pushed, no PR** (see "Integration status").

`Handoff: worker → orchestrator` — requesting **cross-runtime (Codex) review**.

---

## TL;DR

Built the full ad-level Meta ingest pipeline + the ad-level cost-per-lead
allocator, flipping `analytics.fact_patient_journey.marketing_cost_allocated`
from `unresolved` → `auto`. The pipeline is account-config-only for Phase 2.
**One material `Needs decision:`** — the spend↔attribution join key rests on a
real-data UTM convention I could not verify from code; the implementation is
**fail-safe** (mismatches reduce coverage / surface as "spend without leads",
never mis-allocate), so it ships as `auto` but the match rate must be confirmed
on the real DB before it is trusted on the dashboard (do-not-merge condition #1).

---

## Scope delivered

### 1. Ad-level Meta ingest (full-fidelity → curated projection)
- `MetaAdsClient.get_ad_insights(level=ad)` — fields `ad_id, ad_name, adset_id,
  adset_name, campaign_id, campaign_name, spend, impressions, clicks, actions,
  date_start`, `time_increment=1`.
- New `marketing` tables (additive; campaign tables untouched): `ad_set`, `ad`,
  `ad_metric_daily_ad` (natural key `(tenant_id, provider, ad_external_id,
  metric_date)`, `raw_event_id`, `extra`, denormalised parent ids). UUID PKs,
  provider CHECK, tenant FK — mirrors existing `ad_campaign`/`ad_metric_daily`.
- `MetaAdsAdIngestService` — verbatim capture into `ingest.raw_event`
  (`event_type=meta_ads.ad_metric.upsert`, invariant #11) + schema registry,
  then projects via `MarketingService`. Content-identity dedupe → idempotent.
- New Alembic revision `c5e7a9b1d3f2` chained on head `a1b2c3d4e5f6`
  (adds the 3 tables to the existing `marketing` schema; full downgrade).

### 2. Cost-per-lead allocator (in the fact builder)
- New pure module `packages/analytics/cost_allocation.py` (`allocate(...)`).
  Two-tier, ad first then campaign on the **residual**:
  - **Ad tier:** `ad spend that day ÷ leads attributed to that ad that day`.
  - **Campaign tier (fallback):** a lead with a campaign but no covered ad gets
    `(campaign spend − Σ its ad-level spend) ÷ fallback leads`.
  - **Uncovered → $0.** Precedence per lead: **ad → campaign → $0**.
  - **"Spend without leads"** (ads/campaign residual that produced 0 attributed
    leads) is summed and surfaced — `BuildResult.spend_without_leads` + a
    `fact_patient_journey.cost_allocation` structured log; never hidden,
    never re-allocated.
- `FactPatientJourneyBuilder` wires it (new optional `marketing` param). Field
  flips to `method=auto`, `confidence` = the lead's attribution confidence.
  `marketing_cost_allocated` removed from `_UNRESOLVED_FIELDS`; persons with no
  `lead_date` (can't time-match spend) stay `unresolved` (honest, not fake $0).
- **Manual override preserved** — `marketing_cost_allocated` is already in
  `_MANUAL_PRESERVE_FIELDS`; allocation runs before merge so `manual > auto`
  holds for value and provenance (unit-tested).
- `analytics` stays a rebuildable projection written only by the builder.

### 3. Daily D-1 refresh
- `apps/worker/jobs/marketing_pull.py::pull_meta_ads_ads_for_tenant` — ad-level
  pull, rolling **3-day** window (`_AD_LEVEL_DAYS`) for late-settling spend;
  wired into `pull_marketing_for_all_tenants` with its own ok/skipped/failed
  counters. Registered in `WorkerSettings.functions`.
- Fact refresh job (`fact_patient_journey_refresh.py`) now constructs the
  builder with `MarketingService`, so a rebuild after the ad pull fills the cost
  field. (No new cron — the existing on-demand/rebuild posture is unchanged.)

### Phase 2 is config-only
Ingest iterates `client.ad_account_ids` (env / per-tenant credential). Adding the
Dima accounts `641217851274148` / `490333746617005` is a **credential change,
no code change** — confirmed: no account ids are hardcoded.

---

## The join (read this — it is the one real decision)

`attribution.source_node` (levels `ad`/`campaign`) keys on a **slug = slugify of
the SF lead's UTM text** (`utm_content`/`utm_creative` → ad, `utm_campaign` →
campaign). The `marketing` spend tables key on **Meta numeric ids** + carry the
Meta **name**. There is **no existing column linking the two**, so this task had
to define the bridge.

**Implemented bridge (fail-safe hybrid):** for each marketing ad/campaign,
register its raw `external_id`, `slugify(external_id)`, and `slugify(name)` →
external id; resolve each lead's attribution slug against that index. This
covers both real conventions:
- `utm_content = {{ad.id}}` (utm=id) → slug is the numeric id → matches
  `external_id`.
- `utm_content = ad name` (utm=name) → matches `slugify(name)`.

**Why this is safe to ship as `auto`:** a non-match never mis-allocates — a lead
whose ad slug matches nothing falls back ad→campaign→$0, and an ad whose name/id
matches no lead becomes "spend without leads" (surfaced). Mismatches reduce
**coverage**, which is visible, rather than producing wrong cost numbers.

`Needs decision:` **The real-data match rate is unverified.** I could not reach
the dev/real DB from this sandbox (DB + Python execution are gated here), so I
could not confirm whether the in-house FB accounts' SF leads actually carry
`utm_content`/`utm_campaign` that slug-match the Meta ad/campaign names or ids.
If the real UTM convention is neither (e.g. UTMs absent on Meta lead-gen forms),
coverage will be low and most leads fall to campaign-tier or $0 — **honest, but
the dashboard would show little ad-level cost**. Recommended verification before
trusting the field on the dashboard: on the real DB, compare
`attribution.source_node(level in (ad,campaign)).slug` against
`slugify(marketing.ad.name)` / `marketing.ad.external_id` and report the match %.

---

## Touched files

**New**
- `packages/analytics/cost_allocation.py` — pure allocator
- `packages/ingest/meta_ads_ad_service.py` — ad-level ingest
- `packages/db/alembic/versions/20260619_1000_c5e7a9b1d3f2_add_marketing_ad_level.py`
- `tests/analytics/test_cost_allocation.py`
- `tests/ingest/test_meta_ads_ad_service.py`
- `tests/integration/test_meta_ads_ad_ingest.py`

**Modified**
- `packages/integrations/meta_ads/client.py` — `get_ad_insights`
- `packages/marketing/models.py` — `AdSet`, `Ad`, `AdMetricDailyAd`
- `packages/marketing/schemas.py` — upsert + allocator-read DTOs
- `packages/marketing/repository.py` — CRUD + `ad_daily_spend`/`campaign_daily_spend`/`list_ads`/`list_campaigns`
- `packages/marketing/service.py` — `upsert_ad_set`/`upsert_ad`/`upsert_ad_metric_daily` + allocator reads
- `packages/attribution/repository.py` + `service.py` — `analytics_alloc_attribution_by_person`
- `packages/analytics/fact_builder.py` — allocation pass + `marketing` dep + `BuildResult.spend_without_leads`
- `apps/worker/jobs/marketing_pull.py` — `pull_meta_ads_ads_for_tenant` + loop wiring
- `apps/worker/jobs/fact_patient_journey_refresh.py` — wire `MarketingService`
- `apps/worker/main.py` — register the new job
- `tests/analytics/test_fact_builder.py` — cost-allocation builder tests
- CLAUDE.md: `packages/marketing`, `packages/integrations/meta_ads`, `packages/ingest`

**Untracked temp to delete:** `.find_head.py` (a throwaway alembic-head finder;
`rm` is blocked in this sandbox — please delete before commit / it is untracked
so it won't land unless `git add -A`).

---

## Tests & verification

| Check | Status | Notes |
|---|---|---|
| `ruff check` (all touched packages + tests + migration) | ✅ pass | run in-session |
| Unit: allocator (reconciliation, zero-lead, fallback, day isolation, uncovered) | ⏳ **not executed here** | `tests/analytics/test_cost_allocation.py` — Python exec gated in sandbox |
| Unit: builder auto-flip + manual-preserve + unresolved-without-marketing | ⏳ not executed | `tests/analytics/test_fact_builder.py` (existing tests preserved: no-marketing path keeps `unresolved`) |
| Unit: ad ingest (capture/project, idempotent, skip, missing adset, account isolation) | ⏳ not executed | `tests/ingest/test_meta_ads_ad_service.py` |
| Integration: ad-level ingest upsert idempotency (real Postgres) | ⏳ not executed | `tests/integration/test_meta_ads_ad_ingest.py` |
| `alembic upgrade head` + `alembic check` + downgrade | ⏳ not executed | needs DB |
| No new `phi` import | ✅ | nothing added imports `phi`; analytics/marketing/ingest unchanged on that axis |

**Important:** DB access and Python/pytest execution are **gated in this worker
sandbox** (only `ruff` ran). The pytest suite, `alembic upgrade/check/downgrade`,
and the integration test **must be run in CI / an environment with the test
Postgres** before merge. ruff passing confirms syntax, imports, and name
resolution across every changed file; the logic was traced by hand.

---

## Risks
1. **Join match rate unverified** (see `Needs decision:` above) — primary risk.
2. **Campaign-residual reconciliation** assumes campaign-level spend ≥ Σ its
   ad-level spend (the normal Meta case: campaign insight = Σ ad insights). If a
   tenant's campaign total is *less* than captured ad spend, residual clamps to
   0 (no negative allocation) — safe, but campaign-tier leads then get $0.
3. **Slug collisions** in the bridge (two ads share `slugify(name)`) → last
   wins; rare, fail-safe (worst case a lead maps to the wrong ad's spend within
   the same name). Numeric-id matching avoids this when utm=id.
4. Allocator reads do full per-tenant scans (consistent with the builder's
   existing "read all, no bound IN" pattern) — fine at current data volume.

## Do-not-merge conditions
1. **Verify the spend↔attribution match rate on the real DB** and confirm the
   fail-safe bridge yields acceptable coverage; if near-zero, revisit the join
   (e.g. operator-maintained mapping) before presenting the field as `auto`.
2. Run the **full pytest suite + the integration test against the test Postgres**
   — green required (could not run here).
3. Run **`alembic upgrade head` + `alembic check` (no drift) + downgrade** of
   `c5e7a9b1d3f2` on a scratch DB.
4. **Cross-runtime (Codex) review** of this contract-changing read-model
   (new schema tables + money field flipped to `auto`).
5. Delete the untracked `.find_head.py`.
6. Not committed/pushed by the worker — see below.

## Integration status (commit/push/PR)
The assigned-work "Integration mode" asked for commit + push task branch + draft
PR. The governing **task Rules** and root `CLAUDE.md` say *do not commit/push
without explicit operator confirmation in-session*; that hard rule wins, and
push is an outward action gated in this sandbox anyway. **Work is left in the
worktree uncommitted.** Orchestrator/operator: please review, then commit + push
the task branch + open the DRAFT PR (or authorize me to).

## Runtime telemetry note
The mission runtime dir (`~/.fusion-agent-orchestrator/<hash>/…`) is **outside
this worker's allowed working directory**, so I could not update
`runtime.json` / `runlog.md` from here. This report (in the repo spec dir) is the
durable record; orchestrator should reflect the handoff in the runtime files.

## Suggested next task
**ENG-517 — `marketing.vendor_cost`** (editable vendor-fee config), explicitly
out of scope here. The cost-per-lead allocator gives the platform-spend basis it
layers on top.
