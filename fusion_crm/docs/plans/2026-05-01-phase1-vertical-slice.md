# Phase 1 Vertical Slice — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL when executing the FUS tickets cut from this
> plan: `superpowers:executing-plans`. Each task below is sized to land as one
> FUS ticket / one PR.

**Goal:** Demonstrate one end-to-end path — *"a Salesforce lead and a
CareStack consultation appointment land in `ingest.raw_event`,
normalize to `identity.person` + `ops.lead` + `ops.consultation` +
`interaction.event`, and surface on the operator-frontend Person card,
with raw provider payloads visible in env-gated dev-only Inspector
pages (`ENVIRONMENT=local` only)"* — using minimal real provider pulls
and only marketing-relevant fields from CareStack (no clinical
content).

**Architecture:** Depth-first vertical slice. We pick the single path
`provider → ingest → normalize → person + lead + interaction event →
API → operator UI` and build only what that path requires. The full
v0.2 schema (`docs/plans/2026-04-30-full-schema-v0_2.md`) remains the
north star; non-slice domains (`context`, `workflow`, `encounter`,
`segmentation`, `insight`) are deliberately deferred to their own
phases.

**Tech stack additions:**
- Backend: `mcp` (MCP server SDK), `httpx` (already present), arq jobs.
- Frontend: Next.js 14 (App Router) + Tailwind CSS, `apps/web/`.
- MCP server: `apps/mcp/` (separate process, FastAPI-style entry).

---

## 0. Pre-requisites

- **PR #6 (FUS-31 glue)** must be merged before any task in this plan
  starts implementation. The plan PR itself can sit in review in
  parallel.
- Decisions baked into this plan (from 2026-05-01 brainstorm):
  - Q1: depth-first slice, not breadth-first all-9-packages.
  - Q2: Phase 1 does include a real provider pull — one SOQL query
    against Salesforce (`Lead`), and from CareStack: one paginated
    `appointments` list endpoint plus a `patients/{id}` contact
    lookup for person resolution. **Marketing-only**: no clinical
    fields (treatment notes, history, allergies, etc) are
    normalized; raw payload still captured-as-received in
    `ingest.raw_event` per the existing contract. Field allowlist
    in §2.2.
  - Q3: per-domain alembic migrations driven by slice need. No
    big-bang v0.2 migration.
  - Q4: MCP server ships read-only in Phase 1. Writes (`create_action`,
    `add_note`) deferred to Phase 5+.
  - Q5: `apps/web` and `apps/mcp` live in this monorepo. Stack:
    Next.js 14 + Tailwind for `apps/web`.
  - Q6: This plan PR goes through Codex review BEFORE FUS tickets are
    cut. Migration design and test strategy are explicitly in Codex's
    lane and called out per task.

---

## 1. Slice scope

### IN scope (Phase 1)

| Layer | Component | What ships |
|-------|-----------|------------|
| Domain (existing, extend) | `identity` | `source_link`, `merge_event` (additive tables) |
| Domain (existing, extend) | `ops` | `account` (additive); **`consultation`** (NEW — marketing/scheduling view of a CareStack appointment) |
| Domain (existing, extend) | `phi` | **No Phase 1 changes.** Clinical-side tables (`treatment_case`, `appointment` clinical view) deferred to Phase 6 (Encounters), when clinical content actually flows. |
| Domain (new) | `interaction` | Skeleton package + migration. Single table `interaction.event` is enough for the slice timeline; `transcript_raw`, `extracted_fact` deferred to Phase 3/4. |
| Workers | SF connector | One paginated SOQL pull → raw JSON in `ingest.raw_event` → normalize → `identity.person` + `ops.lead` + `interaction.event` |
| Workers | CareStack connector | Two endpoints (appointments + patient contact info), paginated → raw JSON in `ingest.raw_event` → normalize → `identity.person` + `ops.consultation` + `interaction.event`. **Marketing-only fields**: appointment id/datetime/status, patient id + contact (name, phone, email). **Explicitly excluded**: treatment notes, medical history, allergies, prescriptions, x-rays, any clinical free-text. |
| API | Auth | `POST /auth/login`, `POST /auth/logout`, `GET /me` (cookie session via existing `auth.session`) |
| API | Person | `GET /persons/{uid}`, `GET /persons/{uid}/timeline` |
| API | Integrations connect/status | `POST /integrations/{provider}/connect/start` (returns SF OAuth redirect URL or CareStack API-key form schema) + `GET /integrations/{provider}/callback` (OAuth code → token exchange, stores in `integrations.integration_account` with the encrypted storage from FUS-22) + `POST /integrations/{provider}/api-key` (CareStack-style, accepts API key directly) + `GET /integrations` (list all accounts with status: `disconnected` / `connected` / `error` / `syncing`) + `POST /integrations/{provider}/sync` (enqueue W1/W2 job on demand). **Authenticated staff only.** |
| API | Inspector | `GET /dev/inspector/{provider}/latest` — last 50 raw payloads from `ingest.raw_event`, paginated. **Env-gated:** returns 404 unless `ENVIRONMENT=local`. Carve-out documented in `packages/ingest/CLAUDE.md` and Phase 8 closure plan. |
| Frontend | `apps/web` | Next.js + Tailwind scaffold; pages: Login, **`/integrations` (Connect/status page — providers list, Connect button → OAuth/API-key flow, status badges, "Sync now" button)**, Dashboard (counts only), Person card, Inspector (one per provider with raw-JSON viewer; same env-gate as the API endpoint) |
| MCP | `apps/mcp` | Read-only server with 4 tools: `resolve_person`, `get_person_timeline`, `list_recent_leads`, `get_inspector_payload` (last one **env-gated** like its API counterpart). Auth via `auth.api_key` bearer. Every call writes `audit.agent_tool_call`. |
| Tooling | `make mcp-key NAME=...` | Issues an `auth.api_key` row for an `actor.actor` of type `external_service`/`ai`. Outputs plaintext token once. |
| Docs | `docs/integrations/mcp-claude-code.md` | `claude mcp add` invocation + 1–2 example tool calls. |
| Docs | `docs/ROADMAP.md` | Update Phase 1 exit criterion to match this scope (see Task R1 below). |

### OUT of Phase 1 scope (deferred)

- Domain packages: `context`, `workflow`, `encounter`, `segmentation`,
  `insight`. They keep `(planned)` rows in `CATALOG.md`.
- **All clinical content from CareStack** — treatment notes, medical
  history, allergies, prescriptions, imaging refs, clinical
  free-text. Only marketing-relevant fields ship in Phase 1
  (appointments + contact info). See user direction memory
  `feedback_marketing_first_phase`.
- **PHI normalization in general.** No `phi.*` table changes in
  Phase 1. `phi.appointment` (clinical view), `phi.treatment_case`,
  `phi.transcript_raw`, `phi.extracted_fact` all wait for Phase 6+
  when clinical workflows ship.
- MCP write tools (`create_action`, `add_note`).
- HIPAA runtime gates (`PhiService.can_read_phi`, vendor BAA checks).
  Schema separation already enforces compliance posture; runtime
  gating is Phase 8.
- Bulk API for Salesforce. Pagination via SOQL `LIMIT/OFFSET` is
  enough for slice volumes (< 50k records).
- `apps/portal/` — already a stub from FUS-30; remains untouched.
- Multi-clinic / multi-tenant. `IntegrationAccount.company_uid` stays
  a global stub.
- Real production deployment, real backups, GCS storage. Local-only
  this phase.

### What gets delete-listed if it sneaks in

If during execution any of these creep in, push back and re-scope:
- any reference to `context.*` / `workflow.*` / `encounter.*` /
  `segmentation.*` / `insight.*` tables;
- any MCP write tool;
- any `PhiService.can_read_phi` runtime check;
- any code that talks to a real production SF/CareStack tenant
  beyond a sandbox;
- any CareStack field that is clinical (treatment notes, allergies,
  medical history, prescriptions, x-rays, free-text);
- any path that exposes `ingest.raw_event.payload` outside the
  env-gated Inspector — including ad-hoc admin endpoints, generic
  `/internal/*` routes, or MCP tools other than the explicitly-listed
  `get_inspector_payload`.

---

## 2. Architectural decisions baked into this plan

### 2.1 Migration strategy: per-domain, slice-driven

- One alembic revision per domain that ships in this slice. Concretely:
  - Revision A: `interaction` initial (creates `interaction` schema +
    `event` table).
  - Revision B: `identity` extensions (`source_link`, `merge_event`).
  - Revision C: `ops` extensions (`account` + `consultation`).
  - **No `phi` migration in Phase 1.** Clinical-side tables wait
    until Phase 6 (Encounters), when clinical content actually
    flows. The `phi` schema itself already exists from M1; we just
    don't add tables to it now.
- Reasons:
  - Migrations are immutable after merge (root `CLAUDE.md`). If we
    ship the full v0.2 design now and discover a wrong shape during
    slice work, we accumulate corrective additive migrations.
  - Per-domain keeps each PR reviewable.
  - We still design each domain comprehensively before its migration
    PR — *per-domain* ≠ *speculative*.
