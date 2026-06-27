# ADR-0006: Interactive corporate messenger layer

**Status:** Accepted
**Date:** 2026-06-15
**Authors:** Claude Code
**Workstreams affected:** backend, infra
**Related Linear issues:** ENG-433 (epic), ENG-434, ENG-435, ENG-436, ENG-437, ENG-438, ENG-439, ENG-440, ENG-441, ENG-442, ENG-443

---

## Context

The clinic coordinates patient matters — scheduling, follow-ups, hand-offs
between the agent and the treatment coordinator — over uncontrolled WhatsApp and
SMS threads on personal phones. That channel has no audit trail, no access
control, no de-identification, and no programmatic surface an automation or AI
agent can read from or write to. It is also the wrong place for anything that
might touch a medical record once the clinic moves past the marketing-first
phase.

We need an internal messenger that (1) replaces those scattered threads with a
controlled team channel, and (2) doubles as a bidirectional interface where the
system pushes events to humans and humans push commands / approvals / manual
enrichment back to the system. It must be PHI-future-proof: although the early
phase only carries contact data not linked to medical records, the design must
not have to be re-litigated when clinical context starts flowing.

The platform's first architectural invariant is a single canonical PostgreSQL
database with eight schemas, and AI agents never touch the database directly.
Any messenger we adopt must not violate either rule.

Strategy artifact: `.agents/strategy/INTERACTIVE_MESSENGER_LAYER_DOCTRINE.md`.

## Decision

**Adopt self-hosted Mattermost as an EXTERNAL provider behind a `ChatProvider`
abstraction, fed by a transactional outbox with a field-condition rule engine
and de-identified-by-default rendering. Mattermost runs its own database,
physically separate from the canonical eight-schema DB, so invariant #1 is
preserved.**

In force (grep-verifiable):

- **Provider-as-external, not forked.** `infra/docker/docker-compose.yml`
  runs the official `mattermost/mattermost-team-edition:10.5` image (service
  `mattermost`) plus a dedicated `mattermost-db`, both gated behind compose
  profile `chat` — a plain `docker compose up` does not start them. We integrate
  via Mattermost's HTTP API, never by modifying its source. Operator notes live
  in `infra/docker/mattermost/README.md`.
- **`ChatProvider` Protocol.** `packages/integrations/chat/base.py` defines the
  `ChatProvider` Protocol (`async def post(message: ChatMessage) ->
  ChatPostResult`) plus the `ChatMessage` / `ChatPostResult` dataclasses.
  `packages/integrations/chat/mattermost.py` (`MattermostAdapter`) is the single
  implementation, posting to the Mattermost posts API and translating its HTTP
  errors into `ChatPostResult(ok=False, error=...)`.
- **Mattermost's own DB, separate from canonical.** The `mattermost-db`
  service is a distinct Postgres instance, not a ninth schema in the canonical
  database — invariant #1 (one canonical DB, eight schemas) is untouched.
- **Transactional outbox + drain.** Tables `integrations.notification_outbox`
  and `integrations.notification_rule` (migration `a7b8c9d0e1f2`) capture the
  enqueue-then-deliver split. `packages/integrations/notification_service.py`
  enqueues rows in the same unit of work as the originating change;
  `packages/integrations/notification_repository.py` /
  `notification_schemas.py` are the data + DTO layers. The worker job
  `apps/worker/jobs/notification_dispatch.py` (`drain_notification_outbox`,
  scheduled by cron) drains the outbox and posts via the resolved provider. This
  mirrors the email outreach `drain_outbound_queue` pattern (ADR-0004).
- **Field-condition rule engine.** `packages/integrations/chat/conditions.py`
  evaluates predicate rules against an event's field context to decide which
  channel a `notification_rule` routes to. `packages/integrations/chat/events.py`
  defines the event taxonomy constants `lead.created`,
  `opportunity.stage_changed`, `ownership.changed`, `ingest.sync_failed`.
