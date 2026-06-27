# Strategic Roadmap — Fusion CRM

> **Status:** living document, v0.1 (2026-04-30).
> **Update rule:** revise at the end of any phase, or any time we make a scope
> shift, or whenever reality contradicts the plan. Plans rot if they aren't
> tended; an outdated roadmap is worse than no roadmap.

---

## 0. Mission

> **We are building the data backbone of an AI-native Dental Implant Clinic OS.**
> Not a CRM. Not an EHR add-on. An operating system where AI agents and humans
> together execute clinic work end-to-end through closed loops, with every
> action audited and every active patient having a next step.

Strategic doctrine source:
[`AI_Native_Dental_Implant_Clinic_White_Paper_v0_1.docx`](../AI_Native_Dental_Implant_Clinic_White_Paper_v0_1.docx).
Data-model doctrine source:
[`ai_context_workflow_whitepaper.md`](../ai_context_workflow_whitepaper.md).
Agent/workflow doctrine source:
[`agent_driven_workflow_layer_whitepaper.md`](../agent_driven_workflow_layer_whitepaper.md).

When this roadmap conflicts with these whitepapers, the whitepaper wins
unless we record the override here.

---

## 1. Two-layer company model

```
┌─────────────────────────────┐    ┌────────────────────────────────┐
│  Layer 1 — Growth / CRM     │    │  Layer 2 — Clinical            │
│  (PHI-free)                 │    │  (PHI)                         │
│                             │    │                                │
│  - Salesforce as SOR        │    │  - CareStack as SOR            │
│  - Leads, campaigns, calls  │    │  - Medical records, imaging    │
│  - SMS, attribution         │    │  - Treatment plans, surgery    │
│  - Marketing/ops AI agents  │    │  - Post-op, consents           │
│                             │    │  - Clinical AI agents          │
└──────────────┬──────────────┘    └──────────────┬─────────────────┘
               │                                  │
               └──────────┐         ┌────────────┘
                          ↓         ↓
                ┌─────────────────────────┐
                │  Controlled event layer │
                │  (safe summaries +      │
                │   aggregated events)    │
                └─────────────────────────┘
```

Growth never sees raw PHI. Clinical never sees raw marketing. The shared
event layer carries minimum-necessary, aggregated, or de-identified bridges.

---

## 2. Core entity model

The data model is built on **5 root entities + 3 higher-level structures**:

```
Person      — the patient/lead/contact (one per real human, person_uid)
Actor       — executor of work; human | ai | system | external_service
Event       — a raw fact that happened
Context     — AI-/rule-derived meaning extracted from events (versioned)
Action      — a task / executable step

Flow        — a workflow tree (with branches), moves a Person toward a goal
Encounter   — a bounded episode (consultation, surgery visit, financing call)
Insight     — higher-level pattern detected across multiple events / contexts
```

Operating loop:

```
Raw Event → Context → Decision → Branch / Flow → Action → Result → New Event
```

Context is a **hypothesis**, not permanent truth — versioned, can be
superseded as new events arrive. Workflows are **trees**, not linear
sequences — new contexts create new branches. Segments are **derived**, not
source-of-truth.

---

## 3. Schema map

