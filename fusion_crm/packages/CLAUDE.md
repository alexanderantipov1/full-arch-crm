# CLAUDE.md — `packages/` (shared library code)

> Library code consumed by `apps/api`, `apps/worker`, future apps,
> and any future microservice. Read the root `CLAUDE.md` first.

## Layout per package

Every domain package follows the same layout — keep it that way.

```
packages/<domain>/
├── __init__.py        package docstring; do NOT re-export
├── models.py          SQLAlchemy ORM models (one schema per domain)
├── schemas.py         Pydantic DTOs (input/output)
├── repository.py      data access only — no business logic
└── service.py         business logic; THE public surface
```

Add new files here only when there's a real reason
(`enums.py`, `events.py`, `policies.py`, ...). Do not pre-create
empty modules.

## Layering rules

```
api / worker / tools  →  service  →  repository  →  DB
                                ↘  audit / identity / tenant (cross-cutting)
```

- **Routers / jobs / tools** depend on **services** only.
- **Services** depend on **repositories** + other **services**.
- **Repositories** depend on **`AsyncSession`** + the package's own
  models. Nothing else.
- Never import a repository from outside its own package.
- Never import a model from outside its own package — use the DTO.

## Cross-package imports — what's allowed

The matrix below covers the M1-slice domain set plus the Phase 1 slim
`interaction` package (added 2026-05-05), the multi-tenancy root
`tenant` (added 2026-05-09 with ENG-123 / ADR-0003), the
operator-account email outreach domain `outreach` (added 2026-05-10
with ENG-133 / ADR-0004), `insight` (added 2026-06-02 with ENG-314),
`agent_runtime` (added 2026-06-04 for application-owned agent
orchestration), and `catalog` (added 2026-06-13 with ENG-420 for
workspace-wide reference data, starting with the CareStack
procedure-code/CDT catalog), and `enrichment` (added 2026-06-15 with
ENG-439 / Block F for the manual-enrichment store — our own fields
layered over canonical entities). Domains shipped in later milestones
(`context`, `workflow`, `encounter`, `segmentation`) are added when
they land.

| From → To     | tenant | identity | actor | auth | ops | phi | integrations | interaction | outreach | insight | catalog | audit | ingest | tools | core |
|---------------|--------|----------|-------|------|-----|-----|--------------|-------------|----------|---------|---------|-------|--------|-------|------|
| tenant        |   —    |    ✗     |  ✗   |  ✗  |  ✗  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✗    |   ✗   |  ✓   |
| identity      |   ✓    |    —     |  ✗   |  ✗  |  ✗  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✗    |   ✗   |  ✓   |
| actor         |   ✓    |    ✓     |  —   |  ✗  |  ✗  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✗    |   ✗   |  ✓   |
| auth          |   ✓    |    ✓     |  ✓   |  —  |  ✗  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✗    |   ✗   |  ✓   |
| ops           |   ✓    |    ✓     |  ✗   |  ✗  |  —  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   ✓     |   ✓   |   ✗    |   ✗   |  ✓   |
| phi           |   ✓    |    ✓     |  ✗   |  ✗  |  ✗  |  —  |      ✗       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✗    |   ✗   |  ✓   |
| integrations  |   ✓    |    ✓     |  ✓   |  ✗  |  ✗  |  ✗  |      —       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✗    |   ✗   |  ✓   |
| interaction   |   ✓    |    ✗     |  ✗   |  ✗  |  ✗  |  ✗  |      ✗       |      —      |    ✗     |    ✗    |   ✓     |   ✗   |   ✗    |   ✗   |  ✓   |
| outreach      |   ✓    |    ✓     |  ✗   |  ✗  |  ✓  |  ✗  |      ✗       |      ✗      |    —     |    ✗    |   ✗     |   ✓   |   ✗    |   ✗   |  ✓   |
| insight       |   ✗    |    ✗     |  ✗   |  ✗  |  ✗  |  ✗  |      ✗       |      ✗      |    ✗     |    —    |   ✗     |   ✗   |   ✗    |   ✗   |  ✓   |
| catalog       |   ✗    |    ✗     |  ✗   |  ✗  |  ✗  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   —     |   ✗   |   ✗    |   ✗   |  ✓   |
| enrichment    |   ✓    |    ✗     |  ✓   |  ✗  |  ✗  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✗    |   ✗   |  ✓   |
| marketing     |   ✓    |    ✗     |  ✗   |  ✗  |  ✗  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✗    |   ✗   |  ✓   |
| audit         |   ✗    |    ✗     |  ✗   |  ✗  |  ✗  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   ✗     |   —   |   ✗    |   ✗   |  ✓   |
| ingest        |   ✓    |    ✓     |  ✗   |  ✗  |  ✓  |  ✗  |      ✗       |      ✓      |    ✗     |    ✗    |   ✓     |   ✓   |   —    |   ✗   |  ✓   |
| tools         |   ✓    |    ✓     |  ✓   |  ✗  |  ✓  |  ✓  |      ✗       |      ✓      |    ✓     |    ✓    |   ✓     |   ✓   |   ✗    |   —   |  ✓   |
| agent_runtime |   ✓    |    ✗     |  ✓   |  ✗  |  ✗  |  ✗  |      ✓       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✗    |   ✓   |  ✓   |
| attribution   |   ✓    |    ✓     |  ✗   |  ✗  |  ✓  |  ✗  |      ✗       |      ✗      |    ✗     |    ✗    |   ✗     |   ✓   |   ✓    |   ✗   |  ✓   |