- **Full-PHI rendering by default (ENG-460 reversal — see the dedicated
  section below).** `packages/integrations/chat/render.py` supports two modes.
  `phi_mode="deidentified"` substitutes only an allowlist (`person_uid`,
  `deep_link`, `event_type`, plus non-PII labels) and renders every other
  `{{var}}` as `[redacted]`, failing closed. `phi_mode="full"` substitutes any
  context var verbatim. `NotificationEventService.emit` selects the mode from
  `Settings.messenger_phi_full` (default **True** → `full`), so cards carry the
  real patient name / phone / provider. This is the deliberate reversal of the
  original de-identified-default posture, recorded below.
- **Per-tenant credentials in the tenant domain.** The Mattermost bot token is a
  per-tenant `tenant.integration_credential` row with
  `provider_kind="mattermost"`, `credential_kind="api_key"`.
  `packages/integrations/chat/resolver.py` reads it via
  `IntegrationCredentialService.read_for(tenant_id, "mattermost", "api_key")`
  and constructs the `MattermostAdapter`. `"mattermost"` is in `PROVIDER_KINDS`
  (`packages/tenant/models.py`); migration `4fe9f2b9f55a` widens the
  `ck_integration_credential_provider_kind` CHECK constraint to admit it.
- **`ops` does not import `integrations`.** The flagship `lead.created` emit is
  wired at the API boundary `apps/api/routers/ops.py::create_lead` (via the
  injected `NotificationEventService` from
  `packages/integrations/chat/event_service.py`), because the `ops` domain MUST
  NOT import `integrations` (packages import matrix). The remaining three event
  wirings are tracked as ENG-443 (Block D2).
- **Audit actions** written by the new code (exact strings; documented in
  `packages/audit/CLAUDE.md`):
  `integrations.notification.enqueued`, `integrations.notification.rule.create`,
  `integrations.notification.rule.update` (all in `notification_service.py`),
  and `notification.dispatch.sent`, `notification.dispatch.failed` (in
  `notification_dispatch.py`).
- **Multi-tenancy = one server, one Team per tenant.** A single Mattermost
  server hosts one Mattermost Team per Fusion tenant; routing is driven by the
  per-tenant credential and the rule's target channel.
- **Separate local / prod environments.** Locally Mattermost runs under compose
  profile `chat`. In production it must run on a persistent host (stateful,
  websocket-driven) — explicitly NOT a scale-to-zero Cloud Run service, unlike
  the stateless API/worker (ADR-0002).
- **Signed inbound is PLANNED, not built.** Inbound commands from Mattermost
  back into the platform (slash commands / webhooks with signature verification)
  are Block E (ENG-438) and are not yet implemented. The outbound (system →
  chat) direction is what landed in Blocks A/B/C/D.
- **Marketing-first scope (now superseded by the ENG-460 reversal).** At the
  start the messenger carried only contact data not linked to medical records;
  the de-identified default and the (then-reserved) `phi_mode="full"` made
  widening to clinical context a configuration decision rather than a redesign.
  ENG-460 took that decision — see below.

## Update — ENG-460: messenger is an AUTHORIZED PHI surface (2026-06-15)

The de-identified `person_uid`-only cards were useless to staff (`🟢 New lead
f4c2024e-… — open in CRM: …`). The operator decided the corporate messenger is
an **authorized PHI surface**: only staff with PHI access read the Mattermost
team, so notification cards now carry the patient's **real name, phone, source
(lead) / provider+kind+time (consultation)** plus a working CRM deep link, as
rich Mattermost attachment cards.

- **Default flip.** `Settings.messenger_phi_full` defaults to `True`;
  `NotificationEventService.emit` renders in `phi_mode="full"`. Flip the flag to
  `False` for a clean rollback to de-identified rendering.
- **PHI resolved at the boundary.** The real name / phone are resolved via
  `IdentityService` at the worker boundary (lead: `_emit_lead_created_notifications`
  in `apps/worker/jobs/ingest_scheduled.py`; consultation:
  `packages/ingest/carestack_appointment_service.py` → `consultation_notify.py`).
  The NON-PII signals (`SfLeadNotifySignal`, consultation context) are unchanged.
- **SECURITY IMPLICATION.** PHI now lives in the Mattermost store. The prod
  Mattermost server (ENG-442) MUST be treated as a PHI system: access control,
  TLS in transit, encrypted backup, and a retention policy. The platform's own
  application logs stay PHI-free regardless — only `person_uid` and event codes
  are logged, never the rendered card text.