| # | Schema | Purpose | Status (2026-04-30) |
|---|---|---|---|
| 1 | `identity` | One canonical Person + external IDs + merges | Live (`person`, `person_identifier`); `source_link`, `merge_event` planned |
| 2 | `actor` | Humans + AI agents + system jobs as first-class actors; capabilities; source-system mappings | Planned (Phase 1) |
| 2a | `auth` | Polymorphic credentials + sessions for staff (Actor-backed), API keys for MCP clients, portal accounts for future patients | Planned (Phase 1) |
| 3 | `ingest` | Raw inbound payloads, append-only | Live (`raw_event`); `sync_job` planned |
| 4 | `interaction` | Semantic events with content (transcripts, messages, recordings) | Planned (Phase 1) |
| 5 | `context` | Versioned AI-derived facts + context graph | Planned (Phase 1) |
| 6 | `workflow` | Flow definitions, instances, nodes, action steps, escalations | Planned (Phase 1) |
| 7 | `encounter` | Consultation / surgery / call episodes with participants and artifacts | Planned (Phase 1) |
| 8 | `ops` | PHI-free CRM data | Live (`lead`, `followup_task`); `account`, `pipeline_stage`, `safe_summary`, `revenue_event` planned |
| 9 | `phi` | Clinical PHI behind `PhiService` | Live (`patient_profile`, `consultation`); `appointment`, `treatment_case`, `transcript_raw`, `extracted_fact` planned |
| 10 | `segmentation` | Derived segments — definitions, membership, refresh jobs | Planned (Phase 5) |
| 11 | `insight` | Patterns + recommendations + reprocessing | Planned (Phase 5) |
| 12 | `audit` | Append-only audit trails — multiple kinds | Live (`access_log`); `agent_tool_call`, `action_audit_log`, `data_access_log` planned |
| 13 | `integrations` | Provider plumbing only (no domain data) — accounts, mappings, sync runs, cdc cursor, external entities | Planned (Phase 1) |

The catalog of live tables and external-ID kinds is at
[`docs/data-model/CATALOG.md`](./data-model/CATALOG.md). It is the live
single-source-of-truth and gets updated in the same commit as any DDL change.

---

## 4. Parallel workstreams

The roadmap below is sequential for backend phases, but the system has three
**parallel workstreams** that run alongside the backend rather than after it.
This is by design — the system is not "backend, then everything else".

| Workstream | What | Where it starts | Why |
|---|---|---|---|
| **A. Backend phases** | The phased backend build (§5 below) | Phase 0 done; Phase 1 in progress | Foundation — others depend on the data model |
| **B. Operator frontend** | Staff web UI: dashboard, person card, live SLA queue, flow tree, context review, encounter detail, segments, agent management | Starts in Phase 1 alongside backend (minimal vertical slice) | The UI's existence forces real workflows to surface in the API; we don't want to discover frontend needs after the API ossifies |
| **C. MCP server** | A separate process at `apps/mcp/` exposing the service layer to external Claude Code / Codex / future AI clients | Starts in Phase 1 alongside backend | Lets the user (and any AI dev tool) actually QUERY/EDIT the CRM during development. Same auth shape as staff/internal tools (api_key + actor + capabilities) |
| **D. Patient portal (future)** | Patient-facing portal for contacts who reach the operation phase: their treatment plan, post-op instructions, imaging, scheduling | Phase 11 (deliberate placeholder) — schema reserved now | Patients eventually see their own (potentially-PHI) data; design is forward-compatible from day one via `auth.portal_account` and polymorphic `auth.credential`/`auth.session` |

**Implication for v0.2 schema design:** the `auth` schema must already
support all four subject types (staff, AI internal, MCP client, future
patient). That's why `auth.credential` and `auth.session` are polymorphic
(`subject_type IN ('actor', 'portal_account')`) from day one — no rework
when the patient portal ships.

**Implication for app layout (`apps/`):** four reserved directories.
`apps/api/` and `apps/worker/` exist; `apps/mcp/` and `apps/web/` are
created in Phase 1. `apps/portal/` is reserved (empty stub `CLAUDE.md`)
for the patient portal.

```
apps/
├── api/      FastAPI HTTP surface                      (live)
├── worker/   arq background jobs                       (live)
├── mcp/      MCP server for external AI clients        (Phase 1, new)
├── web/      Operator/staff frontend (Next.js)         (Phase 1, new)
└── portal/   Patient portal (Next.js)                  (Phase 11, reserved)
```

---

## 5. Phases

Each phase is **scoped**, has an **exit criterion**, and is **mutable**: when
testing or real use teaches us something, we revise the phase before
continuing. Phase numbering is logical, not calendar-fixed.

### Phase 0 — Bootstrap ✅ DONE

Repo scaffolded, docker compose runs (postgres :5434, redis :6380, api :8000),
initial alembic migration applied, the five MVP schemas live with their core
tables.

**Exit criterion:** ✅ `make up && curl /docs` returns the API, alembic_version
shows the initial revision.

