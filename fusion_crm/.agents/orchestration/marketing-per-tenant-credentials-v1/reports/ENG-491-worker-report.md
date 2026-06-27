# ENG-491 — Connect marketing/SEO providers from integration settings

Parent: ENG-488 · Branch: `eng-489-marketing-creds-provider-kinds` (no commit/push — working tree only)

## Goal delivered

The operator can connect the four marketing/SEO providers (Google Ads, Meta Ads,
GA4, Google Search Console) from the integration-settings UI. Keys persist
encrypted (Fernet envelope) in `tenant.integration_credential` as `api_key`
credentials, shaped exactly like the ENG-489 payload models, and the provider
shows **connected** in the `/integrations` status response. ENG-490's
`from_credential` pull reads these rows unchanged.

## Changed files

### Backend
- `packages/tenant/schemas.py`
  - `BootstrapProviderKind` Literal extended with the four marketing providers.
  - `IntegrationCredentialBootstrapIn` gained the marketing fields:
    `developer_token`, `refresh_token`, `login_customer_id`, `customer_ids`,
    `access_token`, `ad_account_ids`, `app_id`, `app_secret`, `property_id`,
    `site_url` (`client_id`/`client_secret` reused from the existing block).
  - `validate_provider_shape` rewritten to a (required ∪ optional) set model:
    every typed field NOT in a provider's supported set is rejected as
    `unsupported`, and missing required fields are reported. Marketing rules
    mirror the ENG-489 payload models.
- `packages/tenant/credential_service.py`
  - `upsert_bootstrap_credentials` got a marketing branch (credential_kind
    `api_key`, `is_default=True`).
  - New helper `_build_marketing_payload` routes the bootstrap input through the
    ENG-489 typed models (`GoogleAdsCredentialPayload` etc.) and
    `model_dump(mode="json")`, guaranteeing the stored envelope matches what the
    ENG-490 connectors read. Added `_MARKETING_BOOTSTRAP_PROVIDERS` +
    `_MARKETING_DISPLAY_NAMES`.
- `apps/api/routers/integrations_list.py`
  - `_SURFACED_PROVIDERS` extended with the four marketing providers
    (`api_key` usable kind) so an active row flips the card to `connected`.

### Frontend (`apps/web`)
- `lib/api/schemas/common.ts` — `ProviderSchema` (used by `IntegrationAccount`)
  widened with the four marketing providers (additive enum widening; safe for
  person/inspector/ops reuse).
- `lib/api/schemas/tenant.ts`
  - `ProviderKindSchema` synced to backend (added `mattermost`, `google_ads`,
    `meta_ads`, `google_search_console`).
  - `BootstrapProviderKindSchema` + `IntegrationCredentialBootstrapInputSchema`
    extended to mirror the backend: declarative `BOOTSTRAP_REQUIRED` /
    `BOOTSTRAP_OPTIONAL` / `BOOTSTRAP_TYPED_FIELDS` drive the same
    required/unsupported `superRefine` logic. List fields (`customer_ids`,
    `ad_account_ids`) typed as `string[]`.
- `components/integrations/ProviderCard.tsx`
  - Refactored the credential form to a per-provider `fields` descriptor in
    `CREDENTIAL_COPY` (Salesforce/CareStack preserved; four marketing cards
    added with labeled fields, optional markers, masked secrets, and
    comma-separated list inputs). Submit builds the payload strictly from the
    active provider's descriptors (no cross-provider leakage).
  - Marketing providers open the credential form inline on Connect (no
    `connect/start` round trip). Sync/Disconnect buttons are hidden for them
    (`supportsSyncActions`) since their pull/revoke routes are sibling-ticket
    scope.
- `lib/integrations/providers.ts` — added labels, icons, and two new presentation
  categories (`ad_spend`, `chat`) to satisfy the `Record<ProviderKind, …>` maps
  (the new enum members were previously absent, incl. pre-existing `mattermost`).

## API contract