## Consequences

### What this enables

- A single audited, access-controlled internal channel replaces uncontrolled
  WhatsApp/SMS for talking about patients and operations.
- System events (`lead.created` today; opportunity / ownership / sync-failure
  next) reach the right humans through declarative `notification_rule` rows with
  field conditions — no code change to add or retarget a notification.
- Enqueue happens in the originating transaction, so a notification is never
  lost to a crash between the business write and the post, and a chat outage
  never rolls back the business change.
- The `phi_mode` seam made widening to full PHI a configuration decision, not a
  redesign — ENG-460 exercised exactly that by flipping
  `Settings.messenger_phi_full` to `True` (see the ENG-460 update above). The
  trade-off is that the Mattermost server is now a PHI system (see the security
  implication noted there).
- A future AI agent gets a governed surface to push to (and, once Block E lands,
  to receive human commands / approvals from) without ever touching the DB.

### What this costs

- A new stateful service to operate: a Mattermost server + its own Postgres,
  with backups, upgrades, and a TLS-terminated host in production.
- A second provider abstraction and a new outbox/rule subsystem to maintain
  (`packages/integrations/chat/` + the notification service / worker).
- Version-pin discipline: the official image is pinned (`10.5`) and must be
  bumped deliberately rather than tracking `latest`.

### Risks / open questions

- **`record_annotation` domain** — where human-supplied enrichment from chat is
  persisted is still open (ENG-439).
- **Mattermost version pin / upgrade cadence** — the `10.5` pin needs an
  agreed bump policy.
- **Production host + `chat.*` TLS** — the persistent host, DNS, and TLS
  termination for the prod Mattermost are not yet provisioned.
- **Production DB placement** — where `mattermost-db` lives in prod (managed
  instance vs co-located) is undecided.
- **Retention / backup** — message retention and backup policy for the
  Mattermost data store is not yet defined.
- **Not yet verified end-to-end** — a live send against a real Mattermost
  server and signed inbound (Block E, ENG-438) have not been exercised against
  real infrastructure.

## Alternatives considered

### Option A: Slack SaaS

- **Approach:** use Slack as the corporate messenger and bot surface.
- **Pros:** zero hosting, mature apps + API, staff already familiar.
- **Cons:** a HIPAA BAA is available only on Enterprise Grid; conversation and
  attachment data leave the clinic's perimeter and live on a third-party SaaS.
- **Why rejected:** incompatible with PHI-future-proofing — we would have to
  migrate off it the moment clinical context flows, and the data-residency
  posture is wrong for the mission from day one.

### Option B: Fork Mattermost

- **Approach:** fork the Mattermost source and embed our integration directly.
- **Pros:** maximal control over behavior and data model.
- **Cons:** Mattermost is a large monolith; carrying a fork means owning its
  upgrade treadmill and security patches forever.
- **Why rejected:** the API surface is sufficient — we integrate via the posts
  API behind `ChatProvider`, keeping Mattermost a swappable external dependency
  with none of the fork-maintenance cost.

### Option C: Managed Mattermost Cloud

- **Approach:** use Mattermost's hosted Cloud offering instead of self-hosting.
- **Pros:** no server to operate; same product and API.
- **Cons:** data again lives off-perimeter on a third party.
- **Why rejected:** same PHI-future-proofing reason as Slack — self-hosting
  keeps the message store inside the clinic's controlled boundary, which is the
  whole point of the layer.

## References

- Linear: ENG-433 (epic) + ENG-434..ENG-443
- Strategy: `.agents/strategy/INTERACTIVE_MESSENGER_LAYER_DOCTRINE.md`
- Related ADRs:
  - ADR-0003 (tenant-domain multi-tenancy) — per-tenant credential model
    reused for the Mattermost bot token.
  - ADR-0004 (operator-account email outreach) — the transactional
    outbox + drain pattern precedent (`outreach.outbound_queue` →
    `drain_outbound_queue`).
  - ADR-0005 (full-fidelity ingestion) — the raw field set the condition
    engine leans on to evaluate event predicates.
  - ADR-0002 (Cloud Run prod runtime) — why the stateful Mattermost host is
    explicitly NOT a scale-to-zero Cloud Run service.