### Phase 1 — Vertical slice: SF + CareStack data live on UI (current)

> **Pivoted 2026-05-01 → 2026-05-02.** Was originally "Strategic schema v0.2" —
> build all 14 schemas at once. Re-scoped to a **depth-first end-to-end
> vertical slice**: pick one provider-data-on-UI path and build only the
> packages, endpoints, and pages it needs. Detailed plan in
> [`docs/plans/2026-05-01-phase1-vertical-slice.md`](./plans/2026-05-01-phase1-vertical-slice.md).
>
> The full v0.2 schema design (`docs/plans/2026-04-30-full-schema-v0_2.md`)
> stays as the north star — we just implement subsets per milestone instead of
> all at once. Each future phase ships only the schemas/packages it needs.
>
> **Domains deferred from Phase 1 to their natural milestones:** `interaction`
> (Phase 3), `context` (Phase 4), `workflow` (Phase 5), `encounter` (Phase 6),
> `segmentation` and `insight` (Phase 7). All `phi.*` clinical schema
> additions deferred to Phase 6+. Phase 1 ships only the slice subset.
>
> **Provider posture (founder direction 2026-05-05):** Phase 1 connects
> directly to **production** Salesforce org and CareStack tenant, but
> **strictly read-only**. No writes back to providers from any phase before
> agents are operational. Phase 2 (CDC + push) is therefore frozen until
> Phase 5+. See memory `feedback_production_readonly_pull` for the 5 hard
> guard-rails.
>
> **Speed-to-lead refinement (2026-05-14):** Salesforce `Lead.created` is a
> business-critical exception to ordinary scheduled sync latency. The target is
> seconds-level ingestion for the first call/SMS context. This remains
> read-only toward Salesforce: receive `LeadChangeEvent`, store raw event,
> hydrate the full Lead, build semantic `speed_to_lead_context`, and trigger
> controlled outreach. See `docs/PROVIDER_INGESTION_STRATEGY.md`.
>
> **Context/taxonomy governance (2026-05-15):** Agent learning, taxonomy
> improvements, and strategy changes must pass through human approval before
> changing production behavior. See
> `docs/architecture/CONTEXT_ARCHITECTURE.md`,
> `docs/architecture/SEMANTIC_INTERPRETATION.md`, and
> `docs/governance/TAXONOMY_GOVERNANCE.md`.
>
> **Tenant credential UI (2026-05-15):** Provider credentials are company
> settings, not deploy-time env vars. Early Phase 1 must expose Settings /
> Integrations flows for Salesforce, CareStack, and Twilio credentials backed
> by encrypted `tenant.integration_credential`. Env vars remain temporary
> bootstrap/local-dev fallback only.

The agent-driven workflow layer is also a north star, not Phase 1 scope.
Phase 1 may create the durable inputs future agents need, but it does not ship
the workflow runner, agent decisions, approval queue, timer runner, or
staff-created agent builder. The integration plan is
[`docs/plans/2026-05-04-agent-driven-workflow-layer-integration.md`](./plans/2026-05-04-agent-driven-workflow-layer-integration.md).

**Slice work (20 task units, one PR each — see plan §3):**

*Backend (workstream A):*

1. **Two foundational docs** (this and `WORKFLOW.md`). ✅
2. **Full schema design doc** at `docs/plans/2026-04-30-full-schema-v0_2.md`. ✅
3. **Phase 1 vertical-slice plan** at
   [`docs/plans/2026-05-01-phase1-vertical-slice.md`](./plans/2026-05-01-phase1-vertical-slice.md). ✅
4. **Slice domain extensions:**
   - `interaction` (slim — `interaction.event` only; full package deferred to Phase 3) — D1
   - `identity.source_link` + `identity.merge_event` — D2
   - `ops.account` + `OpsService.upsert_lead` change-detection contract — D3
   - `ops.consultation` (marketing view of CareStack appointment; clinical
     view deferred to Phase 6) — D4
