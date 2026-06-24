# CLAUDE.md — `packages/integrations`

Provider plumbing only. NO domain data here. Provider records map into the
canonical schemas (`identity`, `ops`, `phi`) via the service layer.

## Tables (schema `integrations`)

- **`integration_account`** — one per `(provider, company_uid)`. OAuth tokens
  (`access_token`, `refresh_token`) are `EncryptedString` (Fernet). Provider-
  specific extras live in `meta` JSONB. `company_uid` defaults to a GLOBAL
  stub UUID until multi-tenancy lands (M10).
- **`object_mapping`** — per-account map of provider object → our canonical
  target with direction `pull|push|both` and a JSONB `field_map`.
- **`sync_run`** — append-only journal of every inbound/pull/push/cdc/webhook
  batch, including `skipped_credential` runs for missing active credentials.
- **`cdc_cursor`** — last-processed Replay-Id per CDC channel (Salesforce).
- **`external_entity`** — generic safe for provider objects without a
  canonical home (Opportunity, Case, CareStack Provider, …). Promote out
  when an object earns a real domain table.

## Extras

- **`crypto.py`** — `Fernet` helper + `EncryptedString(TypeDecorator)`.
  Token columns use `EncryptedString`; the JSONB `meta` is NOT
  auto-encrypted — when storing a long-lived secret (e.g. CareStack vendor
  password) inside `meta`, wrap it with `encrypt_str` and store the
  ciphertext as a base64 string.
- **`base.py`** — auth class hierarchy and provider client protocol.
- **`_oauth_state.py`** — shared HMAC-signed CSRF token for the
  Google / Microsoft connect flow (ENG-131). Reuses
  `Settings.internal_credential_token` as the HMAC key. Both
  `google_workspace` and `microsoft_365` mint state via the same helper;
  the route handler verifies before processing the `code` parameter.

## Auth class hierarchy (`base.py`)

```
BaseAuth (Protocol)
├── PKCEOAuth         — Salesforce: authorize URL + code_verifier + token exchange
├── StandardOAuth2    — HubSpot: 3-legged authorization_code with refresh tokens
└── PasswordGrantAuth — CareStack: ROPC token issuance, no refresh
```

