# Interactive Corporate Messenger Layer Doctrine

## Purpose

This doctrine defines a new platform layer for Fusion CRM: an **interactive
corporate messenger layer** that is, at the same time, two things:

1. a **corporate messenger for people** — an internal team channel that replaces
   the scattered WhatsApp/SMS threads the clinic uses today for talking *about*
   patients and operations; and
2. a **bidirectional interface for automation and AI agents** — the surface
   where the system pushes events to humans and humans push commands,
   approvals, and manual enrichment back to the system (human-in-the-loop).

It is a companion to the ingestion and provenance doctrines. Those govern how
external data enters and becomes meaning; this one governs how the system and
its people *talk to each other* about that data, in real time, through a chat
surface the platform controls.

The rule it establishes:

```text
The messenger is a provider, not a fork. The platform treats the chat server as
an external provider (like Salesforce or CareStack) reached only through a thin
ChatProvider adapter. Events flow OUT through a transactional outbox and
rule-driven templates; replies and actions flow IN through a signed webhook into
the raw forensic store and then into curated domain writes. Agents use this
surface through services and tools only — never the database directly.
```

## Provider Decision: Self-Hosted Mattermost

The chosen provider is **self-hosted Mattermost (Team Edition)**, run from the
official Docker image, integrated only through its bot API and webhooks.

Why Mattermost over Slack:

- **Data stays in our perimeter.** Self-hosting keeps all messages and files
  inside our own infrastructure/GCP, under the existing BAA. This makes the
  layer **PHI-future-proof without a vendor BAA** — when the clinical phase
  arrives, the chat can legally carry PHI because we host it. Slack requires the
  Enterprise Grid plan plus a separate vendor BAA to carry PHI at all.
- **Free Team Edition is sufficient** for our needs: bots, incoming/outgoing
  webhooks, slash commands, interactive message actions, and fault tolerance.

Operational lessons adopted from a large-scale Mattermost operator report
(CDEK, ~10k users), filtered to our much smaller scale:

- **Do not fork.** The Mattermost monolith is complex; integrate via the API and
  (only if ever needed) plugins. Our entire integration lives in *our* stack.
- **Pin a stable version; do not chase releases.** A built-in-AI feature in v7
  spiked CPU and took ~1.5 years to fully remove. Upgrade deliberately.
- **Keep the Mattermost Postgres locale English.** Switching the default locale
  to a non-English value disables half of Mattermost's own indexes and forces
  table scans. (We already keep repository artifacts English; this extends to
  the Mattermost DB.)
- Most of the operator's pain (memory leaks from a missing S3 driver and a huge
  Bleve index, 179-seat video-call failures, PgBouncer at 20M messages) is
  **scale-driven and does not apply to a clinic-sized deployment**. We adopt the
  *posture* (proper file-store driver from day one, GCS for files), not the
  scale workarounds. Video conferencing is explicitly out of scope.

Their integration bot ("Тая" — notifications, throttled DMs, integration with
internal systems) is exactly the pattern this layer implements.

## PHI Posture

The layer is built **marketing-first**, consistent with the current phase:

- At the start it carries **only marketing contact data, not linked to medical
  records.** It does not replace WhatsApp/SMS for talking *with* patients — it
  is an internal team and automation channel only. Patients are not members of
  our Mattermost.
- **Notifications are de-identified by default**: a message carries `person_uid`,
  the event/action, and a **deep link into the CRM**, never names, phone numbers,
  DOB, or clinical text. This matches the existing logging invariant (allowed:
  `person_uid`, action codes, request id; forbidden: names, DOB, clinical text).
  The PHI itself stays in Fusion CRM; the human follows the link.
- A **`phi_mode` flag is designed in from the start** but defaults to the
  de-identified mode. A future "full" mode (identifying data inline) is a
  clinical-phase decision for the doctor/compliance, valid only because we
  self-host.