5. **Glue (already shipped):** `init-schemas.sql` (8 slice schemas),
   `DOMAIN_SCHEMAS`, `registry.py`, `core/config.py`, `docker-compose.yml`,
   `pyproject.toml` (`cryptography>=43`, `argon2-cffi>=23`). ✅
6. **Per-domain alembic migrations** — `interaction`, `identity` ext,
   `ops` ext (account + consultation). No big-bang; each domain ships its
   own revision when slice demands it.
7. **Salesforce Lead pull worker (W1)** — read-only; PKCE OAuth via FUS-15;
   `was_changed` change-detection drives `interaction.event` emission.
8. **CareStack appointments + patient contact pull worker (W2)** —
   read-only; marketing-only normalization (no clinical content);
   expanded log-redaction tests.
9. **Tenant integration credential UI (C1)** — Settings / Integrations page
   can record, validate, list, set-default, revoke, and rotate tenant-owned
   provider credentials. Initial providers: Salesforce, CareStack, Twilio.
   Backend stores encrypted payloads in `tenant.integration_credential` and
   returns metadata only.

*API (workstream A continued):*

9. **Auth endpoints** — `POST /auth/login`, `POST /auth/logout`, `GET /me`
   via `auth.session` cookie (A1).
10. **Person endpoints** — `GET /persons/{uid}`,
    `GET /persons/{uid}/timeline`, `GET /dashboard/summary` (A2).
11. **Inspector endpoints (env-gated)** —
    `GET /dev/inspector/{provider}/latest` returns 404 unless
    `ENVIRONMENT=local`; carve-out documented in
    `packages/ingest/CLAUDE.md` (A3).
12. **Integrations connect/status endpoints** — `POST /connect/start`,
    SF callback, CareStack `/api-key`, `GET /integrations`,
    `POST /sync` (A4).
13. **Tenant credential endpoints** — authenticated tenant-admin routes for
    provider credential upsert/test/revoke/set-default/list. Payloads never
    leave the API after submission; responses expose metadata only.

*MCP server (workstream C):*

13. **`apps/mcp/` scaffold + bearer auth via `auth.api_key`** (M1).
14. **4 read-only MCP tools** — `resolve_person`, `get_person_timeline`,
    `list_recent_leads`, `get_inspector_payload` (last one env-gated at
    registration time) (M2). MCP write tools deferred to Phase 5+.
15. **`make mcp-key` CLI + connection guide** (M3).

*Operator frontend (workstream B):*

16. **`apps/web/` scaffold** — Next.js 14 + Tailwind + auth shell (F1).
17. **Login page** (F2).
18. **`/integrations` Connect/status page** — provider connection UI
    sequenced before dashboard (F5).
19. **Dashboard + Person card** (F3).
20. **Inspector pages** (env-gated via Next.js server `notFound()`) (F4).

*Patient portal (workstream D, reservation only):*

21. **`apps/portal/`** — empty stub directory with placeholder
    `CLAUDE.md` for M11 (already shipped). ✅

*Exit verification:*

22. **End-to-end smoke + carve-out closure rehearsal** (V1).

**Exit criterion (12 items per plan §8):**

1. R1 merged; this section's exit criterion matches the slice scope.
2. Migrations from D1-D4 applied cleanly on a fresh DB. **No `phi.*`
   migration in Phase 1.**
3. `apps/api`, `apps/worker`, `apps/mcp` all start in `docker compose up`.
4. `apps/web` builds and `npm run dev` serves `/login`.
5. **Connect-via-UI works:** logged-in operator visits `/integrations`,
   completes SF OAuth and CareStack API-key flow, both rows show
   `connected`. Tokens encrypted at rest via FUS-22 `EncryptedString`;
   no plaintext in API responses or logs.
6. W1 was triggered via "Sync now" → produced ≥ 1 `identity.person`,
   ≥ 1 `ops.lead`, ≥ 1 `interaction.event` of `kind='lead_*'`.
7. W2 was triggered via "Sync now" → produced ≥ 1 `ops.consultation`,
   ≥ 1 `interaction.event` of `kind='consultation_*'`. The
   `ops.consultation.raw_marketing` payload contains ONLY allowlisted
   fields (verified by inspecting one row).