`POST /tenant/credentials` (existing endpoint) now also accepts:

```jsonc
// google_ads
{ "provider_kind": "google_ads", "client_id": "...", "client_secret": "...",
  "developer_token": "...", "refresh_token": "...",
  "login_customer_id": "...?", "customer_ids": ["..."]? }
// meta_ads
{ "provider_kind": "meta_ads", "access_token": "...",
  "ad_account_ids": ["act_..."]?, "app_id": "...?", "app_secret": "...?" }
// google_analytics
{ "provider_kind": "google_analytics", "client_id": "...", "client_secret": "...",
  "refresh_token": "...", "property_id": "..." }
// google_search_console
{ "provider_kind": "google_search_console", "client_id": "...",
  "client_secret": "...", "refresh_token": "...", "site_url": "...?" }
```

Response = metadata-only `IntegrationCredentialOut` (no payload). Stored as
`credential_kind=api_key`, `is_default=true`. `?` = optional.

## Verification

- **ruff** + **mypy** on `packages/tenant/{schemas,credential_service}.py` and
  `apps/api/routers/integrations_list.py`: clean.
- **tsc --noEmit** + **next lint** on `apps/web`: clean.
- Backend tests: `tests/tenant/test_credential_service.py` +
  `tests/api/test_tenant_credential_routes.py` → 36 passed.
- Frontend tests: `schemas.test.ts`, `BootstrapCredentialModal.test.tsx`,
  `useCredentials.test.tsx` → 29 passed. (Caught + fixed a regression: my first
  pass mirrored the backend's carestack `client_id`/`client_secret` *required*
  rule, which the CareStack modal does not send — restored the original
  optional treatment to preserve existing behavior.)
- **Functional (live API 127.0.0.1:8000 + DB 5434):**
  - `/integrations` now lists all four marketing providers as `disconnected`.
  - POSTed a dummy `google_ads` credential → 201, metadata-only response,
    `is_default=true`.
  - DB row `tenant.integration_credential`: payload is a Fernet envelope
    `{"alg":"fernet","ciphertext":"gAAA…"}`; grep for the dummy secrets in the
    stored payload text → **0 matches**.
  - Decrypt round-trip via `IntegrationCredentialService.read_for` returned the
    exact ENG-489 google_ads shape (6 keys; `customer_ids` list + nullable
    `login_customer_id` preserved). The read debug log emitted only structural
    fields (provider_kind/credential_kind/credential_id) — no secrets.
  - `/integrations` showed `google_ads` = `connected` with the display name.
  - Deleted the seeded row; status returned to `disconnected`.
  - Validation guard: `google_ads` + `vendor_key` → 422 "unsupported google_ads
    credential fields: vendor_key"; `meta_ads` without `access_token` → 422
    "missing required credential fields: access_token".

## Security notes

- Secrets never logged: service logs `provider_kind` + `credential_kind` only;
  audit `extra` carries structural fields (confirmed unchanged path through
  `upsert`).
- Encrypted at rest via the existing Fernet envelope; metadata-only DTO on read.
- `superRefine` / `validate_provider_shape` reject any sibling-provider field so
  a stray secret can't be encrypted into the wrong envelope.

## Risks / follow-ups

- **Sync/Disconnect for marketing cards** are intentionally hidden — their pull
  trigger + credential revoke routes are ENG-490/492+ scope. A generic
  `useDeleteCredential` (`DELETE /tenant/credentials/{id}`) exists if a later
  ticket wants disconnect on these cards.
- **Pre-existing backend↔frontend divergence on CareStack**: backend
  `validate_provider_shape` lists `client_id`/`client_secret` as *required* for
  carestack, but the frontend Zod (and the BootstrapCredentialModal) treat them
  as optional/absent. Left as-is (out of ENG-491 scope) — not introduced here.
- No migration added (constraint handled by ENG-489's
  `…_allow_marketing_provider_kinds` migration; the local DB CHECK already
  accepts the new kinds). No `.env*` edits.