Notes on the rows:

- **`tenant`** — multi-tenancy root. Owns `tenant.tenant`,
  `tenant.location`, `tenant.integration_credential`,
  `tenant.setting`. May write audit; otherwise imports only `core`.
  Every other per-tenant domain references `tenant.tenant.id` via a
  plain UUID column (DB-level FK, no Python import). See
  `packages/tenant/CLAUDE.md` and ADR-0003.
- **`actor`** — owns the unified actor (human / AI / system). May
  read identity (e.g. for `normalise_email` / `normalise_phone`) and
  write audit. Nothing else.
- **`auth`** — credentials, sessions, API keys, portal accounts. May
  reference `actor.actor` (subject_type = "actor") and
  `identity.person` (1:1 portal_account ↔ person). May write audit.
  Tools cannot import auth — auth is the API/MCP infrastructure
  surface, not an agent-callable domain.
- **`integrations`** — external provider state (Salesforce,
  CareStack, …). May resolve external user → `actor` (the SF user
  who owns a Lead becomes an actor) and writes audit via the OAuth
  + sync_run helpers added in FUS-23.
- **`interaction`** — Phase 1 slim subset: only `interaction.event`
  (the timeline). Imports ONLY `core`; does not import any other
  domain. Cross-references go through `person_uid` (UUID column) —
  the model declares DB-level FK strings to `identity.person.id`,
  `ingest.raw_event.id`, `actor.actor.id` but never imports those
  packages in Python. Workers (W1/W2) and the API timeline
  endpoint write/read through `InteractionService`. Append-only at
  the model layer; no update/delete service methods in Phase 1.
  Full v0.2 package (event_content, transcripts, message artifacts)
  ships in M3 with FUS-16.
- **`outreach`** — operator-account email outreach (ADR-0004).
  Owns `outreach.template`, `outreach.campaign`, `outreach.send`,
  `outreach.suppression`, `outreach.outbound_queue`. Reads
  `identity` (recipient lookup) and `ops` (lead/campaign context).
  Reads `tenant.integration_credential` ONLY via UUID columns
  (`mailbox_credential_id`) — no Python import of the tenant
  models. Writes `audit` for every template state change and every
  render. Never reads `phi`. The full enqueue + send pipeline lives
  in ENG-132 (sibling).
- **`insight`** — semantic analytics catalog proposals and approved
  catalog versions. Owns reviewed business-meaning storage for
  manager analytics, dashboards, chat, and agent tools. Imports only
  `core` in ENG-314; review audit is a follow-up via write-only
  `AuditService`. Version rows are append-only at the service layer.
- **`analytics`** — route-facing semantic analytics API/service
  contracts. ENG-315 uses it for catalog proposal review DTOs and thin
  service orchestration; durable catalog storage remains in `insight`.
  The fact-builder read-model (ENG-506+) derives `fact_patient_journey`
  from canonical domains **read-only via services** — including
  `interaction`, `ops`, `identity`, `attribution`, `actor`, and (ENG-538/539)
  `ingest` (`treatment_procedure_code_ids_by_patient`) and `catalog`
  (`resolve_procedure_codes`, for the `case_type` dimension). It never reads
  `phi` and never imports another domain's models/repositories.
