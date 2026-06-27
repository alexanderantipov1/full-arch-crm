# CLAUDE.md — `packages/tenant`

The multi-tenancy root. Owns the four `tenant.*` tables. Per
`docs/decisions/ADR-0003-tenant-domain-multi-tenancy.md`.

## Tables (schema `tenant`)

- **`tenant`** — root entity per clinic / customer. `slug` is unique
  and URL-friendly (`fusion-dental-implants`). `timezone` IANA
  (`America/Los_Angeles`). `status ∈ ('active','paused','archived')`.
- **`location`** — physical offices for a tenant. `(tenant_id, name)`
  unique. `external_ref` JSONB carries provider linkage
  (`{"carestack_location_id": 10029}`). `timezone_override` falls
  back to `tenant.timezone` when null.
- **`integration_credential`** — encrypted-by-convention provider
  credentials. `payload` JSONB is the Fernet envelope
  `{"ciphertext": "<base64>", "alg": "fernet"}`; the value is wrapped
  via `IntegrationCredentialService.upsert` (which calls
  `packages.integrations.crypto.encrypt_str` internally) BEFORE insert.
  `provider_kind ∈ {salesforce, hubspot, carestack, open_dental, vapi,
  twilio, openai, anthropic, elevenlabs, deepgram, google_workspace,
  microsoft_365, birdeye, podium, google_business, stripe, square,
  carecredit, sunbit, cherry, google_analytics, meta_pixel,
  tiktok_pixel, other}` (expanded by ENG-125 to mirror the Zod
  ProviderSchema on the frontend; CHECK constraint enforced at the DB).
  `credential_kind ∈ ('oauth_token','api_key','password_grant',
  'webhook_secret')`, `status ∈ ('active','expired','revoked')`.

  Multi-mailbox columns (ENG-125):

    - `mailbox_email` — for `google_workspace` / `microsoft_365`
      grants only. Null for every other provider.
    - `location_id` — optional FK to `tenant.location.id`
      ON DELETE SET NULL. Pin a credential to a specific office;
      null = tenant-wide.
    - `is_default` — partial unique
      `(tenant_id, provider_kind) WHERE is_default = true`.
    - `tags` — JSONB string array, GIN-indexed for routing-rule
      lookup (`["marketing", "consult-followup"]`).

  The triple `(tenant_id, provider_kind, credential_kind)` is
  intentionally NOT unique — multi-mailbox depends on this.

- **`setting`** — typed key-value JSON. Composite PK
  `(tenant_id, key)`. Keys are documented per-feature (examples:
  `business_hours`, `lead.assignment_policy`,
  `notifications.daily_digest_recipients`).

## Service surface

- **`TenantService`** — `get_tenant`, `get_by_slug`,
  `create_tenant`, `update_tenant`, `list_settings`,
  `upsert_setting`, `list_credentials`,
  `record_credential`, `revoke_credential`. Every state-change
  method writes an `audit.access_log` row keyed by `tenant_id`.
- **`LocationService`** — `get_location`, `list_locations`,
  `find_by_carestack_id`, `upsert_location`,
  `import_locations_from_carestack`. Idempotent on `(tenant_id,
  name)`. State changes audited.
- **`IntegrationCredentialService`** (ENG-125) — encryption-aware
  surface:
    - `read_for(tenant_id, provider_kind, credential_kind=None)` —
      decrypts and returns the active credential, default-first
      then newest.
    - `read_default(tenant_id, provider_kind)` — only the explicit
      default; returns `None` (no fallback).
    - `read_by_id(credential_id, *, tenant_id=None)` — used by
      mailbox-routing callers that already resolved a UUID.
    - `read_for_location(tenant_id, provider_kind, location_id)` —
      location-pinned with default fallback.
    - `list_for_tenant(tenant_id, provider_kind=None)` — admin
      view, no payloads.
    - `upsert(...)` — encrypts + writes; key includes `mailbox_email`
      for email-OAuth providers. `is_default=True` flips defaults
      atomically.
    - `set_default(credential_id, *, tenant_id, provider_kind)` —
      explicit default flip.
    - `delete(credential_id, *, tenant_id)` — soft-revoke via
      `status='revoked'`.

Resolution helper:

- **`TenantService.resolve_default(slug)`** — looks up the bootstrap
  tenant by slug (used by the API dependency that builds
  `Principal.tenant_id` from `Settings.tenant_default_slug`). Raises
  `NotFoundError` when missing — the bootstrap migration must have
  run.

## Cross-package import rules

- **Allowed in:** `packages.core` only (config, exceptions, logging),
  plus `packages.audit` (write-only) and
  `packages.integrations.crypto` (Fernet helper used by
  `IntegrationCredentialService`).
- **Imported by:** every other package via the SERVICE only. Models
  and the repository are private — no `from packages.tenant.models`
  outside this directory. Code review enforces this; CI lint is on
  the to-do list.

## Hard rules

- **`TenantId` is a `NewType`** (`packages.core.types.TenantId`).
  Use it at every service boundary so a stray UUID can't slip into
  a tenant filter.
- **`tenant.integration_credential.payload` is encrypted at rest.**
  `IntegrationCredentialService.upsert` is the only sanctioned
  writer; it wraps the dict with `encrypt_str` and stores the
  envelope. NEVER call `record_credential` with plaintext payload
  values directly.
- **Plaintext payloads never appear in audit `extra`.** The audit
  row carries `tenant_id`, `credential_id`, `provider_kind`,
  `credential_kind`, `is_default`, `has_mailbox`, `has_location` —
  no payload keys, no values. Sanitiser test enforces.
- **`mailbox_email` is only valid for email-OAuth providers** —
  `MAILBOX_PROVIDER_KINDS` (`google_workspace`, `microsoft_365`).
  The service rejects mismatches at the boundary.
- **No PHI here.** This domain stores configuration only. PHI lives
  in `phi.*` and is gated by `PhiService`.
- **No silent updates.** `upsert_setting`, `record_credential`,
  `upsert_location`, `IntegrationCredentialService.upsert` all
  read-modify-write under the same `AsyncSession`; no auto-commit,
  no per-call sub-transactions.
- **Audit on every write.** State changes write an
  `audit.access_log` row at the service layer (the boundary is the
  caller, but for tenant config drift we want the audit row produced
  alongside the change so multiple call sites don't need to remember).

## Bootstrap

The seed tenant (`fusion-dental-implants`) is inserted by alembic
migration `tenant_bootstrap_seed` together with `tenant_id` backfill
on every other domain table. After the migration, every existing
row in identity / ops / phi / actor / auth / audit / ingest /
interaction / integrations carries this tenant_id.

A second migration (`tenant_credentials_seed`, ENG-125) reads the
populated `SALESFORCE_*` and `CARESTACK_*` env values via
`Settings`, encrypts them, and inserts bootstrap rows under the same
tenant id with `is_default=true`. After this migration, runtime
callers prefer the DB-backed payload (resolved via the FastAPI
`/_internal/credentials/...` endpoint); env values become
**bootstrap-only** and may be cleared.

`TENANT_DEFAULT_SLUG` env var (default `fusion-dental-implants`)
controls which tenant a Phase 1 single-tenant deployment resolves
to at startup.

`INTERNAL_CREDENTIAL_TOKEN` env var (added with ENG-125) is the
shared secret between the FastAPI internal-credentials endpoint and
the Next.js server-side route handlers. Generate with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`. The
token is only required for the multi-process resolver path; Python
callers using `IntegrationCredentialService` directly do not need it.
