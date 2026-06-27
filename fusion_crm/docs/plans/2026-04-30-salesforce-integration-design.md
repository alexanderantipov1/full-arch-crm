# Salesforce Integration — Design

**Status:** Draft, agreed in brainstorming 2026-04-30
**Owner:** TBD
**Tenancy model:** Hybrid (single-tenant now, multi-tenant-ready)
**Scope:** Bi-directional sync of all standard SObjects + real-time via CDC streaming + Outbound Messages

---

## 0. Why this exists

We need to integrate Fusion CRM with Salesforce so the clinic can:

- Pull existing SF records (Lead/Contact/Account/Opportunity/Case/Task/Event) into Fusion CRM,
- Push Fusion CRM-originated leads/updates back to SF,
- React in real time to SF changes (CDC streaming + Outbound Messages),
- Do all of this without breaking the canonical domain model (one Person, one Lead, …).

The neighbour project `dental-calc-mvp` already has a working PKCE OAuth + Lead push;
we are porting **architecture & contracts**, not the code line-for-line.

---

## 1. Architecture & code layout

We follow the existing Fusion CRM convention: domain-package + per-domain BD-schema + services-only layer for AI tools. Integrations are a *transport*, not a domain — so:

```
packages/integrations/
├── CLAUDE.md                       # cross-provider rules (encryption, audit, retries, "how to add a provider")
├── models.py                       # IntegrationAccount, ObjectMapping, SyncRun, CDCCursor, ExternalEntity
├── schemas.py                      # Pydantic DTOs
├── repository.py                   # CRUD on integration tables
├── service.py                      # IntegrationService (provider-agnostic)
├── crypto.py                       # Fernet + EncryptedString TypeDecorator
├── base.py                         # BaseProviderClient (resource Protocol: list/get/create/update/describe) + BaseAuth ┐ PKCEOAuth, StandardOAuth2, PasswordGrantAuth
└── salesforce/                     # Salesforce-specific impl (PKCEOAuth + REST + CDC). CareStack mirrors this layout under packages/integrations/carestack/ (PasswordGrantAuth + REST polling, no CDC). HubSpot will mirror it again (StandardOAuth2 + Webhooks).
    ├── CLAUDE.md                   # SF-specific: scopes, api version, objects, CDC channels, login domain
    ├── config.py                   # constants, default mappings
    ├── oauth.py                    # PKCE: build_authorize_url, exchange_code, refresh
    ├── client.py                   # async REST client (httpx) — query, sObject CRUD, describe, composite
    ├── streaming.py                # CometD long-poll subscriber for /data/*ChangeEvent
    ├── sync.py                     # pull/push pipelines per SObject
    └── webhook.py                  # Outbound Message XML parser

apps/api/routers/integrations/
├── __init__.py                     # APIRouter(prefix="/integrations")
└── salesforce.py                   # all /integrations/salesforce/* endpoints

apps/worker/jobs/
└── salesforce.py                   # salesforce_pull, salesforce_push, salesforce_refresh_token, salesforce_cdc_listener (long-running)

packages/tools/integrations/
└── salesforce_tools.py             # AI-tool wrappers (sf_pull_object, sf_push_lead) — services-only
```

**Touched existing files:**

- `packages/db/registry.py` — import `packages.integrations.models`
- `packages/db/alembic/env.py` — `DOMAIN_SCHEMAS += ("integrations",)`
- `infra/docker/init-schemas.sql` — `CREATE SCHEMA IF NOT EXISTS integrations;`
- `packages/core/config.py` — new fields: `salesforce_client_id`, `salesforce_client_secret`, `salesforce_callback_url`, `salesforce_domain` (default `login.salesforce.com`), `encryption_key`
- `infra/docker/docker-compose.yml` — extend `x-app-env` with `SALESFORCE_*`, `ENCRYPTION_KEY`
- `apps/api/main.py` — mount integrations router
- `apps/worker/main.py` — register new arq jobs + cron schedule
- `packages/identity/CLAUDE.md` — append `salesforce_lead_id`, `salesforce_account_id` to the External ID kinds table
- `pyproject.toml` — add `cryptography>=43`, `aiosfstream>=0.6` (CDC), `lxml>=5` (Outbound Message XML), `simple-salesforce>=1.12` *(optional, for describe/discovery convenience)*

