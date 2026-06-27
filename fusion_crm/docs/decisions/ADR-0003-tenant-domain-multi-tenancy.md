# ADR-0003: Multi-tenancy via the `tenant` domain

**Status:** Accepted
**Date:** 2026-05-09
**Authors:** Claude Code (drafted), eduardk (decision)
**Workstreams affected:** backend, frontend, mcp, devops
**Related Linear issues:** filed alongside this ADR

---

## Context

Today the platform is hard single-tenant. Specifically:

- All credentials (Salesforce OAuth, CareStack vendor/account keys)
  live in repo-root `.env`.
- All `identity.person`, `ops.lead`, `phi.*`, `actor.*`,
  `interaction.*` rows belong implicitly to one clinic. There is no
  column that names which clinic a row belongs to.
- The CareStack account answer (`/api/v1.0/locations`) returns four
  locations belonging to one CS account; we have no row anywhere
  saying "these four locations make up clinic X".
- The strategic doctrine (memory `project_strategic_doctrine.md`)
  envisions Fusion as a productised AI-native operating system whose
  alpha tenant is the Antipov clinic — i.e. **multiple tenants is
  inevitable**, not hypothetical.

Retrofitting multi-tenancy after live PHI data is harder by an order
of magnitude. The cost of laying down the structure now is small;
the cost of doing it later is a coordinated migration across every
schema, plus a backfill against production patient data.

The domain name is `tenant` (not `clinic`). Generic on purpose —
Fusion may eventually serve adjacent verticals (e.g. specialty
medical, vet) that are not "clinics" in the dental sense.

## Decision

### A new domain `tenant`

```
packages/tenant/
├── models.py
├── schemas.py
├── repository.py
└── service.py
```

It owns one PostgreSQL schema, `tenant`, holding four tables:

#### `tenant.tenant` — the root entity

| column | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `slug` | text UNIQUE NOT NULL | URL-friendly handle, e.g. `fusion-dental-implants` |
| `name` | text NOT NULL | display name |
| `primary_email` | text | billing / notifications |
| `timezone` | text NOT NULL | IANA, e.g. `America/Los_Angeles` |
| `locale` | text NOT NULL | e.g. `en-US`; default `en-US` |
| `status` | enum(`active` `paused` `archived`) | default `active` |
| `created_at`, `updated_at` | tz-aware | mixin |

#### `tenant.location` — physical offices

| column | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK → `tenant.tenant.id` NOT NULL | |
| `external_ref` | JSONB | e.g. `{"carestack_location_id": 10029}` |
| `name` | text NOT NULL | |
| `short_name` | text | e.g. `GALLERIA` |
| `address_line1`, `address_line2`, `city`, `state`, `zip`, `country` | text | |
| `phone` | text | |
| `timezone_override` | text NULL | falls back to `tenant.timezone` |
| `latitude`, `longitude` | double | |
| `is_active` | bool DEFAULT true | |
| `created_at`, `updated_at` | tz-aware | |

UNIQUE (`tenant_id`, `name`) — same tenant cannot have two
locations of identical name.

#### `tenant.integration_credential` — encrypted per provider per tenant

| column | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK NOT NULL | |
| `provider_kind` | enum(`salesforce` `hubspot` `carestack` `open_dental` `other`) | extensible via Alembic `add_value` |
| `credential_kind` | enum(`oauth_token` `api_key` `password_grant` `webhook_secret`) | |
| `payload` | JSONB | **encrypted at rest** via the existing Fernet scheme (`packages.core.security.encrypt_text`) — never stored plaintext |
| `display_name` | text | e.g. `Salesforce production org` |
| `status` | enum(`active` `expired` `revoked`) | |
| `expires_at` | tz-aware NULL | |
| `last_refreshed_at` | tz-aware NULL | |
| `created_at`, `updated_at` | tz-aware | |

Replaces today's `integrations.integration_account` for credential
storage; the existing table remains for sync-run state (per ADR-0001
posture: integrations.* is sync state, tenant.* is configuration).

#### `tenant.setting` — typed key-value JSON for everything else

| column | type | notes |
|---|---|---|
| `tenant_id` | UUID FK NOT NULL | composite PK with `key` |
| `key` | text NOT NULL | dotted, e.g. `lead.assignment_policy` |
| `value` | JSONB NOT NULL | |
| `updated_at` | tz-aware | |

Keys are documented per-feature, not enumerated globally. Examples:
- `business_hours` → `[{day: "mon", open: "09:00", close: "18:00"}, ...]`
- `lead.assignment_policy` → `"round_robin"` or `"primary_provider"`
- `notifications.daily_digest_recipients` → `["dr@..."]`

### Foreign-key fan-out into existing domains

Every domain table that holds tenant-scoped data adds a
`tenant_id UUID NOT NULL` FK to `tenant.tenant.id`:

- `identity.person.tenant_id`
- `identity.source_link.tenant_id`
- `ops.lead.tenant_id`, `ops.account.tenant_id`,
  `ops.followup_task.tenant_id`
- `phi.*` (every table) → `tenant_id`
- `audit.access_log.tenant_id`
- `ingest.raw_event.tenant_id`
- `actor.actor.tenant_id`
- `auth.staff_session.tenant_id`, `auth.api_key.tenant_id`
- `interaction.event.tenant_id`
- `integrations.integration_account.tenant_id` (existing
  `account_id` becomes redundant — drop after migration)

Tables that are global by nature (e.g. `tenant.*` itself, or
hypothetical platform-wide reference data) do not get the column.

### Tenant resolution at runtime

**Phase 1 (single-tenant):** `Settings.default_tenant_slug` env var
(`TENANT_DEFAULT_SLUG=fusion-dental-implants`). The API resolves
the request's tenant from this value at startup; every service /
repository call passes `tenant_id` explicitly through `Principal`
(the security primitive in `packages.core.security`).

**Phase 2 (real multi-tenant):** subdomain or path prefix; resolver
in `apps/api/middleware/tenant.py`. Defer to a separate ADR —
not blocking for Phase 1. The schema is correct either way.

### Isolation model

**Phase 1: application-level enforcement.** Every repository takes
`tenant_id` and adds `WHERE tenant_id = :tenant_id`. Queries that
forget the filter are caught by:

1. A repository helper `_for_tenant(query, tenant_id)` that
   centralises the join.
2. A pytest fixture that runs every test against two tenants and
   asserts a tenant cannot read the other's data.
3. Codex review on every PR with new repository methods.

**Phase 2: PostgreSQL row-level security.** Once the second real
tenant is on board (or before, if HIPAA requires it), turn on RLS:
each session sets `SET app.tenant_id = '<uuid>'` and policies on
every table check `tenant_id = current_setting('app.tenant_id')::uuid`.
This is a separate ADR — RLS adds testing and migration friction
that we don't need to take on day one.

### Bootstrap data

Migration `2026-05-XX_tenant_domain_init.py` creates:

- One `tenant.tenant` row with `slug='fusion-dental-implants'`.
- Four `tenant.location` rows, sourced live from CareStack
  `GET /api/v1.0/locations` at migration time:
  - id 1 `FUSION-EDH` Fusion Dental Implants — El Dorado Hills
  - id 8027 `FUSION-ROS` Fusion Dental Implants — Roseville?
    (open question: spec returns same address as EDH; verify)
  - id 9028 `COSMO` Cosmo Dental — San Francisco
  - id 10029 `GALLERIA` Galleria Oral Surgery — Roseville
- One `tenant.integration_credential` row per active integration
  (Salesforce OAuth tokens, CareStack password-grant config),
  with `payload` encrypted from current `.env` values.
- Backfill `tenant_id` on every existing row in identity / ops /
  phi / actor / auth / audit / ingest / interaction / integrations
  to the single tenant id from above.

The migration is **chained**: schema → backfill → `NOT NULL`
constraint. Failure at any step rolls back cleanly.

### Removing `.env` credential-of-record

`.env` keeps Salesforce / CareStack values for the **bootstrap**
flow (the migration reads them once to seed the encrypted
`integration_credential` rows). After the bootstrap migration
ships, the runtime reads credentials from
`tenant.integration_credential` only — `.env` becomes dev-only
override.

ADR-0001's `gcp-secret://` URL scheme stays — it's how
`integration_credential.payload` gets decrypted at runtime: the
encryption key for the Fernet payload itself is a Secret Manager
secret.

### Tenant-owned provider credentials are company settings

In the productized multi-tenant model, provider credentials are entered and
managed through the tenant/company Settings UI, not copied from a developer's
local `.env` into production Cloud Run.

Examples:

- Salesforce OAuth / connected app values
- CareStack password-grant values
- Twilio account SID, auth token, messaging service / phone numbers
- HubSpot OAuth values
- Google / Microsoft mailbox grants
- payment and AI vendor credentials

These credentials are:

1. scoped by `tenant_id`,
2. stored in `tenant.integration_credential`,
3. encrypted at rest using the platform encryption key,
4. audited on create/update/revoke/default changes,
5. exposed to the frontend only as metadata,
6. resolved by services/jobs/agents through `IntegrationCredentialService`.

Secret Manager remains the home for platform runtime secrets such as
`ENCRYPTION_KEY`, DB DSNs, `SECRET_KEY`, and internal service tokens. It is not
the long-term home for per-tenant provider credentials.

### Frontend impact

Phase 1: a single read-only `/settings/tenant` page surfacing the
resolved tenant + its locations + integration statuses (no edit
yet). MCP server gets a `tenant.get_current()` tool returning the
same shape, useful for AI agent orientation.

## Consequences

### What this enables

- A clean home for clinic-level configuration that is currently
  scattered across `.env`, hard-coded constants, and PR descriptions.