Each implements:
- `build_authorize_url() -> str | None` (None when there's no redirect flow)
- `exchange(...) -> AuthExchangeResult`
- `refresh(...) -> AuthExchangeResult | None` (None when not supported)
- `revoke(token: str) -> None`

The Google + Microsoft OAuth clients (ENG-131) intentionally do NOT
adopt this hierarchy — Google and Microsoft both ship typed
ID-tokens whose claims drive a HIPAA compliance gate, which doesn't
fit the abstract `AuthExchangeResult` shape. They live as
self-contained classes inside their own subpackages and reuse the
state-CSRF helper directly. If we ever onboard a third email
provider, factor a shared base; until then, two siblings are
cheaper than a leaky abstraction.

## Provider client protocol

```python
class BaseProviderClient(Protocol):
    async def list(self, resource: str, *, since: datetime | None = None,
                   limit: int | None = None, cursor: str | None = None
                   ) -> AsyncIterator[dict]: ...
    async def get(self, resource: str, external_id: str) -> dict: ...
    async def create(self, resource: str, payload: dict) -> dict: ...
    async def update(self, resource: str, external_id: str, payload: dict) -> dict: ...
    async def describe(self, resource: str) -> dict: ...
```

`resource` is the provider's own name (`Lead`, `patients`, `contacts`, …).
Implementations translate verbs onto provider-specific HTTP shapes.

## Cross-package import rules

Allowed: `tenant`, `identity`, `actor`, `ingest`, `interaction`, `ops`,
`audit`, `core`.

**`phi` is service-only.** Sync code that touches `phi.*` MUST go through
`PhiService.upsert(...)`. NEVER import `phi.models` or `phi.repository` from
this package.

## Service responsibilities

`IntegrationService` is the public surface (skeleton; provider code in
subpackages calls into it):

- `connect(provider, payload)` — start OAuth or store creds; emit audit row.
- `disconnect(account_id)` — revoke tokens, mark disconnected.
- `upsert_account(provider, company_uid, ...)` — idempotent.
- `record_sync_run(account_id, ...)` — open/close sync journal entries.
- `bump_cdc_cursor(account_id, channel, replay_id)` — Salesforce CDC.

For email-OAuth providers (`google_workspace`, `microsoft_365`),
credentials live in `tenant.integration_credential` and are accessed
via `IntegrationCredentialService` (in the `tenant` package). The new
packages do NOT use `integrations.integration_account` — that table
predates `tenant.integration_credential` and is being phased out for
new providers.

## Hard rules

- Token columns are NEVER returned in plaintext from a repository — service
  decrypts on demand only when calling the provider.
- `audit.access_log` (or future `audit.agent_tool_call`) row written for
  every OAuth state change and every sync_run lifecycle event.
- Repositories don't commit; only the boundary commits.
- Adding a new provider = new subpackage `packages/integrations/<provider>/`
  with its own `CLAUDE.md` + `AGENTS.md`. No provider code lives at the
  package root.

## Messenger layer (`chat/` + notification outbox — ENG-433, ADR-0006)

The interactive corporate messenger layer pushes platform events to a
self-hosted Mattermost team and (planned) accepts human commands back.
Mattermost is an EXTERNAL provider behind an abstraction — we never fork
it, we post via its HTTP API. It runs its OWN Postgres, physically
separate from the canonical eight-schema DB (invariant #1 preserved).

- **`chat/` subpackage** — `base.py` (`ChatProvider` Protocol +
  `ChatMessage` / `ChatPostResult`), `mattermost.py` (`MattermostAdapter`,
  the only provider impl), `resolver.py` (reads the per-tenant bot token via
  `IntegrationCredentialService.read_for(tenant_id, "mattermost", "api_key")`
  and builds the adapter), `events.py` (event taxonomy: `lead.created`,
  `opportunity.stage_changed`, `ownership.changed`, `ingest.sync_failed`),
  `conditions.py` (field-predicate rule engine), `render.py`
  (de-identified template renderer), `event_service.py`
  (`NotificationEventService.emit`), `seeds.py`.
- **Tables** — `integrations.notification_outbox` +
  `integrations.notification_rule` (migration `a7b8c9d0e1f2`). Enqueue
  happens in the originating unit of work; the worker
  `apps/worker/jobs/notification_dispatch.py::drain_notification_outbox`
  drains and posts (transactional outbox + drain, mirroring outreach
  `drain_outbound_queue`). DTO/data layers:
  `notification_schemas.py`, `notification_repository.py`,
  `notification_service.py`.
- **Messenger = AUTHORIZED PHI surface (ENG-460, REVERSAL).** The
  operator decided the corporate messenger is a PHI surface — only staff
  with PHI access read the Mattermost team — so notification cards now
  carry the patient's REAL name / phone / provider, not a de-identified
  `person_uid` stub. `event_service.emit` selects the render mode from
  `Settings.messenger_phi_full` (default **True** → `phi_mode="full"`,
  which substitutes ANY context var verbatim; the allowlist is bypassed).
  Setting the flag False restores the historical de-identified behaviour.
  - **Render contract** — `render.py` `phi_mode="deidentified"` (the
    fallback) substitutes ONLY an allowlist (`person_uid`, `deep_link`,
    `event_type`, non-PII labels); everything else renders `[redacted]`,
    failing closed. `phi_mode="full"` (the default via the flag)
    substitutes everything; the lead + consultation cards rely on it for
    `{{name}}` / `{{phone}}`. The PHI is resolved at the worker boundary
    (`IdentityService`), never inside the de-identified signal/context.
  - **SECURITY IMPLICATION** — with full mode on, PHI lands in the
    Mattermost store. The prod Mattermost server (ENG-442) MUST be treated
    as a PHI system: access control, TLS in transit, encrypted backup,
    retention policy. Application logs stay PHI-free regardless (only
    `person_uid` / event codes are logged, never the rendered card).
- **Credential** — `provider_kind="mattermost"` in `PROVIDER_KINDS`
  (`packages/tenant/models.py`); CHECK constraint widened by migration
  `4fe9f2b9f55a` (`ck_integration_credential_provider_kind`).
- **`ops` boundary** — `ops` MUST NOT import `integrations`, so the flagship
  `lead.created` emit is wired at the API boundary
  `apps/api/routers/ops.py::create_lead`. Remaining wirings: ENG-443.
- **Audit actions** — `integrations.notification.enqueued`,
  `integrations.notification.rule.create` / `.update`,
  `notification.dispatch.sent` / `.failed` (see `packages/audit/CLAUDE.md`).
- Signed inbound (chat → platform) is PLANNED (Block E, ENG-438), not built.

See ADR-0006 and `.agents/strategy/INTERACTIVE_MESSENGER_LAYER_DOCTRINE.md`.

## Subpackages (when they land)

- `salesforce/` — PKCE OAuth + REST + CDC streaming + Outbound Messages (M1 + M2)
- `carestack/` — Password Grant OAuth + Sync APIs polling (M1 + M2)
- `google_workspace/` — operator-account OAuth + Gmail send (ENG-131)
- `microsoft_365/` — operator-account OAuth + Graph sendMail (ENG-131)
- `chat/` — Mattermost messenger + notification outbox (ENG-433, ADR-0006)
- `hubspot/` — Standard OAuth2 + Webhooks (future)