8. Operator UI shows non-zero dashboard counts → person card shows
   timeline → `interaction.summary` contains zero PII (verified by
   inspection of rendered text) → Inspector shows raw payload for both
   providers (visible because `ENVIRONMENT=local`).
9. MCP client (Claude Code from another machine, `ENVIRONMENT=local`)
   connects, calls all four read tools, all leave
   `audit.agent_tool_call` rows.
10. **Sync journaling + audit:** `integrations.sync_run` rows exist for
    both W1 and W2 invocations (closed `success`); corresponding
    `audit.access_log` rows from `AuditService.log_sync_run_summary`.
11. `docker compose logs api worker mcp` grep for the full PII fixture
    set returns ZERO matches; same grep for OAuth tokens / api keys
    returns ZERO matches.
12. **Carve-out closure rehearsal** (V1 step 8): with
    `ENVIRONMENT=staging`, the API endpoint, the `apps/web` Inspector
    route, and the MCP `get_inspector_payload` tool ALL become
    unreachable (404 / 404 / not-listed). Verified, not just
    documented.

When (1)–(12) hold, V1 PR merges and Phase 1 closes.

### Phase 2 — Salesforce + CareStack integration transport

> **Frozen 2026-05-05.** Per founder direction, Phase 1-4 stay strictly
> read-only against production providers; writes (push, CDC streaming,
> create/update through provider APIs) are deferred until Phase 5+ when
> agents are operational and demand them. Phase 1 W1/W2 already cover the
> read-only pull use case via periodic poll. Revisit this phase when
> Phase 5 kicks off and write paths become genuinely needed.

Now the providers can actually push data into the canonical model.

**Work:**

- `packages/integrations/crypto.py` (Fernet + `EncryptedString`).
- `packages/integrations/base.py` — `BaseAuth` hierarchy (`PKCEOAuth`,
  `StandardOAuth2`, `PasswordGrantAuth`) + `BaseProviderClient` Protocol
  (resource-oriented: `list / get / create / update / describe`).
- `packages/integrations/salesforce/` — PKCE OAuth, REST client, sync
  pipelines (pull / push), CDC streaming via `aiosfstream`, Outbound Message
  webhook receiver.
- `packages/integrations/carestack/` — Password Grant OAuth, REST client,
  polling-only Sync APIs, Patient → `phi.patient_profile` via
  `PhiService.upsert(...)`.
- `apps/api/routers/integrations/{salesforce,carestack}.py`.
- `apps/worker/jobs/{salesforce,carestack}.py` — pull cron, push, refresh.
- AI-tool wrappers in `packages/tools/integrations/`.

Detailed design: [`docs/plans/2026-04-30-salesforce-integration-design.md`](./plans/2026-04-30-salesforce-integration-design.md)
(also covers CareStack via the §11 "Future providers" matrix).

**Exit criterion:**
- `POST /integrations/salesforce/connect` → OAuth complete → status returns `connected: true`.
- A Salesforce Lead created in the SF UI appears in `ops.lead` within ≤ 1 min (CDC).
- A CareStack Patient pulled appears in `phi.patient_profile` (via PhiService) and is keyed by `identity.person_identifier(kind='carestack_patient_id')`.
- `audit.access_log` has rows for OAuth + each push/pull batch.

### Phase 3 — Interaction ingestion

Calls (Twilio / Vapi / RingCentral), SMS, email, web forms.

**Work:**

- Ingestion adapters per channel into `interaction.event` + `interaction.event_content` + raw payload to `ingest.raw_event`.
- Recording / transcript artifact storage (GCS bucket) with PHI flag.
- Person resolution rules: phone → `identity.person_identifier(kind='phone')`, fallback to lead-creation.
- Webhook routes for each channel; signature verification.
- Worker jobs for transcript pull, recording fetch.
- Event taxonomy aligned with the agent-driven workflow layer: calls, SMS,
  appointment changes, manual tasks, provider sync changes, and form submits
  become durable workflow inputs.
- No agent execution yet. Phase 3 produces normalized events and artifacts
  that later workflow rules can subscribe to.

