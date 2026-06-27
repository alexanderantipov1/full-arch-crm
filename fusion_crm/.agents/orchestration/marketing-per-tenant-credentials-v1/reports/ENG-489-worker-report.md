# Worker Report — ENG-489: marketing provider kinds + credential payload schemas

- **Task id / title:** ENG-489 — marketing provider kinds + credential payload schemas
- **Linear issue:** ENG-489 — https://linear.app/fusion-dental-implants/issue/ENG-489
- **Parent epic:** ENG-488. Mission: `marketing-per-tenant-credentials-v1`.
- **Role / agent:** worker / Claude Code (Opus 4.8)
- **Branch:** `eng-489-marketing-creds-provider-kinds` (NOT committed, NOT pushed — left in working tree)
- **Workspace:** canonical checkout `/Users/eduardkarionov/Desktop/Fusion_crm`
- **Allowed scope:** `packages/tenant/models.py`, `packages/tenant/schemas.py`, ONE new
  Alembic revision under `packages/db/alembic/versions/`. No `.env*` edits.

## Changed files

| File | Change |
| --- | --- |
| `packages/tenant/models.py` | Added `google_ads`, `meta_ads`, `google_search_console` to `PROVIDER_KINDS` (before the `other` catch-all). `google_analytics` was already present — not duplicated. The model's CHECK constraint is built from `PROVIDER_KINDS`, so it stays in lock-step automatically. |
| `packages/tenant/schemas.py` | Added the 3 new values to the `ProviderKind` `Literal` (kept in exact parity with `PROVIDER_KINDS`). Added 4 per-provider credential payload Pydantic models + a `MarketingCredentialPayload` union. |
| `packages/db/alembic/versions/20260616_0500_f4d5e6a7b8c9_allow_marketing_provider_kinds.py` | NEW migration (one revision) widening the `ck_integration_credential_provider_kind` CHECK constraint to admit the 3 new values. |

## New migration

- **revision id:** `f4d5e6a7b8c9`
- **down_revision:** `e3c4d5f6a7b8` (current branch head — `add_marketing_gsc_query_daily`)
- Drops + recreates the named CHECK constraint `ck_integration_credential_provider_kind`
  (constraint name unchanged; only the value list changes). Modeled exactly on the
  ENG-435 mattermost migration (`4fe9f2b9f55a`): self-contained `PRIOR_PROVIDER_KINDS`
  / `NEW_PROVIDER_KINDS` tuples, `op.f(...)`-wrapped constraint name, `_check_clause`
  builder. Additive only — no data change, existing rows unaffected.
- `downgrade()` restores the prior (ENG-435) set. It deliberately raises a
  `CheckViolation` if any row already uses one of the 3 new values (clean those up
  before rolling back) — verified below.

## Payload schema shapes (`packages/tenant/schemas.py`)

All four: `model_config = ConfigDict(extra="forbid")`. Fields are plain JSON-serialisable
`str` / `list[str]` (NOT `SecretStr`) — the payload dict is JSON-encoded then
Fernet-encrypted by `IntegrationCredentialService._wrap_envelope` before it touches the
DB, and `SecretStr` does not round-trip through `json.dumps`. This matches the existing
`IntegrationCredentialBootstrapIn` convention. Secrecy is enforced by the encryption
envelope + the "never log payload" rule, documented in the module/class docstrings.
`credential_kind` for all four = `"api_key"` (the bootstrap kind).

- **`GoogleAdsCredentialPayload`** — `client_id`, `client_secret`, `developer_token`,
  `refresh_token` (all required), `login_customer_id: str | None`, `customer_ids: list[str]`.
- **`MetaAdsCredentialPayload`** — `access_token` (required), `ad_account_ids: list[str]`,
  `app_id: str | None`, `app_secret: str | None`.
- **`GoogleAnalyticsCredentialPayload`** — `client_id`, `client_secret`, `refresh_token`,
  `property_id` (all required). Docstring notes GA4 reuses the Google Ads OAuth client,
  duplicated per provider for now.
- **`GoogleSearchConsoleCredentialPayload`** — `client_id`, `client_secret`,
  `refresh_token` (required), `site_url: str | None`. Same OAuth-reuse docstring note.
- **`MarketingCredentialPayload`** — type alias union of the four above (the single source
  the ENG-490 `from_credential` factories will consume).