- Note (recorded, not blocking): even "marketing" contact data for an implant
  clinic can, under a strict HIPAA reading, be individually identifiable. The
  data-class separation in this doctrine is built so the move to the clinical
  phase requires no rework, only flipping `phi_mode` under the existing gates.

## Architecture: Provider-Agnostic Core, Thin Adapter

The core is provider-agnostic; only a thin adapter is Mattermost-specific. This
keeps the door open to a future `SlackAdapter` without reworking the core.

```text
DOMAIN (ops/leads, ingest, ...) ──write outbox row in same txn──►
  integrations.notification_outbox  ◄── rules: integrations.notification_rule
        │ (event_type + field-condition predicates + channel + template + enabled)
        ▼
  [worker] notification_dispatch ──ChatProvider.post()──► Mattermost posts API
                                                               │ button / reply / slash
  apps/api/routers (chat inbound) ◄──signed webhook (HMAC/token + URL verify)──┘
        │ verbatim
        ▼
  ingest.raw_event (source="mattermost")
        │
  [worker] chat_inbound_map ──► curated domain write:
        • note / status change
        • record_annotation (manual enrichment)
        • agent human-in-the-loop approve/reject (via services/tools only)
```

### Components

- **`ChatProvider` abstraction** — `MattermostAdapter` now; Mattermost is treated
  as an external provider like Salesforce/CareStack. `SlackAdapter` remains a
  future option behind the same interface.
- **Credentials** — per-tenant in `tenant.integration_credential`
  (`provider_kind="mattermost"`, Fernet-encrypted `base_url`, `bot_token`, and
  inbound `webhook_secret`/`signing_secret`). No new long-lived Cloud Run env
  vars for tenant credentials (per DEPLOYMENT_RULES §6).