---

## 2. Data model

### 2.1 New schema `integrations`

5 tables — **all "plumbing", no domain data**. Domain stays in `identity`/`ops`/`phi`.

```python
class IntegrationAccount(Base, IDMixin, TimestampMixin):
    __tablename__ = "integration_account"
    __table_args__ = (
        UniqueConstraint("provider", "company_uid"),
        {"schema": "integrations"},
    )
    provider:        Mapped[str]                      # 'salesforce' | 'carestack' | 'hubspot' | …
    company_uid:     Mapped[UUID]                     # default GLOBAL stub, NOT NULL
    status:          Mapped[str]                      # 'connected'|'disconnected'|'error'|'expired'
    access_token:    Mapped[str | None]               # EncryptedString — bearer token (when provider issues one)
    refresh_token:   Mapped[str | None]               # EncryptedString — only for OAuth flows that issue one (SF: yes; CareStack: no — re-issue via password grant)
    token_expires_at:Mapped[datetime | None]
    scopes:          Mapped[list[str]]                # JSONB
    meta:            Mapped[dict]                     # JSONB — provider-specific creds & endpoints (see "meta JSONB shape" below)

class ObjectMapping(Base, IDMixin, TimestampMixin):
    __tablename__ = "object_mapping"
    __table_args__ = ({"schema": "integrations"},)
    account_id:  Mapped[UUID]
    sf_object:   Mapped[str]                          # 'Lead'|'Contact'|'Account'|…
    our_target:  Mapped[str]                          # 'ops.lead'|'identity.person'|'integrations.external_entity'
    field_map:   Mapped[dict]                         # {sf_field: our_field}
    direction:   Mapped[str]                          # 'pull'|'push'|'both'
    enabled:     Mapped[bool]

class SyncRun(Base, IDMixin, TimestampMixin):
    __tablename__ = "sync_run"
    account_id:        Mapped[UUID]
    sf_object:         Mapped[str | None]
    direction:         Mapped[str]                    # 'pull'|'push'|'cdc'|'webhook'
    status:            Mapped[str]                    # 'running'|'success'|'failed'|'partial'
    started_at:        Mapped[datetime]
    finished_at:       Mapped[datetime | None]
    records_total:     Mapped[int]
    records_succeeded: Mapped[int]
    records_failed:    Mapped[int]
    error:             Mapped[str | None]
    meta:              Mapped[dict]

class CDCCursor(Base, IDMixin, TimestampMixin):
    __tablename__ = "cdc_cursor"
    __table_args__ = (
        UniqueConstraint("account_id", "channel"),
        {"schema": "integrations"},
    )
    account_id: Mapped[UUID]
    channel:    Mapped[str]                           # '/data/LeadChangeEvent', …
    replay_id:  Mapped[int | None]                    # bigint

class ExternalEntity(Base, IDMixin, TimestampMixin):
    __tablename__ = "external_entity"
    __table_args__ = (
        UniqueConstraint("account_id", "object_type", "external_id"),
        {"schema": "integrations"},
    )
    account_id:    Mapped[UUID]
    object_type:   Mapped[str]                        # 'Opportunity'|'Case'|…
    external_id:   Mapped[str]
    person_uid:    Mapped[UUID | None]
    payload:       Mapped[dict]                       # last full snapshot
    last_modified: Mapped[datetime | None]
```

**`meta` JSONB shape (per provider).** Anything provider-specific that doesn't
belong in a typed column lives here. Long-lived raw secrets (vendor passwords,
account passwords) inside `meta` MUST be wrapped via the same Fernet helper
used by `EncryptedString` columns — store the ciphertext as a base64 string in
`meta`, decrypt only at use site. The JSONB itself is **not** auto-encrypted.

| Provider     | Typical `meta` keys |
|--------------|---------------------|
| `salesforce` | `instance_url`, `api_version`, `login_domain` (`login`/`test`) |
| `carestack`  | `idp_base_url`, `api_base_url`, `api_version`, `vendor_key`, `account_key`, `account_id`, `vendor_username` (encrypted), `account_password` (encrypted) |
| `hubspot`    | `portal_id`, `app_id` |

