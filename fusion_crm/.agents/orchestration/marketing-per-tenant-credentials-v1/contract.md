# Contract — Per-tenant marketing creds

Shared contracts in this epic:
- **Credential payload schemas** (ENG-489) — the per-provider dicts stored in `tenant.integration_credential.payload`; consumed by client `from_credential` (ENG-490) and written by the integration UI/API (ENG-491). Backend owns the canonical shape; UI Zod mirrors it.
- **Bootstrap-credentials API** (ENG-491) — request shape for connecting google_ads/meta_ads/google_analytics/google_search_console.
- **New Alembic revision** (ENG-489) — exactly one, chained on current head; immutable once merged.

Forbidden for all: `.env*`, editing merged migrations, prod deploy (operator-run).