**Exit criterion:**
- Inbound SMS to clinic number lands as `interaction.event(event_type='sms_received')` linked to a Person.
- Vapi-completed call writes a `transcript_artifact` and an `event(event_type='call_completed')`.
- Person card timeline shows the events.

### Phase 4 — Context extraction layer

AI begins extracting meaning from events. The system stops being a passive ledger.

**Work:**

- LLM-driven extraction service: event → list[context_fact] per the JSON
  schema in whitepaper Appendix D.
- `context_fact` writes are versioned; superseding is explicit.
- Confidence + urgency + SLA fields populated.
- Live SLA queue endpoint and worker that watches due times.
- First taxonomy of context types (intent / objection / urgency / emotion /
  stage_signal / outcome / risk / opportunity / clinical_phi / ops_safe / unknown).
- Human review UI hooks (API only first; UI later).
- Context packages for future agents: structured facts, confidence, urgency,
  SLA hints, source-event references, and data-class/PHI flags.
- No tool execution yet. Phase 4 produces classified decision inputs, not
  autonomous actions.

**Exit criterion:**
- Inbound SMS "Where is my appointment?" creates a `context_fact(intent=appointment_confusion, urgency=critical, sla_minutes=5)` within seconds.
- The live queue endpoint surfaces it.

### Phase 5 — Workflow / next-action engine

Every active person gets a flow and a next action; flows can branch.

**Work:**

- `flow_definition` seed library (lead follow-up, no-show recovery, price recovery, post-op cycle, etc.).
- Decision engine: context → routing → action_step assigned to actor (human or AI) with SLA.
- Branch creation on context-not-in-expected-set rule.
- Escalation rules on SLA expiry.
- "Active person without next action" detector + dashboard endpoint.
- Tool layer: `create_action`, `complete_action`, `create_flow_branch`, `assign_actor`, `trigger_flow` become live.
- Agent-driven workflow foundation from
  [`2026-05-04-agent-driven-workflow-layer-integration.md`](./plans/2026-05-04-agent-driven-workflow-layer-integration.md):
  `interaction.event` / `context.context_fact` subscriptions, workflow runner,
  `workflow.timer`, `workflow.agent_decision`, `workflow.approval_request`,
  and service-backed tools.
- Policy preflight stub before every tool call: role, capability, data class,
  risk category, and human-approval requirement.
- Canonical execution loop:
  `Event -> State -> Agent Decision -> Policy -> Tool -> Audit -> Event`.

**Exit criterion:**
- A new `ops.lead` triggers a `flow_instance(flow_definition='lead_followup')` with the first `action_step` queued and assigned.
- An overdue action escalates and lands on a supervisor's queue.

### Phase 6 — Encounters

Consultation episodes — bigger than single events.

**Work:**

- `encounter` + `encounter_participant` + `encounter_artifact` populated from CareStack appointments and Vapi/in-person consultation transcripts.
- Outcome extraction (won / lost / pending; reason category + subtype).
- PHI summary vs ops-safe summary split (deferred runtime gating still TODO).
- Encounter detail UI / API endpoint.

**Exit criterion:**
- A completed CareStack consultation creates an `encounter(type='consultation')` with participants linked and an `outcome` row populated.
- The downstream flow (price recovery / surgery scheduling / reactivation) is triggered correctly.

### Phase 7 — Segments + insights + reprocessing

Operational intelligence layer.

**Work:**

- `segment_definition` library + materialized membership refresh job.
- `insight` generator over the context graph + encounter outcomes.
- Reprocessing job: re-extract context from old transcripts when prompts/models improve.
- Tools layer: `create_segment`, batch query tools.

**Exit criterion:**
- Segment "consultation completed but no surgery scheduled, > 14 days" populates and triggers a reactivation flow per matched person.
- Reprocessing job over last 90 days surfaces N new insights documented in a report.

### Phase 8 — HIPAA runtime gating (deferred work)

Pick up the runtime guards we deferred during structural design.

**Work:**