In single-tenant bootstrap these values come from `.env`; once multi-tenant
ships they move into `meta` per-`(provider, company_uid)`. Code reads SF's
`instance_url` via `account.meta["instance_url"]`, not via a typed column.

### 2.2 New domain table

`ops.account` — needed by us *and* by every CRM provider. Minimal fields:

```python
class Account(Base, IDMixin, TimestampMixin):
    __tablename__ = "account"
    __table_args__ = ({"schema": "ops"},)
    name:          Mapped[str]
    billing_city:  Mapped[str | None]
    billing_state: Mapped[str | None]
    website:       Mapped[str | None]
    phone:         Mapped[str | None]
    # owner_person_uid: optional FK to identity.person
```

External IDs go to `identity.person_identifier(kind='salesforce_account_id', value=…)`
when an Account is owned by a Person, **or** to a future `ops.account_identifier`
table when the schema needs business-entity identifiers separately.
For v1 we keep the SF Account.Id in `external_entity.payload` and on the Account row's `meta` JSONB — TBD as we use it.

### 2.3 SObject → canonical mapping (default seed)

Loaded on first Salesforce connect into `integrations.object_mapping`:

| SObject | Direction | Our target | Default field_map |
|---|---|---|---|
| `Lead` | both | `ops.lead` (+ upsert `identity.person` by email/phone) | Email→email, FirstName→first_name, LastName→last_name, Phone→phone, Company→source_company, PostalCode→postal_code |
| `Contact` | both | `identity.person` (+ identifier `salesforce_contact_id`) | Email→email, FirstName→first_name, LastName→last_name, Phone→phone, MobilePhone→mobile_phone |
| `Account` | both | `ops.account` (+ identifier `salesforce_account_id` per CATALOG) | Name→name, BillingCity→billing_city, BillingState→billing_state, Website→website, Phone→phone |
| `Opportunity` | pull | `integrations.external_entity` | full payload |
| `Case` | pull | `integrations.external_entity` | full payload |
| `Task` | pull | `integrations.external_entity` (later → `ops.followup_task`) | full payload |
| `Event` | pull | `integrations.external_entity` | full payload |

Always-on side effect: every pulled record is also written to `ingest.raw_event(source='salesforce', kind=<SObject>, payload=<original>)`.

### 2.4 Encryption — `packages/integrations/crypto.py`

- `Fernet(settings.encryption_key)`; key generated via `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and stored in `.env` as `ENCRYPTION_KEY`.
- `EncryptedString(TypeDecorator(LargeBinary))` — encrypts on write, decrypts on read. Used for `access_token`, `refresh_token`, and per-company OAuth client secrets when they land in `meta`.

### 2.5 Audit

Every outbound write to SF (push), every OAuth lifecycle event (connect/disconnect/refresh/error), every CDC event processed:

```
audit.access_log(
    principal_id, action, person_uid?,
    meta={provider:'salesforce', verb:'push'|'pull'|'oauth'|'cdc',
          object:'Lead', sf_id:'00Q…', replay_id:…, sync_run_id:…}
)
```

This is the same `AccessLog` already used for PHI — we reuse it; it's the audit trail of the system.

### 2.6 Migrations

One alembic revision: `M="add integrations schema (salesforce) + ops.account"`.

Steps:
1. Add models in `packages/integrations/models.py` and `packages/ops/models.py` (Account).
2. Update `packages/db/registry.py`, `infra/docker/init-schemas.sql`, `DOMAIN_SCHEMAS`.
3. Generate inside the api container: `make db-revision M="…"`.
4. Copy the generated file from container to host into `packages/db/alembic/versions/`.
5. Apply: `make db-upgrade`.
6. Update `docs/data-model/CATALOG.md` (move *(planned)* rows to live).

---

## 3. OAuth (PKCE) flow

### 3.1 Lifecycle

1. `POST /integrations/salesforce/connect` — body `{domain?: 'login'|'test'}` (login.salesforce.com vs test.salesforce.com).
   Server:
   - generates `state = uuid4()` and `code_verifier` (43+ chars, url-safe random),
   - computes `code_challenge = base64url(sha256(code_verifier))`,
   - stores `(state → code_verifier)` in **Redis** with TTL 10 min (key `sf:pkce:<state>`). *(Neighbour project uses in-memory dict; we already have Redis — use it.)*
   - returns `{authorize_url}` containing `client_id`, `redirect_uri`, `response_type=code`, `scope=api refresh_token`, `code_challenge`, `code_challenge_method=S256`, `state`.
2. User authorizes in Salesforce. SF redirects to `SALESFORCE_CALLBACK_URL` with `?code=…&state=…`.
3. `GET /integrations/salesforce/callback?code&state` — server:
   - reads `code_verifier` from Redis by `state`, deletes the key,
   - POSTs to `https://<domain>/services/oauth2/token` with `grant_type=authorization_code`, `code`, `code_verifier`, `client_id`, `client_secret`, `redirect_uri`,
   - upserts `IntegrationAccount(provider='salesforce', company_uid=GLOBAL, status='connected', instance_url, access_token, refresh_token, token_expires_at)`,
   - seeds default `object_mapping` rows if first connect,
   - schedules an initial bootstrap pull (`salesforce_pull` for each enabled SObject) and starts the CDC listener,
   - writes audit row,
   - redirects to a frontend success URL (or returns JSON in dev).