Field names mirror the existing `GOOGLE_ADS_*` / `META_ADS_*` / `GA_*` / `GSC_*` env
fields in `packages/core/config.py`, so the ENG-490 env→credential migration is a clean
field-by-field mapping.

## Verification

### ruff + mypy on `packages/tenant`
```
ruff check packages/tenant            → All checks passed!
ruff check <new migration file>       → All checks passed!
mypy packages/tenant                  → Success: no issues found in 7 source files
```

### Import / parity smoke test
- All 4 payload models import; a sample `GoogleAdsCredentialPayload` round-trips through
  `json.dumps` (envelope-safe). `extra="forbid"` rejects an unknown key.
- `set(get_args(ProviderKind)) == set(PROVIDER_KINDS)` → True (literal ↔ tuple parity).
- All 3 new kinds present in `PROVIDER_KINDS`; `google_analytics` still present.

### Migration on a TEMPORARY clean Postgres (NOT the shared dev DB)
Scratch DB `eng489_scratch_<pid>` created on `127.0.0.1:5434` (superuser `fusion`), all 15
domain schemas pre-created (alembic does not create schemas), then dropped at the end.
Settings env supplied inline for the run (dummy `SECRET_KEY` / `REDIS_URL`; no `.env`
edits, no encryption needed for a CHECK-only migration). The 5 untracked `"* 2.py"`
duplicate-artifact files were temporarily stashed during the run to avoid alembic
"revision present more than once" noise, then restored.

```
alembic heads                         → f4d5e6a7b8c9 (head)
alembic upgrade head                  → full chain applied, ... e3c4d5f6a7b8 -> f4d5e6a7b8c9 OK
alembic current                       → f4d5e6a7b8c9 (head)

INSERT provider_kind='google_ads'            → SUCCESS (RETURNING google_ads, INSERT 0 1)
INSERT 'meta_ads' + 'google_search_console'  → SUCCESS (INSERT 0 2)
INSERT 'bogus_provider'                       → REJECTED: violates ck_integration_credential_provider_kind

# downgrade with new-provider rows still present:
alembic downgrade -1                  → CheckViolation (expected safety behavior; documented)
# after deleting the 3 new-provider rows:
alembic downgrade -1                  → OK, current = e3c4d5f6a7b8
INSERT 'google_ads' at prior constraint → REJECTED (constraint correctly tightened)
alembic upgrade head                  → OK, current = f4d5e6a7b8c9
```
Scratch DB dropped; duplicate artifact files restored (5 present, unchanged).

### Project drift check
No dedicated alembic-drift make target exists. `make verify-deploy` covers Settings ↔
env-reference drift only (not touched here). Model CHECK ↔ migration parity is the
relevant "drift" surface and is confirmed in lock-step (both derive from the same value
list; round-trip test above proves the migration matches the model).

## Risks

- **Low.** Additive-only CHECK widening; no data change; existing rows unaffected.
- The 4 payload models are passive DTOs not yet wired into any service method — ENG-490
  (`from_credential` factories) is the consumer. No runtime behavior changes in this PR.
- GA4 + GSC each store their own copy of the Google Ads OAuth `client_id`/`client_secret`
  (documented in docstrings). A shared-OAuth-app store is a deliberate later refactor, not
  a blocker.

## Open questions

- ENG-491 (integration UI) will need an operator-facing input schema analogous to
  `IntegrationCredentialBootstrapIn` (with per-provider field validation). Not in scope
  here — flagged for ENG-490/491.
- Frontend Zod `ProviderSchema` (`apps/web/lib/api/schemas`) mirrors `PROVIDER_KINDS`; it
  is NOT updated by this backend-only ticket. If the integrations UI must offer these
  providers, the Zod literal needs the same 3 values (likely ENG-491).

## Suggested next task

ENG-490 — per-tenant `from_credential` refactor that consumes `MarketingCredentialPayload`
to build the ad-spend / SEO connectors, replacing the `packages/core/config.py` env-var
fallback.

## Do-not-merge conditions

- None blocking. Standard: cross-runtime review of the migration before merge to `main`
  (contract-touching: widens a DB CHECK constraint), per the parallel-work policy.
- Do not commit/push from this worker session — left in the working tree per the prompt.