- `Principal.can_read_phi()` actually denies. `PhiService.*` methods enforce.
- Vendor BAA-eligibility wrapper around all LLM / external API calls.
- Data-class sentinel at every tool-call boundary (deny path active).
- Per-actor capability matrix.
- Zero-retention / approved-endpoint routing.
- HIPAA risk analysis written; staff training materials drafted.
- Policy/guardrail layer from the agent-workflow doctrine: do-not-call,
  do-not-SMS, office-hours/quiet-hours, restricted-write approval, low
  confidence approval, and deny-by-default for unknown tools or unknown data
  classes.

**Exit criterion:**
- A non-clinical principal calling `PhiService.get_patient(...)` gets a 403.
- An LLM call attempting to send PHI to a non-BAA endpoint is denied at wrapper level.
- Audit logs show the denials.

### Phase 9 — UI / dashboards (full operator surface)

The minimal `apps/web/` from Phase 1 grows into a full operator surface.
By this point the backend has flow / context / encounter / segment data
worth surfacing.

**Work (extends what shipped in Phase 1):**

- Command center / dashboard (rich, real-time vs. Phase-1 summary cards).
- Patient/person card with full timeline, context history, action buttons.
- Live SLA queue with assign/escalate/complete controls.
- Flow tree view (visual branches).
- Context review panel — humans correct AI interpretations.
- Encounter detail page.
- Segment builder.
- Actor workload + automation coverage view.
- Agent management UI (capabilities, risk levels, evals, deployment).
- Human approval queue for `workflow.approval_request`.
- Agent decision trace linked to context, action steps, tool calls, and action
  results.
- Tool-call drilldown for `audit.agent_tool_call`, with sanitized inputs and
  outputs.

Detailed wireframes: whitepaper §17 + Doc 1 §12.

**Exit criterion:** all the above screens deliver their primary action with
real data; coordinators can run a shift on the system.

### Phase 10 — Software factory

System improves itself.

**Work:**

- Per-agent eval sets + regression harness.
- Release process for AI agents (rollout, rollback, telemetry).
- Token-economics dashboard.
- Spec-first workflow tooling (humans write spec → AI implements → eval → ship).
- Multi-clinic / multi-tenant cutover (`company_uid` from stub to real).
- Staff agent builder constrained by role, capability, policy, output schema,
  approval thresholds, eval set, release status, and rollback record.
- Workflow template builder for governed `workflow.flow_definition` changes.

**Exit criterion:** every PHI / clinical / patient-communication agent has an
eval suite, a release record, and live performance metrics.

### Phase 11 — Patient portal (placeholder)

Patient-facing portal at `apps/portal/`. Patients who have reached the
operation stage (or earlier, if business decides) get a login that shows
their treatment plan, post-op instructions, scheduling, imaging, financing
status, and approved patient communications. Likely PHI — runtime gating
must be live before this phase ships, so this depends on Phase 8 being
complete.

**Work:**

- `apps/portal/` Next.js app — separate from `apps/web/` so the patient
  surface and the staff surface have independent styling, navigation, and
  most importantly **independent auth boundaries**.
- Patient login uses `auth.portal_account` + `auth.credential(subject_type='portal_account')`.
- Patient sessions: `auth.session(subject_type='portal_account')`.
- Read-side endpoints under `/portal/*` that go through `PhiService` with
  the patient as the principal — the runtime gate (Phase 8) will check that
  `auth.permission_grant` permits the patient to read their own records (and
  nothing else).
- Email/SMS invite flow: clinic staff invites a patient → portal account
  created in `invited` state → patient completes registration → status
  `active`.
- Security: rate limiting on login, email verification required, MFA
  optional but recommended, all `audit.data_access_log` rows tagged with
  `principal_id = portal_account.id` so portal reads are distinguishable
  from staff reads in audit reports.

**Exit criterion:** an invited patient can log in, see their treatment case
status, post-op instructions, and upcoming appointments — and is denied
access to anything else. All accesses appear in `audit.data_access_log`.

---

## 6. Status snapshot

