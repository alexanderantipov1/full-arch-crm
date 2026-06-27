# ENG-490 — Marketing/SEO clients: per-tenant DB credentials + per-tenant pull

Parent: ENG-488. Branch: `eng-489-marketing-creds-provider-kinds` (built on
ENG-489's payload schemas; NOT committed — left in the working tree).

## What was done

1. Added a `from_credential(payload: dict, http=None)` classmethod to each of
   the four marketing/SEO clients. Each validates the decrypted payload against
   its ENG-489 schema (`extra="forbid"`) and builds the SAME client `from_env()`
   builds. `from_env()` is kept intact as the transition fallback.
2. Reworked `apps/worker/jobs/marketing_pull.py` so each per-tenant + per-provider
   pull resolves the DB credential FIRST (`IntegrationCredentialService.read_for(
   tenant_id, "<provider>", "api_key")`), then falls back to `from_env()` on
   `NoCredentialError`, then short-circuits to `{"skipped": "no_credential"}` when
   neither DB nor env creds exist. Each tenant now pulls with ITS OWN account, so
   ingested rows are attributed to the correct `tenant_id`.
3. Logs stay secret-free: only `provider` / `tenant_id` / `source` (db|env) /
   counts. The credential service already logs `provider_kind` + `credential_kind`
   only.

## Changed files

- `packages/integrations/google_ads/client.py` — `GoogleAdsClient.from_credential`
- `packages/integrations/meta_ads/client.py` — `MetaAdsClient.from_credential`
- `packages/integrations/google_analytics/client.py` — `GoogleAnalyticsClient.from_credential`
- `packages/integrations/google_search_console/client.py` — `GoogleSearchConsoleClient.from_credential`
- `apps/worker/jobs/marketing_pull.py` — DB-cred-first resolution + `_read_marketing_credential` helper
- `tests/integrations/{google_ads,meta_ads,google_analytics,google_search_console}/test_client.py` — `from_credential` unit tests (valid/invalid/extra-key/empty-ids)
- `tests/worker/test_marketing_pull_job.py` — NEW; DB-preferred-over-env, env-fallback, graceful-skip (parametrized over all 4 providers)
- `packages/integrations/{google_ads,meta_ads,google_analytics,google_search_console}/CLAUDE.md` — credential-carve-out notes updated to ENG-490

## `from_credential` signatures

```python
GoogleAdsClient.from_credential(payload: dict[str, Any], http: httpx.AsyncClient | None = None) -> GoogleAdsClient
MetaAdsClient.from_credential(payload: dict[str, Any], http: httpx.AsyncClient | None = None) -> MetaAdsClient
GoogleAnalyticsClient.from_credential(payload: dict[str, Any], http: httpx.AsyncClient | None = None) -> GoogleAnalyticsClient
GoogleSearchConsoleClient.from_credential(payload: dict[str, Any], http: httpx.AsyncClient | None = None) -> GoogleSearchConsoleClient
```

Each validates via the matching `packages.tenant.schemas.*CredentialPayload`
and raises the provider's `*NotConnectedError` on a malformed payload (or empty
account/customer id list) so the per-tenant pull skips gracefully instead of
crashing. The `details` on that error never echo secret values (only field
counts / missing-field names). Import path `integrations → tenant.schemas` is
permitted by the package import matrix (integrations → tenant ✓).

## Verification

- `ruff check` on all changed packages + tests → all passed.
- `mypy` on the four integration subpackages + `marketing_pull.py` → Success,
  no issues (13 source files).
- Tests: `pytest` on the four client test dirs + the new worker test →
  **50 passed**.
- Functional check on the LOCAL dev DB (127.0.0.1:5434 fusion/fusion, bootstrap
  tenant `11111111-1111-4111-8111-111111111111`):
  - Seeded ONE dummy `google_analytics` `api_key` credential via
    `IntegrationCredentialService.upsert(...)`.
  - CASE1 (DB cred present, env also present): `pull_ga4_for_tenant` resolved
    the DB credential (`tenant.credential.read` logged), built the client via
    `from_credential`, and `from_env` was NOT called → DB preferred over env;
    got past `no_credential`.
  - CASE2 (no DB cred, env present): env fallback built a REAL client from the
    local `.env` GA creds → got past `no_credential`.
  - CASE3 (no DB cred, no env — `from_env` patched to raise NotConnected):
    returned `{"skipped": "no_credential"}` → graceful skip.
  - Seeded credential deleted afterward; verified 0 leftover `ENG-490%` rows.

  (`google_analytics` was used for the live seed because it is already in the
  DB CHECK constraint — see the risk below. The credential-resolution path is
  identical for all four providers; the other three are covered by the mocked
  worker tests.)

## Risks / follow-ups (NOT in ENG-490 scope)

- **DB CHECK constraint gap (blocking for prod seeding of 3 of 4 providers).**
  `ck_integration_credential_provider_kind` on `tenant.integration_credential`
  currently allows `google_analytics`, `meta_pixel`, `tiktok_pixel`,
  `mattermost`, etc. — but NOT the three ENG-489 kinds `google_ads`,
  `meta_ads`, `google_search_console`. ENG-489 widened the Python `PROVIDER_KINDS`
  literal but the DB constraint was not migrated. Seeding a `google_ads` /
  `meta_ads` / `google_search_console` credential today raises
  `CheckViolationError`. A sibling ticket (ENG-491+) must add a migration that
  widens this CHECK constraint before those three providers can store DB creds.
  This ticket forbade a new migration, so it is intentionally left for the
  sibling. `from_credential` + the worker resolution path are already correct;
  they just have no row to read for those three until the constraint lands.
- The `customer_ids` / `ad_account_ids` in the payload are digit-stripped in
  `from_credential` (matching the env path), so an `act_<id>` or dashed form
  round-trips.