4. Token refresh: `salesforce_refresh_token` cron (every 30 min) checks accounts with `token_expires_at < now + 5 min` and refreshes via `grant_type=refresh_token`. On 400/401 → mark `status='expired'` and emit alert.

### 3.2 Disconnect

`POST /integrations/salesforce/disconnect`:
- POST `https://<domain>/services/oauth2/revoke?token=<refresh_token>` (best effort),
- nullify `access_token`/`refresh_token` columns, `status='disconnected'`,
- stop CDC listener for this account,
- audit row.

---

## 4. REST API — `/integrations/salesforce/*`

All under `apps/api/routers/integrations/salesforce.py`. Auth: standard `Principal` dependency.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/integrations/salesforce/status` | `{connected: bool, instance_url, expires_at, last_sync, last_error}` |
| `POST` | `/integrations/salesforce/connect` | start PKCE; returns `{authorize_url}` |
| `GET` | `/integrations/salesforce/callback` | OAuth callback; redirect or JSON |
| `POST` | `/integrations/salesforce/disconnect` | revoke + cleanup |
| `GET` | `/integrations/salesforce/objects` | list SObjects available in the connected org (uses `/services/data/v59.0/sobjects/`) |
| `GET` | `/integrations/salesforce/fields/{sobject}` | describe fields (uses `/sobjects/{name}/describe/`) |
| `GET` | `/integrations/salesforce/mappings` | list current `object_mapping` rows |
| `POST` | `/integrations/salesforce/mappings` | upsert mapping (per-(account, sobject)) |
| `POST` | `/integrations/salesforce/sync/{sobject}` | enqueue manual `salesforce_pull` job for one SObject |
| `POST` | `/integrations/salesforce/test-sync` | dry-run: build a Lead from a sample payload, validate mapping, no write |
| `GET` | `/integrations/salesforce/runs` | list recent `sync_run` (paginated) |
| `POST` | `/integrations/salesforce/webhook` | Outbound Message receiver (XML SOAP) — verify `Sf-Token` shared secret + Salesforce IP allowlist |

All write endpoints write `audit.access_log`.

---

## 5. Sync pipelines (pull / push)

### 5.1 Pull (`apps/worker/jobs/salesforce.py::salesforce_pull(sobject)`)

For each SObject with `direction in ('pull','both')`:

1. Open `SyncRun(direction='pull', sobject=…, status='running')`.
2. Compute `since` = max of (last successful run end, now-7d on first ever run).
3. SOQL via REST: `SELECT FIELDS(STANDARD) FROM <Object> WHERE LastModifiedDate > :since ORDER BY LastModifiedDate ASC LIMIT 200`. Iterate `nextRecordsUrl` for pagination (up to N pages per run, configurable; never tight-loop the org).
4. For each record:
   - write to `ingest.raw_event(source='salesforce', kind=<SObject>, payload=<record>)` (always),
   - apply `field_map` from `object_mapping` to upsert into the canonical target (per the table in §2.3) **via the owning service** — `IdentityService.upsert_person`, `OpsService.upsert_lead`/`upsert_account`, never `repo.insert`/`repo.update` directly. Sync code MUST go through services so audit, validation, and PHI gating are uniform.
   - upsert `identity.person_identifier(kind='salesforce_<sobject>_id', value=record.Id)` if applicable,
   - if `our_target` resolves to a `phi.*` table, the sync MUST call `PhiService.upsert(...)` — that method is the only path that writes `audit.access_log` and checks `Principal.can_read_phi()`. Salesforce in this PR does not auto-map any clinical SF fields (operator-driven only). CareStack `Patient → phi.patient_profile` is the canonical case where this rule fires.
5. Close `SyncRun(status='success'|'partial'|'failed', records_*=…)`.
6. Audit row per batch (not per record — would explode the log).

Errors: HTTP 401 → trigger `salesforce_refresh_token`, retry once; persistent 4xx/5xx → mark `partial`/`failed`, save trace in `meta`. Use `tenacity` with exponential backoff (already a dep).

### 5.2 Push (`salesforce_push(target_table, target_uid)`)

Triggered by:
- Domain event hooks (e.g., when a new `ops.lead` row is created via Fusion CRM UI/API),
- AI tool call (via `packages/tools/integrations/salesforce_tools.py`),
- Manual API call.

Flow:
1. Open `SyncRun(direction='push', sobject=…)`.
2. Look up `object_mapping` for that SObject; build the SF payload via `field_map` reversed.
3. If the local row already has `salesforce_<sobject>_id` in `person_identifier` → `PATCH /sobjects/<Object>/<Id>`.
4. Else → `POST /sobjects/<Object>`; capture the returned `id`, store as `person_identifier`.
5. On `INVALID_FIELD_FOR_INSERT_UPDATE` or unmapped required field — fail fast with actionable error in `SyncRun.error`.
6. Always-on: write outgoing payload to `ingest.raw_event(source='salesforce.push', kind=<SObject>, payload=…)` + audit row with `principal_id`, `person_uid`, `sf_id`.

### 5.3 What we *don't* do automatically

- We don't pull or push **PHI** through these pipelines. Clinical fields are mapped only on explicit operator action through `PhiService`, which writes its own audit and enforces `Principal.can_read_phi()`.
- We don't deduplicate Persons across providers automatically beyond the email/phone match. Cross-provider identity resolution is a future concern.

---

## 6. Real-time: CDC + Outbound Messages

### 6.1 Change Data Capture (primary channel)

Long-running arq job `salesforce_cdc_listener` (started at worker boot when at least one SF account is `connected`):

1. Open CometD long-poll session via `aiosfstream` against `https://<instance_url>/cometd/<api_version>/`.
2. Subscribe to channels:
   - `/data/LeadChangeEvent`
   - `/data/ContactChangeEvent`
   - `/data/AccountChangeEvent`
   - `/data/OpportunityChangeEvent`
   - `/data/CaseChangeEvent`
   - `/data/TaskChangeEvent`
   - `/data/EventChangeEvent`
   - For each, `replay_id` from `integrations.cdc_cursor` (or `-2` "from earliest available" on first run).