```
Phase 0  ████████████████████████████████ 100%   ✅ Bootstrap
Phase 1  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░  15%   🔄 Vertical slice plan finalized; 20 tickets cut (depth-first)
Phase 2  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      Salesforce + CareStack transport
Phase 3  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      Interaction ingestion
Phase 4  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      Context extraction
Phase 5  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      Workflow / next-action engine
Phase 6  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      Encounters
Phase 7  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      Segments + insights
Phase 8  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      HIPAA runtime gating
Phase 9  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      UI / dashboards
Phase 10 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      Software factory
Phase 11 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      Patient portal (depends on Phase 8)
```

Workstreams (parallel):
```
A. Backend phases    — see bars above
B. Operator frontend ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10%   🔄 starts in Phase 1, scoped MVP slice
C. MCP server        ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10%   🔄 starts in Phase 1, exposes initial tools
D. Patient portal    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%      Phase 11 — schema reserved now
```

Update the bars at the end of each phase or at any meaningful milestone.

---

## 7. Parking lot — open questions

Things we know we need to answer, but not now. Move into a phase when ready.

- **Multi-tenant cutover.** When does `Company` become a real entity?
  `IntegrationAccount.company_uid` is currently a GLOBAL stub.
- **Bulk API for Salesforce.** SOQL pagination is fine for < 50k records.
  When the first real org needs more, switch to Bulk API 2.0.
- **Cross-provider identity dedup.** Email/phone match is enough for v1. Real
  fuzzy dedup is its own project.
- **Storage and retention policy** for raw audio, transcripts, recordings.
  Needs legal/compliance review.
- **CareStack write operations** scope. Confirm which of {create patient, create
  appointment, update appointment, add note, attach docs} are stable enough
  to use.
- **State / jurisdiction.** Which state's dental board rules apply? What
  patient-consent disclosure language do we use for AI-assisted communication?
- **Pricing model.** Cash-pay / insurance / financing-heavy / hybrid? Affects
  the financing flow design.
- **Imaging integration.** How and when do we ingest scans / X-rays?
- **Policy DSL location.** Decide whether policy lives in Python policy
  objects, `auth.permission_grant`, workflow metadata, or a dedicated table.
- **Timer scheduler semantics.** Decide whether Phase 5 timers use database
  polling, Redis/arq scheduled jobs, or a hybrid.
- **Staff agent-template safety review.** Define who can create, approve,
  publish, pause, and retire staff-created agents.

---

## 8. How this roadmap evolves

Reality teaches faster than design. Expect to:

- **Re-scope phases** when testing reveals a missing dependency.
- **Insert phases** for things we discover (e.g. an unexpected provider, a
  compliance ask).
- **Skip phases** for items that get deferred indefinitely.
- **Promote parking-lot items** when they turn out to be on the critical path.

The rule is: when scope shifts, **edit this file in the same commit** as the
work that shifted it. Don't let the doc rot. An outdated roadmap is worse
than no roadmap.

When in doubt about whether to update vs. flag-for-discussion: update + flag.
The user is solo-running this; mental tracking of "things to revise later"
is exactly the failure mode this whole workflow is designed to avoid.

---

## 9. Where to look first

- **Strategic doctrine:** [`AI_Native_Dental_Implant_Clinic_White_Paper_v0_1.docx`](../AI_Native_Dental_Implant_Clinic_White_Paper_v0_1.docx)
- **Data-model doctrine:** [`ai_context_workflow_whitepaper.md`](../ai_context_workflow_whitepaper.md)
- **Agent/workflow doctrine:** [`agent_driven_workflow_layer_whitepaper.md`](../agent_driven_workflow_layer_whitepaper.md)
- **Agent/workflow integration plan:** [`plans/2026-05-04-agent-driven-workflow-layer-integration.md`](./plans/2026-05-04-agent-driven-workflow-layer-integration.md)
- **How we build:** [`WORKFLOW.md`](./WORKFLOW.md)
- **Live table catalog:** [`data-model/CATALOG.md`](./data-model/CATALOG.md)
- **Repo invariants:** [`/CLAUDE.md`](../CLAUDE.md) and the sub-`CLAUDE.md` files
- **In-flight design docs:** [`plans/`](./plans/)