- Codex review focus on each migration PR:
  - Backfill safety on populated DBs (none yet, but discipline).
  - Constraint naming convention (no `<schema>_<schema>_…` double
    prefixes — see PR #2 Codex feedback in commit `0283311`).
  - Index plan vs. expected query patterns (called out per task).
  - `op.execute("CREATE SCHEMA IF NOT EXISTS …")` not duplicated
    across revisions; `init-schemas.sql` already creates schemas.

### 2.2 Real provider pull strategy

- One SOQL query for SF (`Lead`), two endpoints for CareStack
  (`appointments` + minimal patient-contact lookup). All paginated.
  All idempotent on `identity.source_link(provider, source_id)`.
- Raw payload always lands in `ingest.raw_event` first (untransformed
  JSON; per the existing `packages/ingest/CLAUDE.md` contract — table
  is `ingest.raw_event` with columns `source`, `event_type`,
  `external_id`, `received_at`, `payload`, `processed_at`, `error`).
  Normalization reads from `ingest.raw_event` via
  `IngestService.list_unprocessed()` per the existing contract, never
  from the provider directly. This is what makes Inspector pages
  cheap — they just read `ingest.raw_event` (under the env-gate from
  §2.3).
- **CareStack field allowlist for normalization** (defensive — even
  though we control the SOQL/endpoint, the connector explicitly drops
  any field not in the allowlist when writing to `ops.consultation`
  or `identity.person`):
  - Appointments: `id`, `patientId`, `appointmentDateTime`, `status`,
    `appointmentType`, `createdDate`, `lastModifiedDate`.
  - Patients (contact only): `id`, `firstName`, `lastName`, `email`,
    `mobilePhone`, `homePhone`, `createdDate`.
  - Anything else from the response stays in `ingest.raw_event.payload`
    and is visible only via the env-gated Inspector.
- No retry/backoff/bulk semantics in Phase 1 beyond what
  `packages/integrations/transport.py` already gives. Phase 2 hardens
  transport.

### 2.3 Inspector pages (env-gated dev-only carve-out, 2026-05-02)

- Goal: developer visually sees *what fields the providers actually
  return* — including their values — to inform workflow design while
  building the slice. The user is the only consumer in Phase 1, on
  his own laptop, with direct provider access already.
- **Environment gate (HARD).** The Inspector API endpoint, the
  `apps/web` Inspector pages, and the MCP `get_inspector_payload`
  tool ALL return 404 / refuse to register unless
  `settings.environment == "local"`. No staging, no remote dev, no
  prod. This is enforced at the application layer (FastAPI dependency
  + Next.js server action + MCP tool registration check) and asserted
  by tests.
- **Carve-out documented in `packages/ingest/CLAUDE.md`** (updated in
  the same PR as this plan revision). Original rule: "do not surface
  verbatim payloads to ops dashboards or AI agents." New text:
  production rule unchanged; local-dev carve-out explicit; logs NOT
  covered by carve-out.
- **Closure plan** (Phase 8 HIPAA runtime gating): the env-gate is
  removed and replaced by either (a) a real `actor.capability`
  `dev:raw_payload` check, or (b) the field-schema-profiler approach
  (was Codex's suggested replacement on PR #7 review — kept as the
  fallback if (a) is judged too risky). The TODO is tracked in this
  plan, in `packages/ingest/CLAUDE.md`, and in ROADMAP §5 Phase 8.
- Implementation: one page per provider under `/dev/inspector/<provider>`
  in `apps/web`. Reads `ingest.raw_event` via
  `IngestService.list_recent_events(source=...)`. Renders raw JSON
  with collapsible field tree, plus a "fetch fresh" button that
  triggers the corresponding worker job.
- Auth: same staff session as the rest of `apps/web`. Phase 1 has
  no capability check beyond "authenticated staff" + the env-gate.
  Phase 5+ adds an explicit capability when capabilities mature.
- Codex review focus: confirm Inspector reads through service layer
  (`IngestService.list_recent_events`), not directly from repository;
  confirm env-gate is asserted by tests (one positive `local` test,
  one negative `production`/`staging` test that hits 404); confirm
  the MCP tool registration is also gated.

### 2.4 Auth shape (already shipped in FUS-15, reaffirmed)

- Staff: `auth.credential(subject_type='actor', kind='password')` →
  `auth.session(subject_type='actor', cookie=hash(session_token))`.
  Cookie via `Set-Cookie` from `apps/api`.
- MCP clients: `auth.api_key` (bearer token, hashed at rest, plaintext
  shown once at issuance). Each MCP client = one `actor.actor` of type
  `external_service` or `ai`. Capability check is hardcoded in Phase 1
  to "tool name in allowlist for this actor"; full capability matrix
  is Phase 5.

### 2.5 Cross-package import matrix (Phase 1 additions)

The matrix in `packages/CLAUDE.md` (after PR #6 merges) covers
`actor`, `auth`, `integrations`. This plan adds `interaction`. Rules:

- `interaction` may import: `core`, `identity` (read-only via service),
  `audit` (write-only via service).
- `interaction` MUST NOT import: `ops`, `phi`, `actor`, `auth`,
  `integrations`. Cross-references via `person_uid` (UUID column) only.
- `apps/api` and `apps/worker` may import any service. They wire DTOs.
- `apps/mcp` imports services only (no repositories, no models). Each
  tool = one service call + audit row.
- `apps/web` is TypeScript/Next.js — does not import Python packages.
  Talks to `apps/api` only.

---

## 3. Tasks

Tasks are numbered for easy referencing. Each becomes one FUS ticket.
Order is the recommended execution order — dependencies noted.
Test strategy per task is what Codex specifically reviews.

### Task R1 — Roadmap reconciliation (do this first)

**Why first:** the roadmap currently says "all 14 schemas" as Phase 1
exit criterion. Until that's updated, every other task is in scope
limbo.

**Files:**
- Modify: `docs/ROADMAP.md` — Phase 1 section (lines covering "Work"
  list + "Exit criterion" block).

**Scope:**
- Replace the all-14-schemas exit criterion with the slice criterion
  (one path live + Inspector page renders raw payload + MCP read tool
  succeeds).
- Add a short paragraph documenting the 2026-05-01 pivot to depth-first
  slice. Reference this plan file.
- Update §6 Status snapshot bars (Phase 1 from 10% to ~15% to reflect
  scope clarity, not new work).
- Move "all remaining 9 packages skeleton" out of Phase 1 work list
  into "deferred to phases 3-7".

**Test strategy:** docs-only, no code tests. Codex reviews for clarity
and consistency with `WORKFLOW.md`.

**Estimated size:** S (single doc PR, < 100 lines diff).

**Codex review focus:** does the new exit criterion describe a
falsifiable, observable end state? (Yes: "I open `/dev/inspector/sf`
and see a JSON payload" is observable; "all 14 schemas exist" was
not connected to anything).

---

### Task D1 — `interaction` package skeleton + migration

**Depends on:** R1 merged (so the doctrine is consistent). Independent
of FUS-31 glue PR #6.

**Why now:** the slice timeline (`GET /persons/{uid}/timeline`) needs
a place to land "lead created from SF" / "patient created from
CareStack" events. `interaction.event` is the minimum.

**Files:**
- Create:
  - `packages/interaction/__init__.py`
  - `packages/interaction/CLAUDE.md` (rules — what may import from
    interaction, what interaction may import; mirrors the
    `actor`/`auth`/`integrations` style from `packages/CLAUDE.md`)
  - `packages/interaction/AGENTS.md` (thin Codex pointer)
  - `packages/interaction/models/__init__.py`
  - `packages/interaction/models/event.py` — `InteractionEvent`
    SQLAlchemy model
  - `packages/interaction/schemas/__init__.py`
  - `packages/interaction/schemas/event.py` — Pydantic DTOs (Read,
    Create)
  - `packages/interaction/repository/__init__.py`
  - `packages/interaction/repository/event.py` — data-only repository
  - `packages/interaction/service/__init__.py`
  - `packages/interaction/service/interaction_service.py` — facade
    with `create_event`, `list_for_person`
  - `packages/db/alembic/versions/<rev>_interaction_initial.py`
  - `tests/interaction/__init__.py` (empty, but present so
    `explicit_package_bases` is happy — see FUS-31 side-fix lesson)
  - `tests/interaction/test_interaction_service.py`
  - `tests/interaction/test_interaction_repository.py`
- Modify:
  - `packages/db/registry.py` — import `interaction.models`.
  - `packages/CLAUDE.md` — add `interaction` row + column to the
    cross-import matrix (FUS-31 already added rows for actor/auth/
    integrations; this extends).

**Schema for `interaction.event` (slice-minimum):**

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` PK | `uuid4()`, default server-side via `uuid_generate_v4()` |
| `person_uid` | `UUID` not null | FK-by-convention to `identity.person.id` (no DB FK across schemas — convention from root CLAUDE.md) |
| `kind` | `TEXT` not null | enum-ish; Phase 1 values: `lead_created`, `lead_updated`, `consultation_created`, `consultation_rescheduled`, `consultation_cancelled` |
| `source_provider` | `TEXT` not null | `salesforce` / `carestack` |
| `source_event_id` | `UUID` nullable | FK-by-convention to `ingest.raw_event.id` (the raw payload that produced this) |
| `occurred_at` | `TIMESTAMPTZ` not null | provider's timestamp if available, else ingest ts |
| `summary` | `TEXT` not null | **Strict no-PII contract:** action verb + provider + non-PII source_id only. Allowed examples: `"Lead created from Salesforce"`, `"Consultation rescheduled in CareStack (id=12345)"`. Forbidden: any first/last name, email, phone, DOB, address, MRN, clinical free-text. The summary is rendered by Inspector, MCP, and dashboard — it must be safe in every surface, not just the env-gated Inspector. |
| `payload` | `JSONB` not null default `'{}'` | **Structured non-PII fields only.** Allowed examples: `{"lead_status": "open", "lead_source": "Web"}`, `{"consultation_status": "rescheduled", "from_at": "...", "to_at": "..."}`. Forbidden: anything from the `interaction.summary` forbidden list. PII-bearing fields stay in `ingest.raw_event.payload` only. |
| `created_at` | `TIMESTAMPTZ` not null default `now()` | row creation |
| `created_by_actor_id` | `UUID` nullable | FK-by-convention to `actor.actor.id` |

Indexes & constraints:
- Index `(person_uid, occurred_at DESC)` — primary timeline query.
- **Partial UNIQUE constraint** `UNIQUE (source_provider,
  source_event_id) WHERE source_event_id IS NOT NULL` — enforceable
  idempotency for normalizer re-runs **within a single pipeline
  invocation** (Codex blocker on PR #7: a plain index is
  insufficient; the constraint must REJECT a duplicate, not just
  speed up its lookup). Rows where `source_event_id IS NULL`
  (manual / future system events) are exempt from uniqueness.
- **What this constraint does NOT do** (re-review clarification):
  it does not detect cross-provider-pull duplicates, because each
  pull creates new `ingest.raw_event` rows (and therefore new
  `source_event_id` values). Cross-pull dedup is a connector-level
  concern; W1 and W2 use the `was_changed` boolean returned by
  `OpsService.upsert_lead` / `upsert_consultation` to decide
  whether to emit an interaction at all. See W1 / W2 idempotency
  sections.

**Test strategy:**
- `test_interaction_repository.py`: integration test against real
  Postgres — insert two events, list by `person_uid`, assert order.
- `test_interaction_service.py`: integration test — `create_event`
  twice with same `(source_provider, source_event_id)` → second
  raises `IntegrityError` from the partial UNIQUE; service catches it
  and returns the existing row (idempotent contract). Test asserts
  one row in DB after both calls.
- **PII guard test** (new, Codex blocker on PR #7): build a fixture
  with PII strings (`firstName="John"`, `email="john@example.com"`,
  `phone="..."`, `dob="1980-01-01"`, etc.). Pass them through a
  `summary_for_event` helper. Assert the produced summary contains
  ZERO of those substrings.
- No mock DB. Per root `CLAUDE.md`: integration tests use real
  PostgreSQL.

**Codex review focus:**
- Migration shape: schema creation idempotent (`CREATE SCHEMA IF NOT
  EXISTS interaction`); column types match the design table above; no
  cross-schema FKs.
- The partial UNIQUE syntax — confirm alembic emits it correctly
  (Postgres `UNIQUE INDEX … WHERE …`, not just `UNIQUE`).
- Index choice: `(person_uid, occurred_at DESC)` — confirm this is
  what the timeline query actually uses.
- Idempotency contract documented in service docstring AND enforced
  by DB, not by application-level "check then insert".
- Summary/payload no-PII contract: the helper that builds them is
  unit-tested with PII fixtures (see test strategy).
- Cross-import matrix updated correctly.

**Estimated size:** M (one new package, one migration, ~500 lines incl.
tests).

---

### Task D2 — `identity.source_link` + `identity.merge_event`

**Depends on:** D1 not strictly required, can ship in parallel.

**Why now:** SF and CareStack normalization needs an idempotent way to
say "this provider's record `id=X` is `identity.person.id=Y`". That
mapping lives in `identity.source_link`. Without it, every re-pull
creates duplicate persons.

**Files:**
- Create:
  - `packages/identity/models/source_link.py`
  - `packages/identity/models/merge_event.py`
  - `packages/identity/repository/source_link.py`
  - `packages/identity/service/identity_service.py` — extend with
    `resolve_or_create_person(provider, source_id, hints)` and
    `record_merge(person_a, person_b, reason)`.
  - Migration `<rev>_identity_source_link_merge_event.py`.
- Modify:
  - `packages/identity/CLAUDE.md` — document new tables.
  - Existing repository / model `__init__.py` exports.

**Schema for `identity.source_link`:**

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` PK | |
| `person_uid` | `UUID` not null | FK-by-convention to `identity.person.id` |
| `provider` | `TEXT` not null | `salesforce` / `carestack` |
| `source_id` | `TEXT` not null | the provider's record id (SF Lead.Id 18-char, CareStack patient int as text) |
| `kind` | `TEXT` not null | `lead` / `patient` (extensible) |
| `linked_at` | `TIMESTAMPTZ` not null default `now()` | |
| `unlinked_at` | `TIMESTAMPTZ` nullable | for soft un-link without losing history |

Unique constraint: `(provider, kind, source_id) WHERE unlinked_at IS NULL`
— so we can't have two active links for the same external record.

**Schema for `identity.merge_event`:** see
`docs/plans/2026-04-30-full-schema-v0_2.md` §3.1 — copy that design,
no changes.

**Test strategy:**
- Integration: `resolve_or_create_person(provider='salesforce',
  source_id='00Q...', hints={'email':'a@b'})` — first call creates
  person + link, second call returns same person.
- Conflict case: two different providers, same email — current
  behavior is "create separate persons" (no fuzzy dedup in Phase 1);
  test asserts that.
- Migration applies clean on a DB with existing identity tables (no
  table drop).

**Codex review focus:**
- The `WHERE unlinked_at IS NULL` partial unique index — confirm
  Postgres syntax is correct and alembic generates it without
  needing manual SQL.
- The contract of "no fuzzy dedup" should be explicit in service
  docstring + a TODO referencing parking-lot item in ROADMAP §7.

**Estimated size:** M.

---

### Task D3 — `ops.account` extension

**Depends on:** none.

**Why:** SF Account is the parent record of Lead in many SF orgs. The
slice may not need full account hydration but should at least *record*
the account `Id` so future workflow design has it. Cheap to add now.

**Files:**
- Create:
  - `packages/ops/models/account.py`
  - `packages/ops/repository/account.py`
  - Migration `<rev>_ops_account.py`.
- Modify:
  - `packages/ops/service/ops_service.py` — `record_account(provider, source_id, name)` (idempotent on `(provider, source_id)`).
  - `packages/ops/CLAUDE.md` if needed.

**Schema for `ops.account`:** see full-schema v0.2 design doc; for
Phase 1 we ship only: `id` UUID PK, `provider` TEXT, `source_id` TEXT,
`name` TEXT, `raw` JSONB, `created_at`, `updated_at`. Other columns
deferred.

**Test strategy:** integration; idempotency on `(provider, source_id)`.

**Codex review focus:** confirm `ops.account` is *not* importing
`identity` directly except via `IdentityService`.

**Estimated size:** S.

---

### Task D4 — `ops.consultation` (CareStack appointment, marketing view)

**Depends on:** D2 (source_link) merged. Independent of D1 / D3.

**Why:** CareStack's slice contribution is *consultation appointments*
— the marketing-relevant signal of "did the lead actually book a
consult; did they show up; did they reschedule". This data is NOT
clinical (no treatment notes, no procedures). It belongs in `ops`,
not `phi`. When clinical content flows in Phase 6, a parallel
`phi.appointment` will be added with treatment fields; the two views
join on `person_uid`.

**Files:**
- Create:
  - `packages/ops/models/consultation.py`
  - `packages/ops/repository/consultation.py`
  - Migration `<rev>_ops_consultation.py`.
- Modify:
  - `packages/ops/service/ops_service.py` — add
    `upsert_consultation(person_uid, source_provider, source_id,
    scheduled_at, status, raw_marketing) -> (Consultation,
    was_changed: bool)`. Idempotent on `(source_provider,
    source_id)` (D4 UNIQUE). The `was_changed` flag is true if the
    row was newly inserted OR if `status` / `scheduled_at` changed
    on update; false if the second call is a pure no-op. Used by
    W2's normalizer to decide whether to emit an
    `interaction.event` (re-review fix on PR #7: D1's partial
    UNIQUE alone does not detect cross-pull duplicates because it
    is keyed by `raw_event.id`).
  - `packages/ops/CLAUDE.md` — document the new table and
    explicitly disclaim "non-PHI marketing view; clinical
    appointment data lives in `phi.appointment` Phase 6+".

**Schema for `ops.consultation`:**

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` PK | |
| `person_uid` | `UUID` not null | FK-by-convention to `identity.person.id` |
| `source_provider` | `TEXT` not null | typically `carestack`; left provider-agnostic for future SF-side consult tracking |
| `source_id` | `TEXT` not null | provider's appointment id |
| `scheduled_at` | `TIMESTAMPTZ` not null | the appointment datetime |
| `status` | `TEXT` not null | enum-ish: `scheduled`, `rescheduled`, `cancelled`, `completed`, `no_show`. Phase 1 may only see `scheduled` / `rescheduled` / `cancelled` from CareStack. |
| `raw_marketing` | `JSONB` not null default `'{}'` | structured non-PHI fields from the allowlist in §2.2: appointment id/datetime/status, appointmentType, createdDate. **Never** clinical content. |
| `created_at` | `TIMESTAMPTZ` not null default `now()` | |
| `updated_at` | `TIMESTAMPTZ` not null default `now()` | |

Constraints:
- `UNIQUE (source_provider, source_id)` — enforceable idempotency.

**Test strategy:**
- Integration: `upsert_consultation` twice with same
  `(source_provider, source_id)` — second is update, not insert.
- Status transition test: scheduled → rescheduled (allowed),
  cancelled → scheduled (rejected by service-level guard, not DB).
- **No-clinical-content guard test:** fixture with a "treatment_notes"
  field in the raw response → assert that field is NOT persisted to
  `raw_marketing` (allowlist enforced).

**Codex review focus:**
- Naming `ops.consultation` (vs `ops.appointment`) — confirm this
  name doesn't clash with the future `phi.appointment` design.
  Documentation (CLAUDE.md update) calls out the relationship.
- Status enum is TEXT not native PG enum (matches the rest of the
  codebase's enum-via-text convention).
- Allowlist enforcement in `upsert_consultation` is unit-tested.

**Estimated size:** M.

---

### Task W1 — Salesforce connector worker (real pull)

**Depends on:** D1, D2 merged. D3 strongly recommended. **A4 + F5
merged** (worker reads OAuth tokens from `integrations.integration_account`,
which are populated by the connect-via-UI flow; no env-vars path in
Phase 1).

**Why:** This is the primary slice driver. Without this, the rest of
the pipeline has no data to render.

**Files:**
- Create:
  - `apps/worker/jobs/salesforce_pull_leads.py` — arq job. Takes
    `account_id` arg (from `IntegrationsService.enqueue_sync` in A4).
    One SOQL query: `SELECT Id, FirstName, LastName, Email, Phone,
    LeadSource, Status, CreatedDate FROM Lead ORDER BY CreatedDate
    DESC LIMIT 100`. Paginate via OFFSET in 100-row chunks (cap total
    at 1000 per run for the slice).
  - `packages/integrations/services/salesforce_pull.py` — client
    code that calls the SF REST API. Reads OAuth tokens from
    `integrations.integration_account` (populated by A4's OAuth
    callback handler). Uses existing transport from
    `packages/integrations/transport.py`. Refreshes the access_token
    via the FUS-15 OAuth helper if expired; persists the new token
    back to `integration_account`.
  - `tests/worker/test_salesforce_pull.py` — uses `respx`/`httpx_mock`
    to fake SF responses.
- Modify:
  - `apps/worker/main.py` — register the new job.
  - `packages/integrations/CLAUDE.md` — document the connector.

**Pipeline:**

1. Job runs (cron / on-demand via API).
2. Calls SF REST `/services/data/v59.0/query/?q=...`.
3. For each row in response:
   - Persist raw payload to `ingest.raw_event(source='salesforce',
     event_type='lead', external_id=Lead.Id, received_at=now(),
     payload=<row>)` — using the existing table contract from
     `packages/ingest/CLAUDE.md`.
   - Call `IdentityService.resolve_or_create_person(provider='salesforce',
     source_id=Lead.Id, kind='lead', hints={...})`.
   - Call `OpsService.upsert_lead(person_uid, raw=<row>)
     -> (Lead, was_changed: bool)`. Same change-detection contract
     as D4's `upsert_consultation`: `was_changed=true` on insert or
     when `Status` / `LeadSource` changed; false on no-op re-pull.
   - **Only if `was_changed`:** call
     `InteractionService.create_event(person_uid,
     kind='lead_created' if newly inserted else 'lead_updated',
     source_provider='salesforce',
     source_event_id=<ingest.raw_event.id>,
     occurred_at=Lead.CreatedDate,
     summary='Lead created from Salesforce' / 'Lead updated in Salesforce',
     payload={'lead_status': Lead.Status, 'lead_source': Lead.LeadSource})`.
     **No FirstName/LastName/Email in summary or payload** (D1
     contract). Re-review fix on PR #7: D1's partial UNIQUE is
     keyed by `raw_event.id`, so it doesn't catch cross-pull
     duplicates; the W1 normalizer must use `was_changed` from
     `upsert_lead` to suppress no-op interactions.
4. Sync journaling + audit:
   - `IntegrationsService.open_sync_run(account_id, kind='pull',
     ...)` at start; returns `sync_run_id`.
   - `IntegrationsService.close_sync_run(sync_run_id, status, stats)`
     at end — writes the operational outcome to
     `integrations.sync_run` (NOT `audit.sync_run` — that table
     does not exist).
   - `AuditService.log_sync_run_summary(sync_run_id, provider,
     status, counts)` — writes the audit summary row into
     `audit.access_log` via `extra` payload (helper landed in
     FUS-23). One per terminated `integrations.sync_run`.

**Test strategy:**
- Unit tests with `respx`-mocked SF transport — fake 100 rows, assert
  100 `ingest.raw_event` rows + 100 `identity.person` rows + 100
  `interaction.event` rows of `kind='lead_created'` (first pull, all
  inserts → all `was_changed=true`).
- **Cross-pull idempotency** (re-review fix on PR #7): run W1 twice
  against IDENTICAL fake data. After the second run assert: still
  100 persons, still 100 leads, still exactly 100 interactions
  (NOT 200, NOT 100 + 100). The second pull produces 100 new
  `ingest.raw_event` rows (raw is captured-as-received), but
  `OpsService.upsert_lead` returns `was_changed=false` for every
  row, so the W1 normalizer skips `InteractionService.create_event`
  entirely. Zero new interactions.
- **Change-detection idempotency:** run W1 twice with the second
  fixture mutating `Status` on 5 of the 100 rows. After the second
  run assert: 100 persons, 100 leads, 105 interactions (100
  `lead_created` from the first run + 5 `lead_updated` from the
  second run for the changed rows). Confirms `was_changed=true`
  fires only on actual changes.
- Error path: SF returns 401 → job fails fast, `integrations.sync_run`
  closed with `status='failed'`, `AuditService.log_sync_run_summary`
  records the failure.

**Codex review focus:**
- Ingest-first principle (raw payload lands first, before any
  normalization) — confirm.
- OAuth token refresh path — covered by FUS-15 OAuth helpers; confirm
  the connector uses them and doesn't duplicate logic.
- Idempotency strategy: `(provider='salesforce', kind='lead',
  source_id=Lead.Id)` is unique in `identity.source_link` (D2). Re-run
  hits the unique constraint → `resolve_or_create_person` returns
  existing person.

**Estimated size:** L (real network code + idempotency + tests).

---

### Task W2 — CareStack connector worker (marketing-only pull)

**Depends on:** D1, D2, D4 merged. **A4 + F5 merged** (worker reads
the CareStack API key from `integrations.integration_account`,
populated via the connect-via-UI api-key form). Pattern mirrors W1
but with a **narrowed marketing-only scope**.

**Why narrowed:** user direction (memory
`feedback_marketing_first_phase`): Phase 1 takes only marketing
signals from CareStack — when a consultation is scheduled,
rescheduled, cancelled — and the patient contact info needed to
link to a person. **No clinical content** (treatment notes, medical
history, allergies, prescriptions, x-rays, free-text). Even though
the carve-out in §2.3 lets Inspector show full payload, the
*normalizer* never touches non-allowlisted fields.

**Files:** mirror of W1 with `source='carestack'`. CareStack uses an
API key (no OAuth flow). Key is stored in
`integration_account.access_token` (encrypted via FUS-22
`EncryptedString`) by A4's `/integrations/carestack/api-key`
endpoint; the worker reads it from there.

**Endpoints (confirm exact shapes against
`docs/integrations/carestack/_source/`):**
- `GET /carestack/api/v1.0/appointments?$top=100&$skip=...&$select=<allowlist>` — list of consultation appointments (created, rescheduled, cancelled events implied by `status` + `lastModifiedDate`).
- `GET /carestack/api/v1.0/patients/{id}?$select=<allowlist>` — minimal patient contact lookup (name, phone, email, id) for person resolution.

**Pipeline:**

1. Job runs (cron / on-demand via API).
2. Fetches one page of appointments (`$top=100`).
3. For each appointment:
   - Persist raw payload to `ingest.raw_event(source='carestack',
     event_type='appointment', external_id=appt.id,
     received_at=now(), payload=<appt_row>)`. **Full payload** —
     this is captured-as-received per `packages/ingest/CLAUDE.md`.
     The Inspector carve-out is the only way it's surfaced.
   - If `appt.patientId` is unseen: fetch patient contact, persist
     to `ingest.raw_event(source='carestack', event_type='patient',
     external_id=patient.id, payload=<patient_row>)`.
   - `IdentityService.resolve_or_create_person(provider='carestack',
     source_id=patient.id, kind='patient', hints={'email':
     patient.email, 'phone': patient.mobilePhone})`.
   - `OpsService.upsert_consultation(person_uid,
     source_provider='carestack', source_id=appt.id,
     scheduled_at=appt.appointmentDateTime, status=<derived>,
     raw_marketing=<allowlisted dict>) -> (Consultation,
     was_changed: bool)`. **Allowlist enforced here** — only the
     §2.2 fields are passed in.
   - **Only if `was_changed`:** call
     `InteractionService.create_event(person_uid,
     kind='consultation_created' if newly inserted else
     'consultation_rescheduled' if scheduled_at changed else
     'consultation_cancelled' if status changed to cancelled,
     source_provider='carestack',
     source_event_id=<ingest.raw_event.id>,
     occurred_at=appt.lastModifiedDate or appt.createdDate,
     summary='Consultation created in CareStack (id=' + appt.id +
     ')' / 'Consultation rescheduled in CareStack (id=' + appt.id +
     ')' / etc.,
     payload={'consultation_status': <status>, 'from_at': <prev>?,
     'to_at': <new>?, 'appointment_type': appt.appointmentType})`.
     **No name/email/phone/DOB in summary or payload.** When the
     second pull sees an unchanged appointment (`was_changed=false`),
     no interaction is emitted — this is the cross-pull dedup
     mechanism described in the idempotency section below.
4. Sync journaling + audit: same shape as W1 — pair
   `IntegrationsService.open_sync_run` + `close_sync_run` (writes to
   `integrations.sync_run`) with `AuditService.log_sync_run_summary`
   (writes the audit summary). Per-pull stats: appointments fetched,
   appointments normalized, patient contacts resolved, errors.

**Test strategy:**
- Unit tests with `respx`-mocked CareStack — fake 50 appointments
  spanning three statuses, assert correct interaction kinds.
- **Idempotency** (re-review fix on PR #7): D1's partial UNIQUE on
  `(source_provider, source_event_id)` is keyed by
  `ingest.raw_event.id`. A second provider pull creates NEW
  `raw_event` rows, so D1 alone does NOT detect "same provider
  entity, re-pulled". Real idempotency for W2 has two layers:
  - **DB-enforced for `ops.consultation`:** D4's
    `UNIQUE (source_provider, source_id)` on the provider's
    appointment id rejects duplicates / makes the second call an
    UPDATE, not an INSERT.
  - **App-level for `interaction.event`:** the W2 normalizer first
    calls `OpsService.upsert_consultation(...)` which returns
    `(row, was_changed: bool)`. The normalizer ONLY creates an
    `interaction.event` if `was_changed` is true (status changed,
    `scheduled_at` changed, or row was newly inserted) AND emits
    the appropriate `kind` (`consultation_created`,
    `_rescheduled`, `_cancelled`). When the second pull sees an
    unchanged appointment, no interaction is emitted.
  - **D1 partial UNIQUE remains a safety net** for "same raw_event
    row being re-normalized within a single pipeline run" (e.g.
    pipeline retry after a partial failure). It is NOT the
    cross-pull dedup mechanism.
  Test asserts: run W2 twice on identical fixture data → exactly
  one `ops.consultation` row, exactly one `interaction.event` row
  (the first pull emits `consultation_created`; the second pull is
  a no-op on the change-detector and emits nothing).
- **Allowlist enforcement test:** fixture appointment includes a
  `treatmentNotes: "patient reports back pain"` field. After the
  job runs, assert: `ops.consultation.raw_marketing` does NOT
  contain `treatmentNotes`; `interaction.event.payload` does NOT
  contain `treatmentNotes` or its value; `ingest.raw_event.payload`
  DOES contain it (raw is captured-as-received by contract).
- **Expanded log-redaction test (Codex blocker on PR #7):** fixture
  patient has `firstName='John'`, `lastName='Smith'`, `email='john@example.com'`,
  `mobilePhone='+15555551234'`, `dateOfBirth='1980-01-01'`,
  `streetAddress='123 Main St'`, plus a clinical-looking string in
  a non-allowlisted field. Capture all structlog output during a
  full pipeline run AND during three error paths (CareStack 401,
  CareStack 500, malformed JSON). Assert NONE of the PII strings
  appear in any log line, including exception traceback frames.
  Run the assertion across `apps.worker`, `packages.integrations`,
  `packages.ops`, `packages.identity`, `packages.interaction`,
  `packages.ingest` loggers.

**Codex review focus:**
- **PHI redaction in logs** — must be explicitly asserted by tests
  across happy and error paths (Codex blocker on PR #7).
- **Allowlist enforcement** — unit test, not just code review.
- Endpoint shapes verified against
  `docs/integrations/carestack/_source/`.
- The raw payload going into `ingest.raw_event.payload` is full
  (per ingest contract) — only the *normalization output* is
  filtered. This is the right split.
- **Reverse-leak guard:** confirm that nothing in the W2 pipeline
  reads raw payload back out for non-Inspector purposes (e.g. no
  log message that interpolates `payload['firstName']`).

**Estimated size:** L.

---

### Task A1 — API auth endpoints

**Depends on:** none structural (auth domain already exists). May
proceed in parallel with W1/W2.

**Files:**
- Create:
  - `apps/api/routes/auth.py` — `POST /auth/login`, `POST /auth/logout`,
    `GET /me`.
  - `apps/api/dependencies/session.py` — `current_actor` FastAPI
    dependency that resolves cookie → `auth.session` → `actor.actor`.
  - `tests/api/test_auth_routes.py`.
- Modify:
  - `apps/api/main.py` — register routes.

**Endpoint contracts:**

- `POST /auth/login` body `{email, password}` → on success:
  - Verify against `auth.credential(subject_type='actor', kind='password')`.
  - Issue `auth.session(subject_type='actor', cookie=<random>)`,
    `expires_at = now() + 12h`.
  - `Set-Cookie: session=<value>; HttpOnly; Secure; SameSite=Lax`.
  - Body: `{actor_id, display_name}`.
- `POST /auth/logout` reads cookie → marks session `revoked_at = now()`.
- `GET /me` reads cookie → returns `{actor_id, display_name,
  capabilities: [...]}`.

**Test strategy:** integration tests through `httpx.AsyncClient` against
the FastAPI app + real test DB. Cover: bad creds → 401, good creds →
200 + cookie set, logout invalidates cookie, `/me` after logout → 401.

**Codex review focus:**
- Cookie flags (`HttpOnly`, `Secure`, `SameSite`).
- Password verify uses argon2 (FUS-15 helper), not bare bcrypt or
  sha256.
- Rate limiting on `/auth/login` — Phase 1 may skip this and TODO it,
  but call it out explicitly.

**Estimated size:** M.

---

### Task A2 — API person endpoints

**Depends on:** D1 (interaction), W1 or W2 producing data (so the
endpoints have something to return in tests with seeded fixtures).

**Files:**
- Create:
  - `apps/api/routes/persons.py` — `GET /persons/{uid}`,
    `GET /persons/{uid}/timeline`.
  - `apps/api/schemas/person.py` — DTOs.
  - `tests/api/test_persons_routes.py`.

**Endpoint contracts:**

- `GET /persons/{uid}` →
  ```
  { id, display_name, email, phone, source_links: [{provider, kind, source_id}], counts: {leads, interactions} }
  ```
- `GET /persons/{uid}/timeline?limit=50&before=<ts>` →
  ```
  { events: [{id, kind, source_provider, occurred_at, summary, payload}], next_cursor: <ts | null> }
  ```
  Cursor pagination on `occurred_at DESC` matches the index from D1.

**Test strategy:** integration; fixture seeds 1 person with 5 events;
assert payload shape, ordering, cursor behavior.

**Codex review focus:**
- No business logic in routes — they only call `IdentityService` /
  `InteractionService`.
- DTO has zero PHI fields (timeline `summary` is non-PHI by D1
  contract; confirm tests assert this).
- Cursor uses ISO-8601 string, not raw timestamp object.

**Estimated size:** M.

---

### Task A3 — API Inspector endpoints (env-gated)

**Depends on:** W1 or W2 producing `ingest.raw_event` rows.

**Why:** Powers the frontend Inspector pages and the MCP
`get_inspector_payload` tool's data path.

**Files:**
- Create:
  - `apps/api/routes/inspector.py` — `GET /dev/inspector/{provider}/latest?limit=50&event_type=...`.
  - `apps/api/dependencies/local_only.py` — FastAPI dependency
    `require_local_env()` that raises 404 unless
    `settings.environment == "local"`.
  - `tests/api/test_inspector_routes.py`.

**Endpoint contract:**
- `GET /dev/inspector/salesforce/latest?limit=50&event_type=lead` →
  ```
  { events: [{ id, source, event_type, external_id, received_at, payload (raw JSON), processed_at, error }], total: N }
  ```
  (Field names match `ingest.raw_event` columns from
  `packages/ingest/CLAUDE.md`.)
- **Env-gate:** the route depends on `require_local_env()`. In any
  non-`local` env, the route returns 404 (NOT 403) so it's
  indistinguishable from a missing endpoint to an external caller.
- Auth (in addition to env-gate): requires authenticated staff
  session (`current_actor` dependency). No capability check beyond
  that in Phase 1; Phase 5+ adds `dev:raw_payload`.

**Test strategy:**
- Integration positive: `ENVIRONMENT=local`, seed 5 ingest events,
  authenticate, call endpoint → 200, payload visible.
- Integration negative (env-gate): override settings to
  `ENVIRONMENT=production`, authenticate, call endpoint → 404.
  Repeat with `ENVIRONMENT=staging` → 404. (Critical: this is the
  carve-out closure mechanism.)
- Integration negative (auth): `ENVIRONMENT=local`, no session →
  401.

**Codex review focus:**
- The env-gate dependency is the FIRST dependency on the route, not
  buried after auth. Reasoning: even a 401 leaks endpoint existence;
  404 must come first.
- The endpoint reads `IngestService.list_recent_events(source=...)`,
  NOT the repository directly.
- Path prefix `/dev/` signals "not a stable production API" —
  confirmed in OpenAPI tags as well.
- Tests cover all three env values (`local` / `staging` / `production`),
  not just one.

**Estimated size:** S.

---

### Task A4 — API integrations connect/status endpoints

**Depends on:** FUS-22 (integrations package) merged + FUS-15 (auth) merged
+ FUS-31 glue PR #6 merged (config env vars). Independent of D1/D2/D3/D4
and W1/W2 (workers read credentials from `integrations.integration_account`,
not env vars, so this task replaces the env-vars-only path).

**Why:** without UI-driven connection, the slice is not self-observable
end-to-end — operator would have to hand-edit `.env.local` to make
W1/W2 fire. The original M1 milestone description in Linear listed
`/integrations/{provider}` connect/status pages; they got dropped during
the slice-narrowing pivot, this task restores them.

**Files:**
- Create:
  - `apps/api/routes/integrations.py` — five endpoints (see contracts below).
  - `apps/api/schemas/integrations.py` — DTOs (`ConnectStartIn`,
    `ConnectStartOut`, `IntegrationAccountOut`, etc).
  - `tests/api/test_integrations_routes.py`.
- Modify:
  - `packages/integrations/service.py` — add `record_account_from_oauth_callback`,
    `record_account_from_api_key`, `list_accounts_with_status`,
    `enqueue_sync(account_id)` (delegates to arq queue).
  - `packages/integrations/CLAUDE.md` — document the public API surface.

**Endpoint contracts (all `current_actor`-gated):**

- `POST /integrations/{provider}/connect/start` body `{}` → response varies by provider:
  - `salesforce`: `{ kind: "oauth_redirect", url: "https://login.salesforce.com/services/oauth2/authorize?..." }`. PKCE state stored server-side in a short-lived cache (Redis) keyed by `actor_id`.
  - `carestack`: `{ kind: "api_key_form", fields: [{name: "subdomain", required: true}, {name: "api_key", required: true, secret: true}] }`. No redirect; UI renders the form and POSTs to `/integrations/carestack/api-key`.
- `GET /integrations/{provider}/callback?code=...&state=...` (Salesforce only) → exchange code → access_token + refresh_token → `IntegrationsService.record_account_from_oauth_callback(provider='salesforce', tokens=..., actor_id=...)` → redirect to `/integrations` with success flash.
- `POST /integrations/{provider}/api-key` body `{subdomain, api_key}` (CareStack) → `IntegrationsService.record_account_from_api_key(provider='carestack', credentials=..., actor_id=...)` → 200 with `IntegrationAccountOut`.
- `GET /integrations` → `{accounts: [{id, provider, company_uid, status, last_sync_at?, last_error?}]}`. `status` ∈ `disconnected` / `connected` / `error` / `syncing` (derived from latest `integrations.sync_run` for the account, or `connected` if no sync_run yet).
- `POST /integrations/{provider}/sync` → enqueues the corresponding W1 (`salesforce_pull_leads`) or W2 (`carestack_pull_appointments`) arq job for the active account; returns 202 + `{sync_run_id}` (the row created by `IntegrationsService.open_sync_run`).

**Test strategy:**
- Integration positive (SF):
  - `POST /integrations/salesforce/connect/start` → assert response shape includes a Salesforce `https://login.salesforce.com/services/oauth2/authorize` URL with PKCE params.
  - Mock SF token endpoint via `respx` → `GET /integrations/salesforce/callback?code=fake&state=...` → assert one `integrations.integration_account` row exists with encrypted tokens (use the FUS-22 `EncryptedString` round-trip check).
- Integration positive (CareStack):
  - `POST /integrations/carestack/connect/start` → assert form schema response.
  - `POST /integrations/carestack/api-key {subdomain: "test", api_key: "..."}` → assert account row + token in encrypted column.
- `GET /integrations` returns combined list with derived statuses.
- `POST /integrations/salesforce/sync` enqueues exactly one job; subsequent immediate call returns 409 (already-syncing guard) — TODO: this guard may be too strict for Phase 1; flag in PR.
- Negative auth: anonymous → 401.
- **Secret-leak guard test:** the `IntegrationAccountOut` DTO MUST NOT include the access_token / refresh_token / api_key. Test: create an account with known token, GET `/integrations`, assert response JSON does not contain the token substring.

**Codex review focus:**
- Token storage: SF tokens land in `integration_account.access_token` / `refresh_token` (encrypted via FUS-22 `EncryptedString`). CareStack api_key lands in the same column shape. Confirm encryption is at rest, not at boundary.
- PKCE state cache: short TTL (e.g. 10 min), keyed by actor_id, single-use.
- DTO secret-leak guard is asserted by tests, not just code review.
- The `current_actor` dependency is on every endpoint (no anonymous OAuth callback hijack — OAuth state binds to the actor who initiated `/connect/start`).
- `enqueue_sync` writes the `sync_run` row BEFORE enqueueing (so a queue failure leaves a `failed` row, not a missing one).

**Estimated size:** M.

Pre-req: PR #6 merged.
Plan: this section.

---

### Task M1 — `apps/mcp/` scaffold + auth

**Depends on:** A1 (so we have working sessions to copy auth shape from)
is helpful but not strictly required since MCP uses api_key, not session.
Independent of W1/W2.

**Files:**
- Create:
  - `apps/mcp/CLAUDE.md` — rules (services-only, audit per call,
    api_key auth).
  - `apps/mcp/AGENTS.md` — Codex pointer.
  - `apps/mcp/main.py` — MCP server entry. Uses the `mcp` Python SDK.
  - `apps/mcp/auth.py` — bearer token → `auth.api_key` →
    `actor.actor`.
  - `apps/mcp/tools/__init__.py`
  - `apps/mcp/tools/_audit.py` — decorator that wraps every tool
    with `AuditService.log_agent_tool_call`.
  - `tests/mcp/test_auth.py`.
- Modify:
  - `pyproject.toml` — add `mcp` dependency.
  - `infra/docker/docker-compose.yml` — add `mcp` service entry
    (separate process, separate port).
  - `packages/core/config.py` — add `mcp_*` env vars (host/port).

**Auth flow:**
1. MCP client sends bearer token in `Authorization` header.
2. `apps/mcp/auth.py` hashes the token (argon2), looks up
   `auth.api_key` by hash. If not found or revoked → 401.
3. Resolves `actor.actor` by `api_key.actor_id`.
4. Stashes `Principal(actor=...)` for the duration of the call.

**Test strategy:**
- Unit: hash + lookup roundtrip.
- Integration: real DB, real api_key row, real call → audit row
  appears.

**Codex review focus:**
- Token hashing strategy — argon2 with same params as session cookies,
  not sha256.
- Revoked keys (`revoked_at IS NOT NULL`) are rejected.
- Audit row written even if the tool itself errors (record the
  attempt).

**Estimated size:** M.

---

### Task M2 — MCP read-only tools (4 of them)

**Depends on:** M1 + (D1 or A2 — service layer needed for tool
implementations).

**Files:**
- Create:
  - `apps/mcp/tools/resolve_person.py` — args: `{email?, phone?,
    provider?, source_id?}` → returns `person` object.
  - `apps/mcp/tools/get_person_timeline.py` — args: `{person_uid,
    limit?, before?}` → mirrors A2's `/persons/{uid}/timeline`.
  - `apps/mcp/tools/list_recent_leads.py` — args: `{provider?,
    since?}` → top N lead-kind interaction events with person snippet.
  - `apps/mcp/tools/get_inspector_payload.py` — args: `{provider,
    external_id}` → the raw `ingest.raw_event.payload` for one
    record. **Env-gated** like its API counterpart: the tool's
    registration in `apps/mcp/main.py` is conditional on
    `settings.environment == "local"`. In any other env, the tool
    is not exposed (the MCP `tools/list` response simply doesn't
    include it).
  - `tests/mcp/test_tools_*.py` — one per tool.
  - `tests/mcp/test_inspector_envgate.py` — explicit test that the
    tool is absent from `tools/list` when `ENVIRONMENT=production`.

**Each tool wrapped in `_audit` decorator** so every call writes
`audit.agent_tool_call(actor_id, tool_name, args, result_status,
duration_ms)`.

**Test strategy:**
- Integration per tool: assert correct service is called + audit row
  written.
- `get_inspector_payload` env-gate test (positive `local` + negative
  `production` + negative `staging`): on non-local envs, the tool is
  absent from `tools/list`; calling it directly returns
  tool-not-found (mirrors API 404 semantics).

**Codex review focus:**
- `get_inspector_payload` env-gate is at TOOL REGISTRATION time
  (not runtime per-call). On non-local startup the tool simply
  doesn't exist. This is the strongest carve-out form for MCP.
- Tool reads `IngestService.list_recent_events` / `get_by_external_id`,
  not the repository directly.
- No tool returns model objects directly — all return plain dict /
  Pydantic DTO.
- Three other tools (`resolve_person`, `get_person_timeline`,
  `list_recent_leads`) return only non-PHI fields by D1 contract,
  so they have no env-gate.

**Estimated size:** M.

---

### Task M3 — `make mcp-key` CLI + connection guide

**Depends on:** M1.

**Files:**
- Create:
  - `infra/scripts/mcp_issue_key.py` — argparse CLI; creates one
    `actor.actor` (if not exists by name) + one `auth.api_key`. Prints
    plaintext token once.
  - `docs/integrations/mcp-claude-code.md` — usage guide.
- Modify:
  - `Makefile` — add `mcp-key` target.

**Test strategy:** smoke test in CI — `make mcp-key NAME=test-actor`
succeeds, prints a token, and a subsequent MCP request with that token
returns 200.

**Codex review focus:**
- Plaintext token shown once and never stored anywhere except hashed.
- Idempotency on `name` (re-running with same name does NOT issue a
  new key by default; needs `--force`).

**Estimated size:** S.

---

### Task F1 — `apps/web/` scaffold (Next.js + Tailwind)

**Depends on:** A1 (so login page can talk to a real endpoint), but
can scaffold-without-data first.

**Files:**
- Create:
  - `apps/web/CLAUDE.md` — frontend rules (no PHI in client logs;
    only talk to `apps/api`; auth via httponly cookie).
  - `apps/web/AGENTS.md` — Codex pointer.
  - `apps/web/package.json`, `apps/web/tsconfig.json`,
    `apps/web/tailwind.config.ts`, `apps/web/next.config.mjs`.
  - `apps/web/app/layout.tsx`, `apps/web/app/page.tsx` (placeholder
    home).
  - `apps/web/lib/api.ts` — typed fetch wrapper with cookie
    forwarding.
  - `apps/web/.env.example` — `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- Modify:
  - root `Makefile` — add `web-dev` target (`cd apps/web && npm run dev`).
  - `infra/docker/docker-compose.yml` — `web` service entry (optional,
    can be local-only via `npm run dev` initially).
  - root `CLAUDE.md` folder map — add `apps/web/`.

**Test strategy:** scaffold-only PR; smoke test = `npm run build`
succeeds in CI. Integration test deferred to F4.

**Codex review focus:**
- Tailwind config is minimal (no design system bloat).
- Auth: `lib/api.ts` always sends `credentials: 'include'` (cookie
  flow) and parses the JSON-envelope errors from root CLAUDE.md
  contract.
- No secrets in `.env.example`.

**Estimated size:** M.

---

### Task F2 — Login page

**Depends on:** F1, A1.

**Files:**
- Create:
  - `apps/web/app/login/page.tsx`
  - `apps/web/app/login/actions.ts` — server action calling
    `POST /auth/login`.
  - `apps/web/components/LoginForm.tsx`.

**Behavior:**
- Email + password form.
- On success: redirect to `/dashboard`.
- On failure: show error from API envelope.

**Test strategy:** Playwright/RTL component test for the form. E2E
deferred to F4.

**Codex review focus:**
- No password value in any console.log or analytics call.
- Form submission goes through server action, not client-side fetch
  (so cookie is set by server).

**Estimated size:** S.

---

### Task F5 — `/integrations` Connect/status page

**Depends on:** F1, F2, A4.

**Why this is sequenced BEFORE F3/F4:** without a connected provider,
W1/W2 have nothing to pull, so the dashboard and Inspector are empty.
The slice's "data live on UI" promise depends on the operator being
able to click Connect → OAuth → see status flip to `connected` → click
Sync → see counts update.

**Files:**
- Create:
  - `apps/web/app/integrations/page.tsx` — server component listing
    accounts via `GET /integrations`. Each provider row shows: name,
    status badge, last_sync_at relative time, last_error tooltip,
    "Connect" or "Sync now" button depending on state.
  - `apps/web/app/integrations/[provider]/connect/page.tsx` — client
    flow handler. For SF: triggers `POST /integrations/salesforce/connect/start`
    via server action → redirects to the returned OAuth URL. For
    CareStack: renders the API-key form schema returned by
    `/connect/start` and POSTs to `/integrations/carestack/api-key`.
  - `apps/web/app/integrations/salesforce/callback/page.tsx` — receives
    `?code=...&state=...` from SF, server-action proxies to API
    `/integrations/salesforce/callback`, on 200 redirects to
    `/integrations` with success flash.
  - `apps/web/components/IntegrationCard.tsx` — provider row
    (status badge, action button, last sync text).
  - `apps/web/components/StatusBadge.tsx` — colored chip:
    `disconnected` (gray) / `connected` (green) / `syncing` (blue
    pulse) / `error` (red).
  - `apps/web/components/CareStackKeyForm.tsx` — controlled form for
    API key + subdomain.

**UX flow:**
1. Operator logs in → redirects to `/dashboard`. Dashboard shows
   "No data yet — [Connect a provider]". Link goes to `/integrations`.
2. `/integrations` shows two rows: Salesforce (disconnected),
   CareStack (disconnected).
3. Click Connect on Salesforce → OAuth redirect → SF login → callback
   → land on `/integrations` with SF row now `connected`.
4. Click Connect on CareStack → modal with API-key form → submit →
   row flips to `connected`.
5. Click "Sync now" on either → row flips to `syncing` (with
   spinner) → on completion (poll `/integrations` every 3s while
   syncing) flips back to `connected` with new `last_sync_at`.
6. On failure: status flips to `error` with hover-tooltip
   summarizing the error (from `last_error` field, derived from the
   most recent `integrations.sync_run.status='failed'` for the
   account).

**Test strategy:**
- E2E (Playwright): seed staff user → log in → go to `/integrations` →
  assert two disconnected rows. Mock SF OAuth flow → click Connect
  on SF → assert redirect → simulate callback with fake code → mock
  SF token endpoint → assert SF row flips to `connected`. Repeat
  for CareStack with API-key form submission. Click "Sync now" → mock
  worker completion → assert row updates.
- Component test for `StatusBadge` rendering all four states.
- **Secret-handling test:** API key form's input has `type="password"`
  AND the form does NOT include the value in any logged event,
  analytics call, or URL param.

**Codex review focus:**
- OAuth callback page is a server component; `code` + `state` never
  hit the client. State is verified server-side via the cache from A4.
- API key flows through server action (POST body), never as URL param.
- Polling cadence (3s during syncing) is reasonable — Phase 1 may
  use simple polling; SSE / WebSocket can be added later.
- Status badge colors meet WCAG contrast (Tailwind defaults are
  fine; just confirm).

**Estimated size:** M.

Pre-req: F1, F2, A4 merged.
Plan: this section.

---

### Task F3 — Dashboard + Person card pages

**Depends on:** F2, A2.

**Files:**
- Create:
  - `apps/web/app/dashboard/page.tsx` — counts of total persons,
    leads, interactions in last 24h. Plus a list of 10 most-recent
    persons with link to their card.
  - `apps/web/app/persons/[uid]/page.tsx` — Person card.
  - `apps/web/components/PersonHeader.tsx`,
    `apps/web/components/Timeline.tsx`,
    `apps/web/components/SourceLinks.tsx`.
- Modify:
  - `apps/api/routes/dashboard.py` (NEW endpoint:
    `GET /dashboard/summary`) — wire the counts. Add to A2 task or
    as Task A2.5.

**Person card contents (Phase 1 minimum):**
- Header: display name, email, phone.
- Source links: chips like `salesforce:lead:00Q3i...` and
  `carestack:patient:12345`.
- Timeline: vertical list of `interaction.event` entries with kind
  badge, occurred_at, summary, expandable payload (JSON).

**Test strategy:** RTL component tests; one E2E in F4 covering full
flow.

**Codex review focus:**
- Timeline payload JSON viewer — does it accidentally render PHI for
  CareStack patients? In Phase 1, payload is non-PHI by D1 contract;
  but if W2 ends up dumping CareStack patient demographics into
  payload, we have a leak. Codex will catch this.
- Component split keeps PersonHeader stateless.

**Estimated size:** L (multiple components + state management).

---

### Task F4 — Inspector pages (one per provider, env-gated)

**Depends on:** A3.

**Files:**
- Create:
  - `apps/web/app/dev/inspector/[provider]/page.tsx` — list of recent
    raw payloads for the provider; click → expand JSON tree.
  - `apps/web/lib/env-gate.ts` — server-side helper that reads
    `process.env.ENVIRONMENT` (Next.js server-only) and throws
    `notFound()` from `next/navigation` for non-`local`. Imported
    by every `dev/*` route.
  - `apps/web/components/JsonTree.tsx` — collapsible JSON viewer.
  - `apps/web/components/FetchFreshButton.tsx` — POSTs to
    `/dev/inspector/{provider}/refresh` (this endpoint added under
    A3 / A3.5; behind the scenes it enqueues the W1/W2 worker job).

**Env-gate (front-side):** The inspector page route uses Next.js
`notFound()` from a server component when `ENVIRONMENT != "local"`.
Combined with the API-side gate in A3 (which returns 404), the
inspector simply doesn't exist in non-local builds — no UI flash, no
button visible, no clue it was ever there.

**Test strategy:** one E2E (Playwright) test that:
1. Sets `ENVIRONMENT=local`, logs in as seeded staff user.
2. Triggers a fake-data fetch (test fixture, not real SF/CareStack).
3. Opens inspector page, asserts a known payload field is visible.
4. Opens person card, asserts timeline contains the corresponding
   event with no name/PII in `summary`.

Plus an env-gate test (Playwright):
1. Set `ENVIRONMENT=production`, build, navigate to
   `/dev/inspector/salesforce` → assert 404 page.
2. Set `ENVIRONMENT=staging`, repeat → assert 404 page.

**Codex review focus:**
- The env-gate helper is server-only (Next.js server component),
  not a client guard — a client-side check would still ship the
  bundle.
- JSON tree component does not eval-render anything; pure data
  render.
- The "fetch fresh" button is rate-limited or at minimum requires
  re-confirm so it can't be spammed.
- E2E test covers BOTH the local-positive and the
  production/staging-negative paths.

**Estimated size:** M.

---

### Task V1 — End-to-end smoke test on real provider data

**Depends on:** all of the above merged.

**Why:** This is the slice exit criterion. Until this passes once, the
phase is not done.

**Files:**
- Create:
  - `tests/e2e/test_phase1_slice.py` — manual / staged test, runs
    against a real SF sandbox + CareStack sandbox. Guarded by env var
    `E2E_REAL_PROVIDERS=1` so it doesn't run in normal CI.
- Modify:
  - `docs/ROADMAP.md` — mark Phase 1 complete + bump bars.
  - `docs/data-model/CATALOG.md` — flip planned → live for shipped
    tables.

**Smoke test outline (run in `ENVIRONMENT=local` only):**
1. Issue an MCP api_key via `make mcp-key`.
2. Run `salesforce_pull_leads` job manually → assert ≥ 1 person row,
   ≥ 1 interaction row of `kind='lead_created'` or `'lead_updated'`,
   ≥ 1 `ingest.raw_event` row with `source='salesforce'`.
3. Run CareStack appointments job manually → assert person count grew,
   ≥ 1 `ops.consultation` row, ≥ 1 interaction row of
   `kind='consultation_*'`. Assert `ops.consultation.raw_marketing`
   contains ONLY allowlisted fields.
4. Open `apps/web` → log in → see dashboard counts > 0 → click person
   → see timeline with correct events (summary contains zero PII) →
   open Inspector → see raw SF row + raw CareStack row.
5. From a separate Claude Code session, `claude mcp add` to register
   `apps/mcp` → call `resolve_person`, `get_person_timeline`,
   `list_recent_leads`, `get_inspector_payload` → assert results
   match the API.
6. Verify `audit.agent_tool_call` rows for every MCP call;
   `integrations.sync_run` rows for both worker invocations (closed
   with success status); corresponding `audit.access_log` rows from
   `AuditService.log_sync_run_summary`.
7. **Expanded PHI-in-logs check:** grep
   `docker compose logs api worker mcp` for the full PII fixture set
   (name, DOB, address, phone, email, MRN-like, the clinical-looking
   string from W2 fixtures) → assert ZERO matches.
8. **Inspector closure rehearsal:** stop containers, set
   `ENVIRONMENT=staging` in `.env.local`, restart → curl
   `/dev/inspector/salesforce/latest` → assert 404; navigate to the
   page in browser → assert Next.js 404; call `get_inspector_payload`
   from MCP → assert tool-not-found. This verifies the carve-out
   actually closes when env changes, before we ever deploy.

**Codex review focus:**
- Test does not hard-code real customer data; PII fixture set is
  defined as test data only.
- The PHI-in-logs check is a real grep against captured stdout, not
  a TODO.
- Step 8 (carve-out closure rehearsal) is asserted, not just
  documented.

**Estimated size:** M (mostly test code; harness work).

---

## 4. Sequencing & dependency graph

```
R1 (roadmap update)
 │
 ├── D1 (interaction)         ──┐
 ├── D2 (identity.source_link)─ ┤
 ├── D3 (ops.account)          ─┤  (parallel-able)
 └── D4 (ops.consultation)     ─┘
                                 │
                          A1 (auth) ───────────┐
                          A4 (integrations connect/status) ─┤
                          A2 (persons)  ───────┤
                          A3 (inspector, env-gated) ───────┐
                                               │           │
                          F1 (web scaffold) ───┤           │
                          F2 (login)        ───┤           │
                          F5 (/integrations Connect UI) ───┤
                                               │           │
                                               │   (F5 unlocks W1/W2 via "Sync now" — workers
                                                │    read account creds from integrations.integration_account)
                                                │
                                 ├── W1 (SF connector)         ┐
                                 └── W2 (CareStack connector)  ┤
                                                                │
                          F3 (dashboard+card) ─┤
                          F4 (inspector, env-gated) ─┘
                                               │
                          M1 (mcp scaffold) ───┐
                          M2 (mcp tools, get_inspector env-gated) ─┤
                          M3 (mcp cli)      ───┘
                                               │
                                               └── V1 (E2E smoke + carve-out closure rehearsal)
```

Suggested execution order (one PR per task, smallest interesting
chunks first):

1. R1
2. D1, D2, D3, D4 — parallel where reviewer bandwidth allows. Note
   D4 is now `ops.consultation`, NOT `phi.*` stubs.
3. A1 — unblocks the rest of the API + the frontend's auth.
4. **A4** — integrations connect/status endpoints. Unblocks F5 +
   replaces env-vars-only path for W1/W2.
5. F1 → F2 → **F5** — operator can now connect SF + CareStack from
   the UI. Without this step W1/W2 have no creds to use (the env-vars
   fallback was dropped during this revision).
6. W1 — first real data on the box, triggered via F5's "Sync now".
7. A2 + A3 in parallel — endpoints over W1's data. A3 includes the
   env-gate dependency.
8. F3 → F4 — dashboard + person card + Inspector pages.
9. W2 — second provider with marketing-only normalization +
   expanded redaction tests.
10. M1 → M2 → M3 — MCP server. M2 includes `get_inspector_payload`
    env-gated registration.
11. V1 — verify end-to-end + carve-out closure rehearsal.

Total: 19 PRs (R1 + 4 D + 4 A [A1-A4] + 2 W + 3 M + 5 F [F1-F5] + V1).
About one PR per ~½ day; phase can plausibly close in 2.5 working
weeks of solo dev + Codex review turnaround.

---

## 5. Cross-cutting concerns

### 5.1 Logging

- Every connector job, every MCP tool call, every API endpoint logs at
  INFO with `request_id` / `job_id`, `actor_id`, `person_uid` (when
  known), `event_kind`. Allowed structured fields: opaque ids,
  action codes, counts, durations.
- **Forbidden anywhere in logs (production AND local — the carve-out
  is for Inspector ONLY, not logs):**
  first/last name, email, phone, DOB, full address, MRN-like ids,
  any clinical free-text, payment / financing details, transcript
  fragments. The full forbidden list is the same fixture used by
  the W2 redaction test (Task W2).
- **How redaction is enforced:** structlog processor that drops or
  hashes any field matching the forbidden list, applied to every
  log call across `apps.*` and `packages.*`. Configured once in
  `packages/core/logging.py`; no per-module configuration. Tests in
  W2 verify the processor is wired in production-like config.
- Tests assert the no-PHI invariant explicitly for W2 (happy + error
  paths + traceback frames) and F3 (Person card render path —
  ensures `interaction.summary` and `payload` don't leak PII even
  if a misconfigured connector wrote them).

### 5.2 Auditing & sync journaling

Two separate concerns, two separate tables:

- **Operational journal:** `integrations.sync_run` — append-only
  log of every pull/push/cdc/webhook batch with `started_at`,
  `finished_at`, `status`, `stats` JSONB. Written by
  `IntegrationsService.open_sync_run` / `close_sync_run`.
- **Audit summary:** one row per terminated sync run, written via
  `AuditService.log_sync_run_summary(sync_run_id, provider, status,
  counts)` — lands in `audit.access_log` with the sync details in
  `extra`. Helper from FUS-23.

W1 and W2 use both: open the operational journal at start, close it
with stats at end, then log the audit summary. The two operations
together replace the (non-existent) `audit.sync_run` table that
earlier drafts of this plan referenced.

- MCP calls: `audit.agent_tool_call` per tool invocation (M1
  decorator).
- API reads of person/timeline: out of scope for Phase 1 (PHI access
  audit is Phase 8 runtime gating).

### 5.3 Local dev story

After Phase 1, `make dev` should bring up:
- Postgres + Redis (existing).
- `apps/api` (existing).
- `apps/worker` (existing).
- `apps/mcp` (new — Task M1).
- `apps/web` runs separately via `make web-dev` (Next.js dev server
  on `:3000`).

`make slice-demo` (optional add): provisions a seeded staff user,
runs W1/W2 with sandbox creds (provided via `.env.local`), and prints
URLs to dashboard + inspector.

---

## 6. Codex review checkpoints (handoff)

Plan-level review (this PR + the 2026-05-02 revision addressing
Codex review on PR #7):
- Does the slice scope match the answer to Q1 (depth-first)?
- Does the migration strategy match Q3 (per-domain)?
- Are the cross-package import rules consistent with `packages/CLAUDE.md`
  after FUS-31 merges?
- Are the deferrals (`context`/`workflow`/`encounter`/`segmentation`/
  `insight`, plus all `phi.*` clinical content) defensible?
- Is the **Inspector carve-out** (env-gated to `local`, documented
  in `packages/ingest/CLAUDE.md`, asserted by V1 closure rehearsal)
  acceptable as a time-bounded exception, or does Codex prefer the
  field-schema-profiler alternative? User has explicitly opted into
  the carve-out (memory: `feedback_inspector_local_carveout`).
- Does the **CareStack marketing-only scope** (no clinical content
  in normalization; allowlist in §2.2; `ops.consultation` not
  `phi.appointment`) hold up under Codex's PHI lens?

Per-task review focuses are noted inline above. The four
highest-stakes tasks for Codex's lane are:
- **D1** (`interaction.event` schema + partial UNIQUE constraint +
  no-PII summary/payload contract)
- **D4** (`ops.consultation` allowlist enforcement — first time
  marketing/PHI boundary is concrete)
- **W2** (CareStack connector — expanded redaction discipline:
  full PII fixture set, happy + error paths, traceback frames)
- **A3 + F4 + M2 env-gate** (the Inspector carve-out closure
  mechanism — must be testably enforced across API, web, and MCP
  surfaces, not just one)

---

## 7. Open follow-ups (out of Phase 1 plan, parking-lot)

- Capability matrix beyond "tool name allowlist" — Phase 5.
- **Inspector carve-out closure** (env-gate → real
  `actor.capability` `dev:raw_payload` check OR replace with the
  field-schema-profiler approach Codex proposed on PR #7) — Phase 8.
  Tracked in `packages/ingest/CLAUDE.md` and ROADMAP Phase 8.
- `phi.appointment` (clinical view of consultation), `phi.treatment_case`,
  `phi.transcript_raw`, `phi.extracted_fact` — Phase 6+ when
  clinical content actually flows.
- MCP write tools (`create_action`, `add_note`) — Phase 5+.
- Rate limiting on `/auth/login` — Phase 8 hardening.
- Bulk API for SF when first real org > 50k records — parking lot
  (see ROADMAP §7).

---

## 8. Acceptance criteria for Phase 1

Phase 1 is done when **all of these are true**:

1. R1 merged; ROADMAP exit criterion matches this scope.
2. All schema migrations from D1 (interaction), D2 (identity ext),
   D3 (ops.account), D4 (ops.consultation) applied cleanly on a
   fresh DB. **No `phi.*` migration in Phase 1.**
3. `apps/api`, `apps/worker`, `apps/mcp` all start in `docker compose
   up`.
4. `apps/web` builds and `npm run dev` serves `/login` successfully.
5. **Connect-via-UI works:** logged-in operator visits `/integrations`,
   clicks Connect on Salesforce → completes OAuth → returns to
   `/integrations` with status `connected`. Same flow for CareStack
   via API-key form. Both `integrations.integration_account` rows
   exist with encrypted tokens (FUS-22 `EncryptedString`); no
   plaintext token in API responses or logs.
6. W1 was triggered via the `/integrations` "Sync now" button (NOT
   manually invoked) and produced ≥ 1 `identity.person`, ≥ 1
   `ops.lead`, ≥ 1 `interaction.event` of `kind='lead_created'` or
   `'lead_updated'`.
7. W2 was triggered via "Sync now" and produced ≥ 1 additional
   `identity.person`, ≥ 1 `ops.consultation`, ≥ 1 `interaction.event`
   of `kind='consultation_*'`. The `ops.consultation.raw_marketing`
   payload contains ONLY allowlisted fields (verified by inspecting
   one row).
8. Operator dashboard shows non-zero counts → person card shows
   timeline → `interaction.summary` contains zero PII (verified by
   inspection of rendered text) → Inspector shows raw payload for
   both providers (visible because `ENVIRONMENT=local`).
9. MCP client (Claude Code from another machine, `ENVIRONMENT=local`)
   connects, calls `resolve_person` + `get_person_timeline` +
   `list_recent_leads` + `get_inspector_payload`, all return data,
   all four leave `audit.agent_tool_call` rows.
10. **Sync journaling + audit:** an `integrations.sync_run` row exists
    per W1 and W2 invocation (closed `status` reflects success /
    failure / partial), AND a corresponding `audit.access_log` row
    exists per sync_run via `AuditService.log_sync_run_summary`.
11. `docker compose logs api worker mcp` grep for the full PII
    fixture set (name / DOB / email / phone / address / MRN-like /
    clinical-looking string) returns ZERO matches. Same grep for any
    OAuth access_token / refresh_token / CareStack api_key value
    returns ZERO matches.
12. **Carve-out closure rehearsal** (V1 step 8): with
    `ENVIRONMENT=staging`, the API endpoint, the `apps/web`
    Inspector route, and the MCP `get_inspector_payload` tool ALL
    become unreachable (404 / 404 / not-listed). Verified, not just
    documented.

When (1)–(12) hold, V1 PR merges and Phase 1 closes.