3. On each event:
   - decode payload `ChangeEventHeader` (`changeType`: CREATE/UPDATE/DELETE/UNDELETE; `recordIds`),
   - write `ingest.raw_event(source='salesforce.cdc', kind=<SObject>, payload=…)`,
   - for CREATE/UPDATE: enqueue `salesforce_pull_record(sobject, record_id)` (single-record SOQL fetch with full standard fields, then merge into canonical),
   - for DELETE: soft-delete in `external_entity`, mark identifier as inactive (we keep history),
   - update `cdc_cursor.replay_id` after successful processing.
4. On disconnect/timeout — exponential reconnect with jitter; preserve last `replay_id`.

**Edition note:** CDC is available in Developer Edition for free (all standard SObjects;
custom SObjects up to 5 selected). User confirmed Developer org → no extra licensing needed.

### 6.2 Outbound Messages (secondary channel)

Salesforce admin can configure Workflow / Flow → Outbound Message → POST XML to
`POST /integrations/salesforce/webhook` for redundancy / for legacy orgs without CDC.

Receiver:
1. Verify shared-secret header (`X-Fusion-Webhook-Token`) matches `WEBHOOK_SECRET` env (we'll add).
2. Parse SOAP envelope with `lxml`, extract `notification[*]` records.
3. Same processing as CDC: write `ingest.raw_event(source='salesforce.webhook')` + enqueue per-record sync.
4. Return `<notificationsResponse><Ack>true</Ack>` so SF doesn't retry.

### 6.3 Idempotency

Every event carries the SF record `Id`; our upserts are idempotent by `(provider, sobject, external_id)`. Duplicates between CDC and Outbound Messages are merged on the canonical row — no double-inserts.

---

## 7. AI tools layer

`packages/tools/integrations/salesforce_tools.py` exposes thin wrappers, **services-only**:

```python
async def sf_pull_object(ctx: ToolContext, sobject: str) -> dict:
    return await IntegrationService(ctx.session).enqueue_pull("salesforce", sobject)

async def sf_push_lead(ctx: ToolContext, person_uid: UUID) -> dict:
    return await IntegrationService(ctx.session).push_record("salesforce", "Lead", person_uid)
```

Registered in `packages/tools/registry.py`. Tools never touch repositories or SF directly — that's enforced by the existing tools-layer contract.

---

## 8. Configuration

### 8.1 `.env` additions

```dotenv
# --- Salesforce (Connected App OAuth, single-tenant default credentials) ---
SALESFORCE_CLIENT_ID=...
SALESFORCE_CLIENT_SECRET=...
SALESFORCE_CALLBACK_URL=http://localhost:8000/integrations/salesforce/callback
SALESFORCE_DOMAIN=login.salesforce.com   # or test.salesforce.com for Sandbox

# --- Encryption (Fernet, 32-byte url-safe base64) ---
ENCRYPTION_KEY=<generate via python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# --- Webhook shared secret (for Outbound Message receiver) ---
SALESFORCE_WEBHOOK_SECRET=<random 32+ chars>
```

### 8.2 `infra/docker/docker-compose.yml`

Extend `x-app-env: &app-env` with `SALESFORCE_*`, `ENCRYPTION_KEY`, `SALESFORCE_WEBHOOK_SECRET` so they reach api+worker containers.

### 8.3 `packages/core/config.py`

Add typed Settings fields with the same names + a `salesforce_login_url` computed property.

---

## 9. Observability

- Structured log on every job (already wired via `structlog`): job name, `account_id`, `sobject`, `replay_id`, `records_*`, `duration_ms`.
- Counters in `SyncRun` are the operational truth — admin endpoint `/integrations/salesforce/runs` exposes them.
- A future Grafana board reads `sync_run` + `audit.access_log` directly. *(Out of scope for this design.)*

---

## 10. Implementation plan (high level)

Sequential phases; each ends with a green smoke test before moving on.

1. **Foundations**
   - Add `ENCRYPTION_KEY` + `SALESFORCE_*` to `.env`, `core/config.py`, compose env.
   - Build `packages/integrations/` skeleton + `crypto.py` (`EncryptedString`, Fernet).
   - Add `integrations` schema to `init-schemas.sql` + `DOMAIN_SCHEMAS`.
   - Add `ops.account` model.
   - Generate alembic migration; update CATALOG.md.
2. **OAuth + accounts**
   - Implement PKCE (`oauth.py`) using Redis for verifier storage.
   - Endpoints: `connect`, `callback`, `status`, `disconnect`.
   - Default mapping seed on first connect.
   - Audit on every state change.
3. **Discovery**
   - `client.py` with describe / list-sobjects / SOQL.
   - Endpoints: `objects`, `fields/{sobject}`, `mappings` (GET/POST).
4. **Pull pipeline**
   - `sync.py::pull(account, sobject)` with `LastModifiedDate` cursor.
   - Worker job `salesforce_pull` + cron (every 15 min) per enabled SObject.
   - Endpoint `sync/{sobject}`; `runs` listing.
5. **Push pipeline**
   - `sync.py::push(account, target_table, target_uid)`.
   - Hook into `ops.lead` create/update events (post-commit).
   - AI tool wrappers in `packages/tools/integrations/salesforce_tools.py`.
6. **Real-time**
   - `streaming.py` with `aiosfstream`; arq long-running job `salesforce_cdc_listener`.
   - `webhook.py` + `POST /integrations/salesforce/webhook` (Outbound Messages).
   - Idempotency via `external_id` upsert.
7. **Refresh + recovery**
   - Cron job `salesforce_refresh_token` every 30 min.
   - Reconnect/backoff in CDC; alert on `status='expired'`/`'error'`.
8. **Docs**
   - `docs/integrations/salesforce.md` (operator guide: Connected App setup, scopes, callback URL, troubleshooting).
   - Update `packages/integrations/CLAUDE.md` and `packages/integrations/salesforce/CLAUDE.md`.

Each phase is an independent commit. Test plan per phase: smoke endpoints + at least one happy path + one error path (token expired, missing required SF field).

---

## 11. Future providers — design implications

The patterns in this doc (BaseAuth hierarchy, resource-oriented BaseProviderClient,
PhiService gating for `phi.*` writes, `meta` JSONB for per-provider creds) are
chosen so adding a new provider is "fill in the blanks", not "design from scratch".
Concrete near-term targets:

### 11.1 Provider matrix

| Aspect | Salesforce (this doc) | CareStack | HubSpot (future) |
|---|---|---|---|
| **Auth class** | `PKCEOAuth` (S256, code_verifier in Redis 10 min TTL) | `PasswordGrantAuth` (OAuth2 ROPC against IdP; token TTL 1h, no refresh — re-issue) | `StandardOAuth2` (3-legged authorization_code with client_secret, refresh tokens) |
| **Bearer creds source** | Per-account: `access_token`, `refresh_token` typed columns; `instance_url`/`api_version` in `meta` | Per-account: `access_token` typed column; `vendor_key`/`account_key`/`account_id`/encrypted `vendor_username`+`account_password`/`idp_base_url`/`api_base_url` in `meta`. No `refresh_token` | Per-account: `access_token`, `refresh_token` typed columns; `portal_id`/`app_id` in `meta` |
| **PHI exposure** | Low. Standard SObjects (Lead/Contact/Account/Opportunity/Case/Task/Event) are PHI-free in our usage. Clinical fields are operator-driven only. | **High.** `Patient` is PHI by default. Every Patient pull → `PhiService.upsert(...)` keyed by `identity.person_identifier(kind='carestack_patient_id')`. No direct `phi.patient_profile` repo writes from sync code. | Low. Contacts/Companies/Deals are PHI-free. |
| **Real-time** | CDC streaming (CometD long-poll, `aiosfstream`) on `/data/<Object>ChangeEvent` + Outbound Messages (XML SOAP) as redundancy | **None.** Polling-only Sync APIs (`/sync-apis/<resource>?since=...`). Worker cron pulls every N minutes per resource | Webhooks (HMAC-signed POST) — receiver under `/integrations/hubspot/webhook` |
| **API shape** | REST + SOQL for queries; `/sobjects/<name>/<id>` for CRUD | Resource REST: `GET /api/{ver}/patients`, `GET /api/{ver}/appointments?since=...`, etc. | Resource REST: `GET /crm/v3/objects/contacts`, etc. |
| **Client base** | `BaseProviderClient` Protocol (`list/get/create/update/describe`) — SF impl wraps SOQL+sObject endpoints behind those verbs | Same Protocol — CareStack impl maps verbs onto Sync APIs / Resource APIs | Same Protocol — HubSpot impl maps verbs onto CRM v3 endpoints |
| **External ID kinds** (per CATALOG) | `salesforce_lead_id`, `salesforce_contact_id`, `salesforce_account_id` | `carestack_patient_id`, `carestack_appointment_id`, `carestack_provider_id`, `carestack_location_id` | `hubspot_contact_id`, `hubspot_company_id` |
| **Domain mapping (default)** | Lead→`ops.lead`, Contact→`identity.person`, Account→`ops.account`, rest→`integrations.external_entity` | Patient→`phi.patient_profile` (via `PhiService`), Provider/Location→`integrations.external_entity`, Appointment→`integrations.external_entity` (later → its own ops table) | Contact→`identity.person`, Company→`ops.account`, Deal→`integrations.external_entity` |

### 11.2 BaseAuth hierarchy

`packages/integrations/base.py` exposes auth as a small class hierarchy, not a
single `BaseOAuth`:

```
BaseAuth (Protocol)
├── PKCEOAuth         # SF: authorize_url + code_verifier (Redis) + token exchange
├── StandardOAuth2    # HubSpot: authorize_url + client_secret + refresh_token
└── PasswordGrantAuth # CareStack: ROPC token issuance, no refresh
```

Each implements the same surface (`build_authorize_url() | None`, `exchange(...)`,
`refresh(...) | None`, `revoke(...)`). Providers compose: SF's `oauth.py`
inherits `PKCEOAuth`; CareStack's `auth.py` inherits `PasswordGrantAuth`.

### 11.3 Resource-oriented BaseProviderClient

```
class BaseProviderClient(Protocol):
    async def list(self, resource: str, *, since: datetime | None = None,
                   limit: int | None = None, cursor: str | None = None) -> AsyncIterator[dict]: ...
    async def get(self, resource: str, external_id: str) -> dict: ...
    async def create(self, resource: str, payload: dict) -> dict: ...
    async def update(self, resource: str, external_id: str, payload: dict) -> dict: ...
    async def describe(self, resource: str) -> dict: ...
```

`resource` is the provider's own name (`Lead`, `Contact`, `patients`,
`appointments`, `contacts`, …). Implementations translate the verb onto the
provider's actual endpoints (SOQL+sObject for SF; Sync APIs for CareStack;
CRM v3 for HubSpot). Sync code (`sync.py::pull/push`) talks to this Protocol
and never sees provider-specific HTTP shapes.