- **`agent_runtime`** — application-owned agent orchestration, provider
  health checks, guardrails, approvals, tool projection, and future run
  state. It may call tenant credential services, provider adapters under
  `integrations`, governed `tools`, and future audit services. It must
  never import repositories or bypass the tool/service boundary.
- **`catalog`** — workspace-wide reference data sourced from external
  systems (ENG-420). First member is the CareStack procedure-code
  (CDT/CPT) catalog. Intentionally NOT tenant-scoped — CDT codes are
  the ADA-published US dental code standard. Imports only `core`. Read
  by `ops`, `interaction`, future analytics, and the AI-agent `tools`
  layer via `CatalogService.resolve_procedure_codes`. Sync is
  read-only against CareStack (operator backfill script +
  low-frequency Cloud Run Job).
- **`enrichment`** — manual-enrichment store (ENG-439, Block F). Owns
  `enrichment.record_annotation`: *our own* fields layered over canonical
  entities, written from the staff UI now and the chat / agent action
  paths (Block G) later, all through one `EnrichmentService`. References
  `tenant.tenant.id` and `actor.actor.id` via plain UUID columns
  (DB-level FK, no Python import). Writes `audit` for every annotation via
  the write-only `AuditService`. Never reads `phi`; the annotation `value`
  (which may hold free text / PII) never enters the audit row. The 9th
  canonical schema (user-approved). See `packages/enrichment/CLAUDE.md`.
- **`attribution`** — derived lead source distribution chain (added 2026-06-15
  with ENG-446 / ENG-447). Owns `attribution.source_node` (the
  vendor→channel→campaign→ad_set→ad→form chain), `attribution.lead_attribution`
  (resolved per person), and `attribution.mapping_rule` (editable pattern→node
  rules). Tenant-scoped. The resolver (ENG-448) reads `ingest` (raw lead
  payloads), `identity` (source_link ordering), and `ops` (lead) to derive the
  chain, and writes `audit` for manual enrichment. Derived data — re-buildable
  from raw evidence, carries no PHI.

- **`marketing`** — aggregate, non-PHI ad-spend + campaign metrics pulled
  read-only from Google/Meta/TikTok ads (added 2026-06-15). Owns
  `marketing.ad_campaign` and `marketing.ad_metric_daily`. References
  `tenant.tenant.id` via a plain UUID column; may write `audit`. Imports only
  `tenant`, `audit`, `core`. The per-source ingest connectors live in
  `packages/ingest/*_campaign_service.py` and write here through
  `MarketingService` — so **`ingest → marketing` is permitted (service-only),
  analogous to `ingest → ops`** (not shown as a matrix column, same as
  `enrichment`). Person-linked marketing signals (leads/calls/SMS) do NOT live
  here — they stay in `identity` / `ops` / `interaction`.

Crossings happen via **services**, not models or repositories.

## Sessions and the unit of work

- Repositories never `commit()` and never `rollback()`.
- Services never `commit()` and never `rollback()`.
- Only the **caller boundary** commits:
  - API: the `get_db` FastAPI dependency.
  - Worker: the `async_session()` context manager.
  - Scripts/tests: same `async_session()`.
- Use `await session.flush()` inside repositories when you need an
  ID before commit; never `await session.commit()`.

## Pydantic schemas

- Inputs end with `In`, outputs with `Out`.
- Outputs use `model_config = ConfigDict(from_attributes=True)` so
  they accept ORM objects via `.model_validate(obj)`.
- Never embed an ORM model in a schema; build the DTO in the service.
- PHI-bearing fields live ONLY in `packages/phi/schemas.py`. If you
  catch yourself adding a clinical field to `ops` or `identity` —
  stop and re-check.

## Naming

- Tables: snake_case singular (`patient_profile`, `followup_task`).
- Columns: snake_case.
- FKs use the constraint convention in `packages/db/base.py`.
- IDs: `id` for the table's own PK, `<entity>_id` or `person_uid`
  for references. `person_uid` is the ONE name for the global person
  reference across every domain.
- `tenant_id` is the ONE name for the tenant FK across every per-tenant
  domain.
