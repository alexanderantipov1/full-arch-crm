# Acceptance — Per-tenant marketing/SEO credentials (ENG-488)

## ENG-489 — provider kinds + schemas
- `tenant.integration_credential` accepts provider_kinds `google_ads`,
  `meta_ads`, `google_search_console` (added to `PROVIDER_KINDS` + CHECK
  constraint via a new Alembic revision chained on the current head).
  `google_analytics` already exists.
- Per-provider credential payload schemas defined (Pydantic) — the single
  source the client `from_credential` consumes:
  - google_ads: client_id, client_secret, developer_token, refresh_token,
    login_customer_id?, customer_ids[]
  - meta_ads: access_token, ad_account_ids[], app_id?, app_secret?
  - google_analytics: client_id, client_secret, refresh_token, property_id
  - google_search_console: client_id, client_secret, refresh_token, site_url?
- Migration applies cleanly on a temp/local DB; existing rows unaffected.

## ENG-490 — from_credential + per-tenant pull
- 4 clients gain `from_credential(payload)`; pull reads per-tenant creds via
  `IntegrationCredentialService.read_for`, env is fallback, no-cred → graceful
  skip. Verified by seeding a DB credential locally.

## ENG-491 — integration settings (API + UI)
- Operator can enter the 4 providers' keys in the UI; persisted encrypted in
  `tenant.integration_credential`; pull then uses them. No secrets in logs/audit.

## ENG-492 — historical backfill
- ~12 months Google/Meta/GSC/GA loaded per tenant; idempotent re-run.

## ENG-493 — prod job
- `fusion-job-marketing-pull` Cloud Run Job + Scheduler in `deploy_cloud_run.sh`,
  per-tenant DB creds; documented in PRODUCTION.md.

## Epic DoD (operator)
- Deployed to prod (frontend + backend); keys entered in the **prod**
  `tenant.integration_credential`; marketing/SEO pulls run in prod per tenant.