### 11.4 What CareStack does NOT inherit from this doc

- **No CDC.** CareStack has no streaming. Replace §6 with a polling cron
  whose cursor is `last_modified_at` (or `?since=` per Sync API), persisted in
  `integrations.sync_run.meta` (or a future `cdc_cursor`-equivalent — TBD).
- **No Outbound Messages.** No SOAP webhook receiver.
- **PHI mapping is the centerpiece, not an aside.** §5.1 step 4's
  `PhiService.upsert(...)` requirement is mandatory for CareStack from day one,
  not deferred as it is for Salesforce.

---

## 12. Open questions / follow-ups

- **Multi-tenant cutover.** When we add `Company` as a real entity, `IntegrationAccount.company_uid` flips from GLOBAL stub to the real FK. UI to enter per-company `client_id/secret` follows the neighbour project's `SalesforceCredentialsModal` pattern, but is not in this iteration.
- **PHI-aware mapping.** We deliberately don't auto-map clinical SF fields into `phi.*`. When the clinical workflow needs SF data, a separate operator-driven mapping flows through `PhiService`.
- **Bulk API.** For initial backfills > 50k records SOQL pagination is too slow; switch to Bulk API 2.0. Defer until first real org needs it.
- **Cross-provider identity dedup.** Email/phone match is enough for v1. Real dedup is a separate project.

---

## 13. Acceptance / demo

We will consider this "done for v1" when:

1. Operator runs `make up`, opens `/docs`, hits `POST /integrations/salesforce/connect`, completes OAuth in a Developer org, and `GET /integrations/salesforce/status` returns `connected: true`.
2. A Lead created in Salesforce shows up in `ops.lead` within ≤ 1 minute (CDC).
3. A Lead created via `POST /ops/leads` in Fusion CRM appears in Salesforce within ≤ 1 minute (push).
4. `audit.access_log` has rows for OAuth + each push/pull batch.
5. `docs/data-model/CATALOG.md` is updated to mark all `(planned)` rows live.
