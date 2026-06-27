# Goal — Per-tenant marketing/SEO integration credentials

**Epic:** ENG-488

Move marketing + SEO ingest (Google Ads, Meta Ads, GA4, Google Search Console)
from env-based credentials (`Settings.from_env()`, the Phase 1/2 bootstrap path)
to **per-tenant credentials in `tenant.integration_credential`** — the same
model Salesforce/CareStack already use (encrypted at rest, read via
`IntegrationCredentialService.read_for`, entered through the integration-settings
UI). Multi-tenant: each tenant enters their own keys.

The daily `pull_marketing_for_all_tenants` already covers all four connectors
(Ads + Meta + GA4 + GSC) — "SEO" is included.

## Children (dependency order)
1. **ENG-489** — provider kinds (`google_ads`, `meta_ads`,
   `google_search_console`; `google_analytics` exists) + CHECK-constraint
   migration + credential payload schemas.
2. **ENG-490** — `from_credential(payload)` for the 4 clients + per-tenant pull
   (env fallback during transition). Depends on 489.
3. **ENG-491** — integration settings API + UI (ProviderCard forms) to enter the
   4 providers' keys → encrypted in DB. Depends on 489.
4. **ENG-492** — historical backfill (~12 months) per tenant. Depends on 490.
5. **ENG-493** — prod Cloud Run Job `fusion-job-marketing-pull` + Scheduler.
   Depends on 490.

## Definition of done (operator, 2026-06-16)
- Build per-tenant credentials properly (not env-only).
- Deploy frontend + backend to **prod**, and the keys live in the **prod
  `tenant.integration_credential`** (operator enters them via the prod UI),
  so marketing/SEO pulls run in prod per tenant.

## Out of scope
TikTok ads (tokens pending). Full Funnel v2 (ENG-480, PR #171).
