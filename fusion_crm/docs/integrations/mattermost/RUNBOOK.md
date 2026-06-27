# Interactive Corporate Messenger Layer — Runbook (ENG-433)

> How the Mattermost messenger layer works, how to operate + test it, and how to
> bring it to production. Companion to **ADR-0006**
> (`docs/decisions/ADR-0006-interactive-messenger-layer.md`) and the doctrine
> (`.agents/strategy/INTERACTIVE_MESSENGER_LAYER_DOCTRINE.md`). Local infra
> quick-start lives in `infra/docker/mattermost/README.md`.

Status: **merged to `eng-425`** (PR #152). Blocks A–H done. Remaining: D2
(ENG-443), production infra (ENG-442), frontend Zod `mattermost` value.

---

## 1. What it is

A bidirectional interactive corporate messenger on **self-hosted Mattermost**,
treated as an **external provider** behind a thin `ChatProvider` adapter — never
forked. Two directions:

- **Outbound:** a platform event → rule match (field conditions) →
  **de-identified** render → transactional outbox → worker → Mattermost post.
- **Inbound:** a human message / button click in Mattermost → signed webhook →
  verbatim capture to `ingest.raw_event` → worker maps it (actor link, manual
  enrichment, agent approve/reject).

Marketing-first PHI posture: messages carry `person_uid` + a deep link only,
never names/phones/clinical text (`phi_mode="deidentified"` default; `phi_mode`
"full" reserved for the clinical phase). Mattermost is an **internal team**
channel — NOT a patient-facing replacement for WhatsApp/SMS.

## 2. How it works (component map)

```
DOMAIN event ──► NotificationEventService.emit(event_type, ctx, person_uid)
                   │  rules: integrations.notification_rule (conditions + channel + template)
                   │  render: de-identified (render.py)  →  integrations.notification_outbox (pending)
                   ▼
        [worker] drain_notification_outbox  ──ChatProvider.post()──►  Mattermost
                                                                        │ button / reply
        apps/api/routers/chat_inbound.py  ◄── signed webhook (token verify, fail-closed) ──┘
                   │ redact token, verbatim
                   ▼
        ingest.raw_event (source="mattermost")
                   │
        [worker] map_chat_inbound  ──► actor link  +  agent-action resolution
                                          └─ approve → EnrichmentService.add_annotation (worker boundary)
```

| Concern | Code |
|---|---|
| Provider adapter | `packages/integrations/chat/mattermost.py` (`MattermostAdapter`), `resolver.py` |
| Outbound rules + render | `chat/events.py`, `chat/conditions.py`, `chat/render.py`, `chat/event_service.py`, `chat/seeds.py` |
| Outbox + dispatch | `integrations.notification_outbox/_rule`, `notification_{service,repository,schemas}.py`, `apps/worker/jobs/notification_dispatch.py` |
| Inbound | `apps/api/routers/chat_inbound.py`, `chat/inbound.py`, `apps/worker/jobs/chat_inbound_map.py` |
| Enrichment | `packages/enrichment/` (`enrichment.record_annotation`), `apps/api/routers/enrichment.py` |
| Agent HITL | `chat/agent_actions.py` (`integrations.agent_action_proposal`), `packages/agent_runtime/agent_chat_actions.py` |
| Migrations | `a7b8c9d0e1f2`, `4fe9f2b9f55a`, `37f5ec4af909`, `b69bce1e2195` |

**Architecture invariants honored:** Mattermost has its OWN DB (separate from the
canonical 8 schemas, #1); no business logic in routes (#5, outbox+worker);
agents never touch the DB (#6, execution at the worker boundary);
`integrations` MUST NOT import `enrichment` (orchestration is in the worker);
secrets in `tenant.integration_credential` (#10).

## 3. Credentials (per tenant, encrypted)

All in `tenant.integration_credential` (Fernet-encrypted), resolved via
`IntegrationCredentialService`:

| provider_kind | credential_kind | payload | used by |
|---|---|---|---|
| `mattermost` | `api_key` | `{base_url, bot_token}` (+ optional `action_callback_base`) | outbound `resolver.py` → adapter |
| `mattermost` | `webhook_secret` | `{token}` (the MM outgoing-webhook / action token) | inbound token verification |

- `base_url` is what the API process can reach (local in-host: `http://127.0.0.1:8065`).
- `action_callback_base` is what the Mattermost SERVER can reach back (local:
  `http://host.docker.internal:8000`; prod: the public API host). Defaults to
  `http://host.docker.internal:8000` if omitted.
- The inbound `webhook_secret` token is **separate** from the bot `api_key` so
  rotating one does not disturb the other. Inbound resolves tenant by matching
  the presented token against active `webhook_secret` rows (constant-time;
  fail-closed on zero or cross-tenant ambiguity).

## 4. Local setup + testing

### 4.1 Bring up Mattermost (one-time)
```
docker compose -f infra/docker/docker-compose.yml --profile chat up -d mattermost
```
Apple Silicon prerequisites (the image is amd64-only) — both are already in the
compose, but Rosetta is a Docker Desktop GUI toggle:
- **Docker Desktop → Settings → General → "Use Rosetta for x86/amd64 emulation"**
  (needs Apple Virtualization framework). Without it the Go binary crashes under
  qemu (`fatal error: lfstack.push`).
- `MM_SERVICESETTINGS_ALLOWEDUNTRUSTEDINTERNALCONNECTIONS` (already set) — without
  it Mattermost refuses to call our private inbound URL ("address forbidden").

Then at `http://127.0.0.1:8065`: create admin → Team → bot account (Integrations
→ Bot Accounts) → copy token → create `#leads` channel → add the bot.

### 4.2 Configure the outgoing webhook (inbound)
Integrations → Outgoing Webhooks → Add: Channel `leads`, Content-Type
`application/x-www-form-urlencoded`, Callback URL
`http://host.docker.internal:8000/integrations/chat/mattermost/webhook`. Copy the
generated Token → store as the `mattermost`/`webhook_secret` credential.

### 4.3 Store credentials + seed rules (example, dev)
Use `IntegrationCredentialService.upsert(tenant_id, "mattermost", "api_key",
{"base_url": "http://127.0.0.1:8065", "bot_token": ...})` and
`(..., "webhook_secret", {"token": ...})`, then
`seed_all_notification_rules(session, tenant_id)`.

### 4.4 Test checklist (all verified live 2026-06-15)
1. **Outbound adapter:** `MattermostAdapter(base_url, bot_token).post(ChatMessage(...))` → message in `#leads`, `ok=True`, no token logged.
2. **Full outbound pipeline:** `NotificationEventService.emit("lead.created", ctx, person_uid=...)` → `notification_outbox` row (de-identified) → `drain_notification_outbox({})` → post. Verify the rendered payload has ONLY `person_uid` + deep link.
3. **Inbound reject:** POST to `/integrations/chat/mattermost/webhook` with a wrong/missing token → 401, nothing captured.
4. **Inbound accept:** correct token → 200 + a `raw_event` (`source="mattermost"`); the stored payload has the token **redacted**.
5. **Agent HITL:** `AgentChatActions.propose_annotation(...)` posts Approve/Reject → click Approve → action captured → run `map_chat_inbound` (or the worker cron) → proposal `executed` + `enrichment.record_annotation` row (`source="agent"`).

> NOTE: arq has no hot-reload. After changing worker/ingest code, restart it:
> `pkill -f "arq apps.worker"` (dev-up.sh respawns on current code).

## 5. Production bring-up (Block I / ENG-442) — plan

Strictly per `docs/DEPLOYMENT_RULES.md`; isolated from feature PRs.

### 5.1 Topology
- **Mattermost is stateful (websockets) — NOT scale-to-zero Cloud Run.** Run the
  official image on a host: a small GCE VM (or the existing prod compose host)
  via `docker-compose.prod.yml`, min-instances=1.
- **Its own database**, physically separate from the canonical Cloud SQL DB
  (separate Cloud SQL DB or instance — OPEN DECISION #4).
- File store in **GCS**; DB backup into the existing GCS backup contour.
- Public `chat.*` subdomain behind TLS (OPEN DECISION #3 — host shape + DNS/TLS).
- The inbound callback URL becomes the public API host (set `action_callback_base`
  + the outgoing-webhook callback to `https://<api-host>/integrations/chat/mattermost/...`).

### 5.2 Hard prerequisites / checklist
- [ ] **Alembic single head** on the deploy branch: `alembic heads` shows exactly
      one, and `alembic upgrade head` succeeds from the prod DB's current revision.
      (Cross-branch caveat: other epics — e.g. lead-attribution — may add migrations;
      reconcile to a single head before prod. The messenger chain itself is single-headed
      at `b69bce1e2195`.)
- [ ] Mattermost version tag pinned + upgrade cadence agreed (OPEN DECISION #2).
- [ ] Tenant credentials (`mattermost`/`api_key` + `/webhook_secret`) stored in
      prod `tenant.integration_credential` (NOT Cloud Run env).
- [ ] `action_callback_base` set to the public API host; Mattermost
      `AllowedUntrustedInternalConnections` adjusted (prod uses the public host,
      not host.docker.internal).
- [ ] Message/file retention + backup policy (OPEN DECISION #6).
- [ ] Worker runtime that actually runs `drain_notification_outbox` +
      `map_chat_inbound` in prod (note: `drain_outbound_queue` for email is
      currently PAUSED in prod per `apps/worker/CLAUDE.md` ENG-172 until an
      always-on background runtime + Memorystore exists — the messenger drains
      need the same runtime; confirm before relying on outbound/inbound in prod).
- [ ] De-identified `phi_mode` confirmed for prod (full mode is a separate
      doctor/compliance decision).

### 5.3 Open decisions to close before/with prod
1. `record_annotation` domain — RESOLVED (new `enrichment` schema, shipped).
2. Mattermost version pin + cadence.
3. Prod host shape + `chat.*` hostname/TLS.
4. Prod Mattermost DB placement (separate Cloud SQL DB vs instance).
5. `event_type` taxonomy — defaulted (`lead.created` / `opportunity.stage_changed`
   / `ownership.changed` / `ingest.sync_failed`); confirm.
6. Retention/backup policy.

## 6. Known gotchas (this stack)
- **Rosetta** required for the amd64 Mattermost image on Apple Silicon.
- **AllowedUntrustedInternalConnections** required for outgoing webhooks to reach
  a private/loopback API host.
- **`ingest.list_unprocessed(source=...)`** — the chat inbound worker MUST filter
  by source; the global unprocessed backlog is >1M rows and would otherwise
  starve the Mattermost rows (fixed; keep the filter).
- **Alembic via `cd packages/db`** fails (Settings loads `.env` by cwd) — drive
  alembic via its Python API from repo root with an absolute `script_location`,
  or run from repo root. See `feedback_dev_traps` memory.
- **arq no hot-reload** — restart the worker to pick up code changes.

## 7. Remaining work (tickets)
- **ENG-443 (D2):** wire `opportunity.stage_changed`, `ownership.changed`,
  `ingest.sync_failed` emits at the documented call-sites (ops.service upsert
  return points; ingest_scheduled/backfill failure sites).
- **ENG-442 (I):** production infra (this §5).
- **Frontend Zod `ProviderSchema`** — add `mattermost` (apps/web) to mirror
  `PROVIDER_KINDS` so the credential UI lists it.