- A path to onboarding a second clinic without code changes — the
  resolver is the only piece that needs work, and that's a
  bounded ADR.
- Encrypted credential storage in DB (closes the "OAuth secrets in
  plaintext .env" gap before HIPAA hardening lands).
- A canonical source for `location_id` resolution (today operators
  see `Galleria` from `locationName` text; agents need a stable id).

### What this costs

- A **schema-wide migration** with backfill. Every domain table
  gets a new column. Risky on live data — mitigated by the
  current pre-PHI window where the only real data is SF leads.
- The repository layer becomes verbose: every method takes
  `tenant_id`. Centralising this in a helper softens but doesn't
  eliminate the cognitive load.
- A second source of truth (encrypted `integration_credential` vs
  `.env`) during the migration window. We commit to deleting
  `.env` integration values within one week of the migration to
  avoid drift.

### Risks / open questions

- **Are FUSION-EDH (id 1) and FUSION-ROS (id 8027) real distinct
  locations or a CareStack data-quality bug?** Both have the same
  name and address. Operator must confirm before we treat them as
  separate `tenant.location` rows.
- **Test discipline.** Cross-tenant data leak is the killer
  failure mode. Mitigation above (two-tenant pytest fixture)
  must land in the same PR as the schema migration.
- **MCP tools** must take `tenant_id` in every call. Existing
  `packages/tools/*` have no tenant context yet — needs a sweep.

## Alternatives considered

### Option A: name the domain `clinic`

- **Approach:** dental-specific noun.
- **Pros:** matches strategic doctrine ("Clinic OS"), fewer
  vocabulary mismatches when reading code.
- **Cons:** locks the platform to "clinic"-shaped customers; if we
  ever onboard a non-clinic vertical, every reference reads wrong.
- **Why rejected:** generic noun (`tenant`) is cheaper to live with
  than a noun-rename later.

### Option B: defer multi-tenancy until the second customer

- **Approach:** stay single-tenant; retrofit when a second clinic
  arrives.
- **Pros:** zero work today, every story unblocked.
- **Cons:** retrofit lands on top of live PHI data — a minimum
  six-week migration, plus a feature freeze. Strategic doctrine
  treats multi-tenant as inevitable, not optional.
- **Why rejected:** false economy — pre-PHI is the cheapest
  window for this work.

### Option C: tenant-per-database (separate Postgres database per tenant)

- **Approach:** each tenant gets its own Postgres database.
- **Pros:** strongest isolation possible.
- **Cons:** every Alembic migration runs N times; cross-tenant
  reporting (ever wanted "all leads across all clinics") becomes a
  cross-database query; runtime resolves to a different connection
  pool per request. Operationally heavy for a 2–3 tenant horizon.
- **Why rejected:** schema-level multi-tenancy with `tenant_id`
  columns is the standard SaaS pattern at this size and gives us
  RLS on demand later.

### Option D: tenant-per-schema (one Postgres schema per tenant)

- **Approach:** the existing `identity` / `ops` / `phi` schemas
  get duplicated under namespaces (e.g. `identity_galleria`,
  `identity_cosmo`).
- **Pros:** strong isolation, single connection.
- **Cons:** migrations, ORM mappings, and the Pydantic Settings
  domain map all explode by tenant count. Works at 2 tenants;
  becomes a nightmare at 20.
- **Why rejected:** schema-explosion does not scale, and the
  isolation gain over RLS is marginal.

### Option E: app-level filter without DB-level enforcement, ever

- **Approach:** keep enforcement in the repository layer
  permanently.
- **Pros:** simplest forever.
- **Cons:** one missed `WHERE tenant_id = …` is a HIPAA
  cross-tenant data leak. RLS is the belt-and-braces backup.
- **Why partially rejected:** Phase 1 takes this approach for
  speed, but Phase 2 must add RLS. Documented as a hard gate.

## Open questions to resolve in implementation

1. CareStack EDH/ROS location duplication — operator decision
   (keep both as separate rows or merge to one).
2. `tenant.timezone` field — operator confirms `America/Los_Angeles`
   for the seed clinic.
3. Where the Fernet master key lives in production — already
   answered by ADR-0001 (`gcp-secret://encryption-key/latest`).
4. MCP tool signature change — every existing tool grows a
   `tenant_id` parameter; agents must pass it. Out-of-band
   migration plan needed.

## References

- Linear: parent + sub-issues filed alongside this ADR.
- Related: ADR-0001 (Cloud SQL prod, Secret Manager pattern),
  ADR-0002 (Cloud Run prod runtime).
- Memory: `project_strategic_doctrine.md`,
  `feedback_solo_dev_no_iteration.md`,
  `feedback_hipaa_runtime_deferred.md`.
- Code: `packages/integrations/integration_account` (current
  per-tenant home), `apps/web/lib/sf/client.ts`,
  `apps/web/lib/cs/client.ts` (current `.env`-only credential
  resolution).