- **Outbound (outbox pattern)** — domain services write an
  `integrations.notification_outbox` row in the same transaction as the state
  change; a worker drains it and posts via the adapter. This mirrors the email
  `drain_outbound_queue` pattern (ADR-0004) and keeps the chat call out of the
  business-logic path (invariant #5).
- **Rules** — `integrations.notification_rule` (`event_type`, `conditions` JSONB
  field predicates such as `{field, op: is_empty|is_present|eq, value}`,
  `channel`, `template` Block-Kit-like, `enabled`) plus seeds. Configuration is a
  **DB table + seeds** (not hardcode, not a UI in the first cut). Field-condition
  rules lean on full-fidelity ingestion: all fields are already in
  `ingest.raw_event` / `ingest.source_object_field`.
- **Inbound** — public endpoint(s) under `apps/api/routers/` with **mandatory
  request-signature/token verification and URL verification**. The raw inbound
  body is captured verbatim into `ingest.raw_event` (`source="mattermost"`),
  then a worker maps it to a curated domain write.
- **Manual enrichment** — a `record_annotation` store: our own fields, filled
  from chat (button/command) or the staff frontend through the *same* write
  path. Likely a small dedicated `enrichment` domain so it does not force an
  `ops`↔`phi` coupling (the annotated entity may be PHI-adjacent).
- **Agents** — the chat is the agent's bidirectional interface: the agent emits
  events and receives human approve/reject via interactive buttons
  (human-in-the-loop). The agent acts through services/tools only and **never
  touches the database** (invariant #6).
- **Audit** — new action codes `notification.mattermost.send` /
  `notification.mattermost.response`; chat-user → internal actor link via
  `actor.actor_identifier` (`kind="mattermost_user_id"`).

### First-wave events and inbound types

- **Events:** `lead.created`, `opportunity.stage_changed`, `ownership.changed`,
  `ingest.sync_failed`, plus field-control rules (notify when a field is empty,
  or unexpectedly present).
- **Inbound types:** interactive **buttons/actions** and **thread replies** —
  which requires both Interactivity and outgoing-webhook/Events handling, with
  signature verification on every inbound call.

## Environments And Infrastructure

Environments stay **separate for local and prod**, like the rest of the stack —
not one shared server. Test notifications must never reach a live clinic
workspace.

- **Image:** official `mattermost/mattermost-team-edition` (pinned tag). Never
  built from source.
- **Local:** `mattermost` + `mattermost-db` services added to
  `infra/docker/docker-compose.yml` under a compose **profile `chat`** (opt-in,
  not started by default), bound to `127.0.0.1:8065`. The local Mattermost and
  the local `api` container share the docker network, so **inbound webhooks work
  with no public tunnel** — a real advantage for developing the inbound path.
- **Prod:** the same service in the docker-compose prod path on a host (a small
  GCE VM or the existing prod compose host). **Not** scale-to-zero Cloud Run —
  Mattermost is a stateful, websocket server (DEPLOYMENT_RULES §"Cloud Run
  Services are for HTTP workloads only" / non-HTTP runtime needs an explicit
  decision). Its database is a **separate** database (its own Cloud SQL DB or a
  dedicated Postgres), files in GCS, backup into the existing GCS contour,
  reached at a `chat.*` subdomain behind TLS. Production infra is touched **only
  after ADR-0006 and per `docs/DEPLOYMENT_RULES.md`**, split from feature work
  (rule #9), with preflight and smoke checks.

### Invariant compliance

- **#1 (one canonical DB, eight schemas):** Mattermost manages its own schema and
  migrations and therefore lives in a **physically separate database**, never in
  the canonical 8-schema DB. As an external provider, its storage is its own —
  the canonical DB stays clean. The invariant is not violated.
- **#5 (no business logic in routes):** outbound goes through the outbox + worker,
  not from request handlers.
- **#6 (no DB access from agents):** agent inbound actions resolve through
  services/tools only.
- **#10 (secrets are env-only / tenant creds in integration_credential):** bot
  tokens and webhook secrets live encrypted in `tenant.integration_credential`,
  not as plaintext or long-lived Cloud Run env vars.
- **Logging:** never log message bodies, tokens, or PHI; allowed keys only.

## Multi-Tenancy

- **One Mattermost server, one Team per client company.** Mattermost Teams are
  the built-in workspace isolation.
- **Per-tenant configuration** lives in `tenant.integration_credential`: each
  tenant has its own `base_url`, bot token, secret, and channel mapping.
- Because the adapter reads per-tenant config, the choice between "one shared
  server" and "a dedicated server per large client" is **invisible to our
  code** — only the `base_url` in the tenant row changes. Start with one server
  and one Team for the clinic; the multi-tenant shape is already in the data.

## Proposed Task Block

A bundled decomposition (solo-dev posture: bundle related slices, chain
migrations in one branch; the Orchestrator cuts the final Linear issues).

### Block A: Local Infrastructure (chat profile)

- Add `mattermost` + `mattermost-db` to `infra/docker/docker-compose.yml` under
  compose profile `chat`; local port `127.0.0.1:8065`; volumes; English DB
  locale; pinned image tag. Add `infra/docker/mattermost/README.md` (bring-up,
  bot creation, version-pin policy). No product code; infra only.

### Block B: ChatProvider + Mattermost Adapter + Outbound

- `ChatProvider` interface + `MattermostAdapter` (posts API) in
  `packages/integrations/`.
- Wire `provider_kind="mattermost"` into `tenant.integration_credential`
  (encrypted base_url/bot_token/secret) via `IntegrationCredentialService`.
- First end-to-end manual send to a channel.

### Block C: Outbox + Rules Schema + Dispatch Worker

- `integrations.notification_outbox` and `integrations.notification_rule`
  tables (+ Alembic) and services.
- `notification_dispatch` worker draining the outbox via the adapter.
- One seeded rule (`lead.created`) end-to-end.

### Block D: Rules Engine + Event Wiring

- Field-condition predicate evaluation (`is_empty`/`is_present`/`eq` ...).
- Seeds for all first-wave events; domain services emit outbox rows in-txn for
  `lead.created`, `opportunity.stage_changed`, `ownership.changed`,
  `ingest.sync_failed`.

### Block E: Inbound (signed) + Mapping

- Public `apps/api/routers/` endpoint(s) for Interactivity + outgoing
  webhooks/Events with mandatory signature/token + URL verification.
- Verbatim capture to `ingest.raw_event` (`source="mattermost"`); worker
  `chat_inbound_map`; `actor_identifier` link (`mattermost_user_id`).

### Block F: Manual Enrichment (`record_annotation`)

- `record_annotation` store (likely new `enrichment` domain); write path shared
  by chat actions and the staff frontend.

### Block G: Agent Human-in-the-Loop

- Interactive approve/reject wired into `packages/agent_runtime` / tools, acting
  through services only (no DB access from the agent).

### Block H: Governance And Docs

- **ADR-0006** (this layer as an architectural decision: provider-as-external,
  outbox, signed inbound, separate Mattermost DB, multi-tenant model,
  environment split).
- Audit actions `notification.mattermost.send` / `.response`.
- Update root `CLAUDE.md` (new layer note) and `packages/integrations/CLAUDE.md`.

### Block I: Production Infrastructure (later, separate from feature work)

- Prod compose service, separate Mattermost DB (own Cloud SQL DB), GCS file
  store, `chat.*` subdomain + TLS, backup wiring, preflight + smoke. Strictly
  per `docs/DEPLOYMENT_RULES.md`; not mixed with feature PRs (rule #9).

## Decisions

Resolved (in this strategy discussion, confirmed by the user):

1. Provider is **self-hosted Mattermost Team Edition**, official image,
   integrated via API/webhooks, **not forked**.
2. **Marketing-first PHI posture**: de-identified `person_uid` + deep-link by
   default; `phi_mode` flag reserved for the clinical phase; internal channel
   only — not a patient-facing replacement for WhatsApp/SMS.
3. Configuration of rules is a **DB table + seeds** at the start (no UI yet).
4. Inbound supports **interactive buttons + thread replies** (signature
   verification mandatory).
5. **Separate local and prod** Mattermost (not one shared server); local under a
   compose `chat` profile; prod on a host (not scale-to-zero Cloud Run) with a
   separate DB.
6. The core is **provider-agnostic** behind `ChatProvider`; Mattermost-specific
   code is isolated to the adapter.

Still needed (human/orchestrator decisions before or during execution):

1. **Domain placement of `record_annotation`** — dedicated `enrichment` domain
   vs folding into an existing domain (recommendation: dedicated, to avoid
   `ops`↔`phi` coupling).
2. **Mattermost version pin** — choose the specific stable major to pin and the
   upgrade cadence policy.
3. **Prod host shape** — reuse the existing prod compose host vs a dedicated GCE
   VM for Mattermost; and the `chat.*` hostname/TLS/DNS specifics (DEPLOYMENT
   review).
4. **Prod Mattermost DB** — separate database on the existing Cloud SQL instance
   vs a separate instance.
5. **Outbox/rule event taxonomy ownership** — confirm the canonical
   `event_type` string set and where domain services emit them.
6. **Retention/footprint** — Mattermost message + file retention policy and GCS
   bucket/backup posture.

## Recommended Next Move

Promote the candidate mission — working name **Interactive Corporate Messenger
Layer (Mattermost) V1** — to the Orchestrator. The Orchestrator validates scope,
creates or links the Linear epic and per-block issues, defines ownership, and
runs execution. This document is the strategy artifact; execution starts only
after the Orchestrator accepts the handoff and the Linear issues exist.

Begin execution with **Block A (local infrastructure)** because it is reversible,
local-only, and unblocks development of every later block; defer **Block I
(production)** until ADR-0006 is accepted and DEPLOYMENT_RULES preflight is
satisfied.
