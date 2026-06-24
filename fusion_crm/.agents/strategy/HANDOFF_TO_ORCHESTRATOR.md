# Handoff To Orchestrator

This file records Strategy and Architecture topics that are ready to be
evaluated by the Orchestrator.

Strategy and Architecture agents may prepare structured handoff requests here.
They must not launch workers, assign execution tasks directly, or modify
product code.

The Orchestrator is responsible for validating scope, creating the mission
folder, creating or syncing Linear issues, defining ownership, assigning
workers, running verification, integration, and final handoff.

Handoff rule:

```text
Strategy proposes, Orchestrator disposes.
```

## Template

### <handoff title>

- **Readiness status:** draft / needs decision / ready for orchestrator
- **Business goal:** <what business outcome this execution mission should support>
- **Why now:** <trigger, priority, or timing rationale>
- **Expected outcome:** <observable output or state after completion>
- **Assumptions:** <assumptions the Orchestrator should validate>
- **Architecture constraints:** <repo, compliance, domain, and integration constraints>
- **Suggested decomposition:** <suggested tasks, ownership areas, and sequencing>
- **Parallel safety:**
  - **Task class:** normal / tiny_fix / hotfix / contract_change
  - **Expected owned paths:** <paths the task should own>
  - **Expected shared contracts:** <schemas, tool envelopes, read models, deploy contracts, or none>
  - **Likely conflicts:** <active or likely overlap with other work>
  - **Cross-runtime review:** <required/recommended/not required, and why>
  - **Recommended merge order:** <contract first, implementation second, hotfix ahead, etc.>
- **Risks:** <business, technical, operational, data, compliance, or delivery risks>
- **Human decisions needed:** <open decisions before or during orchestration>
- **Notes for Orchestrator:** <scope validation, Linear, ownership, verification, or integration notes>

## Active Handoffs

### Revenue Intelligence Analytics Platform V1

- **Readiness status:** ready for orchestrator. Operator explicitly directed
  Strategy to create the Linear mission, so project "Revenue Intelligence
  Analytics Platform V1" + epic ENG-504 + children ENG-505..ENG-529 already
  exist under team Engineering, and mission docs are written at
  `.agents/orchestration/revenue-intelligence-analytics-v1/`. No worker launched,
  no branch, no product code — execution still requires Orchestrator acceptance
  and operator go.
- **Source candidate:** `.agents/strategy/CANDIDATE_MISSIONS.md` → "Revenue
  Intelligence Analytics Platform V1".
- **Source spec:** `market.md`. Strategy plan:
  `.agents/strategy/REVENUE_INTELLIGENCE_ANALYTICS_PLATFORM_PLAN.md`.
- **Business goal:** A unified Revenue Intelligence Platform tracing every patient
  from ad spend to collected revenue: 14 analytics pages + `fact_patient_journey`
  + derived metrics + global filters (incl. per-location) + CSV/Excel export.
- **Why now:** Marketing-first funnel is the current priority; 5 analytics pages
  already shipped; operator provided the full spec. Money metrics (ENG-283),
  attribution (ENG-446), multi-location data, and person-anchored funnel dating
  (ENG-481) already exist.
- **Expected outcome:** new `analytics` schema + person-anchored, rebuildable
  `fact_patient_journey` (nullable + per-field provenance); shared filter/metric
  contract; the 14 pages; missing-field enablement via auto-resolver OR manual
  enrichment; export + drill-down.
- **Assumptions the Orchestrator must validate:** read-only staff surface;
  dev-phase full-visibility; `packages/analytics` exists and composes in
  `apps/api`; agents never touch DB; logs PHI-free; raw payloads stay in
  `ingest.raw_event`; fact-builder arq job ships gated off for prod.
- **Architecture constraints:** new `analytics` schema is an operator-approved
  addition to invariant #1 (rebuildable projection, never a source of truth; file
  an ADR in B0.1); migrations immutable; no business logic in routes (#5); no DB
  from agents (#6); person spine `identity.person.id`.
- **Suggested decomposition:** B0 foundation (ENG-505→506→507→508) → B1
  enablement (ENG-509..513, alongside once ENG-505 frozen) → B2 14 pages
  (ENG-514..527, each also gated on its dimension's B1) → B3 closeout
  (ENG-528, ENG-529).
- **Parallel safety:**
  - **Task class:** `contract_change` (new DB schema, new fact table, shared
    filter contract for 14 pages).
  - **Expected owned paths:** `packages/analytics/**`,
    `apps/web/app/(staff)/analytics/**`, `apps/web/lib/api/{schemas,hooks}/**`,
    `docs/analytics/**`, `apps/worker/jobs/fact_patient_journey_*.py`.
  - **Expected shared contracts:** `analytics` schema +
    `analytics.fact_patient_journey`, `AnalyticsFilters`/`TimeRange` DTO,
    derived-metric definitions, provenance precedence; shared paths
    `apps/api/routers/dashboard.py`, `apps/web/components/layout/AppShell.tsx`,
    `packages/db/alembic/versions/**`, `packages/{actor,attribution,marketing}/**`.
  - **Likely conflicts:** concurrent migration work (chain in one branch);
    actor/attribution/marketing edits from B1; nav-shell edits across pages.
  - **Cross-runtime review:** required (new schema, fact table, shared contract).
  - **Recommended merge order:** B0.1 → B0.2 → B0.3 → B0.4; B1 alongside after
    B0.1; pages after B0.3; B3.2 verification last.
- **Risks:** treatment-accepted/surgery classification gap (ENG-511,
  discovery-gated — flag `Needs decision:` rather than guessing); operational cost
  basis (ENG-522) needs operator input; attribution maturity caps vendor/campaign
  richness (show "Unattributed", never drop); new schema scope creep; number drift
  vs existing dashboards (reconcile on real data before merge).
- **Human decisions needed:** CareStack treatment-acceptance + surgery
  classification source; operational cost basis for cost-per-conversion;
  provenance precedence confirmation (manual > auto > unresolved); Marketing
  Performance extend-vs-new route.
- **Notes for Orchestrator:** Accept the handoff and record the
  `Handoff: strategy → orchestrator` event in runtime files before execution.
  Linear already exists (operator-directed); validate scope/ownership and assign
  workers from B0.1. Do not launch workers until the operator approves execution.
  Production enablement of the fact-builder job is a separate operator-gated step
  per `docs/DEPLOYMENT_RULES.md`.

### Interactive Corporate Messenger Layer (Mattermost) V1

- **Readiness status:** accepted by orchestrator on 2026-06-15; Linear project +
  epic ENG-433 + children ENG-434..ENG-442 created under team ENG. Mission
  folder: `.agents/orchestration/interactive-messenger-layer-v1/`. No worker
  launched yet — awaiting user go for Block A (ENG-434).
- **Source candidate:** `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "Interactive Corporate Messenger Layer (Mattermost) V1"
- **Source strategy spec:**
  `.agents/strategy/INTERACTIVE_MESSENGER_LAYER_DOCTRINE.md`
- **Business goal:** Create a Linear-backed mission that builds an interactive
  corporate messenger layer on self-hosted Mattermost: an internal team channel
  plus a bidirectional automation/agent interface (events out, commands +
  approvals + manual enrichment in), with Mattermost treated as an external
  provider behind a thin `ChatProvider` adapter.
- **Why now:** The clinic currently coordinates patient matters over
  uncontrolled WhatsApp/SMS; the platform mission is to replace that. Full-
  fidelity ingestion makes field-condition notification rules possible. Self-
  hosting keeps data in-perimeter (PHI-future-proof, no vendor BAA), and a
  marketing-first de-identified default lets it ship now.
- **Expected outcome:**
  1. Provider-agnostic core (`ChatProvider` + `MattermostAdapter`); per-tenant
     credentials in `tenant.integration_credential`.
  2. Outbound outbox + `notification_rule` (field-condition) + dispatch worker +
     seeds for the four first-wave events.
  3. Signed inbound (buttons + thread replies) → `ingest.raw_event`
     (`source="mattermost"`) → curated domain mapping; `actor_identifier`
     (`mattermost_user_id`).
  4. `record_annotation` manual enrichment (chat + staff frontend, one path).
  5. Agent human-in-the-loop approve/reject via services/tools only.
  6. ADR-0006 + audit actions; local infra under compose profile `chat`;
     production infra deferred to its own DEPLOYMENT_RULES-gated block.
- **Assumptions the Orchestrator must validate:**
  - Marketing-first, de-identified default (`person_uid` + deep link), `phi_mode`
    reserved; not patient-facing.
  - Mattermost self-hosted Team Edition, official image, not forked, pinned
    version, English DB locale, its own separate database (invariant #1 intact).
  - Local and prod stay separate; verify current `infra/docker/` state before
    assigning the infra block.
  - The new `enrichment` domain placement is unconfirmed (see human decisions).
- **Architecture constraints:**
  - Follow root `CLAUDE.md`/`AGENTS.md` and `.agents/CLAUDE.md`/`.agents/AGENTS.md`.
  - Invariants #5 (outbox+worker, no business logic in routes), #6 (agents via
    services/tools, no DB), #10 (tenant creds in `integration_credential`).
  - Inbound endpoints must verify signature/token + URL challenge.
  - Production infra only after ADR-0006 and per `docs/DEPLOYMENT_RULES.md`,
    never mixed with feature PRs; Mattermost is stateful (not scale-to-zero
    Cloud Run).
- **Suggested decomposition:** doctrine Blocks A–I; merge order A → C → B → D →
  E → F → G → H, with I (production) last and isolated.
- **Parallel safety:**
  - **Task class:** `contract_change` (new durable schema, new provider kind,
    new public route, new `raw_event` source, new audit taxonomy, deployment).
  - **Expected owned paths:** `packages/integrations/**`,
    `packages/<enrichment-domain>/**`, `apps/api/routers/` chat inbound module,
    `apps/worker/jobs/notification_*.py` and chat-inbound job,
    `packages/db/alembic/versions/**` (new revisions),
    `infra/docker/**` (compose + `mattermost/`), `docs/decisions/ADR-0006-*.md`,
    `.agents/strategy/**`, relevant `CLAUDE.md` updates.
  - **Expected shared contracts:** `integrations` schema
    (`notification_rule`, `notification_outbox`),
    `tenant.integration_credential` provider kinds, `ingest.raw_event` `source`
    values, `audit` action taxonomy, public API route contract,
    deployment/env contract.
  - **Likely conflicts:** any concurrent migration work (chain in one branch per
    solo-dev policy); `tenant.integration_credential` / `IntegrationCredential`
    service edits; `apps/worker` cron registration.
  - **Cross-runtime review:** required — touches migrations, a public endpoint,
    audit, secrets, and deployment.
  - **Recommended merge order:** local infra (A) → schema/contract (C) →
    adapter+outbound (B) → rules+events (D) → signed inbound (E) → enrichment (F)
    → agent HITL (G) → governance/ADR (H) → production infra (I, isolated PR).
- **Risks:** PII leak if templates are not de-identified; unsigned/misverified
  inbound is an injection surface; self-hosting adds a stateful service to
  operate; durable-schema and public-route changes need careful sequencing.
- **Human decisions needed:** `record_annotation` domain placement; Mattermost
  version pin + cadence; prod host shape and `chat.*` hostname/TLS; prod
  Mattermost DB placement; canonical `event_type` taxonomy; retention/footprint.
- **Notes for Orchestrator:** Strategy proposes; Orchestrator must accept this
  handoff and create/link Linear issues before any worker is launched. Suggested
  first execution step is Block A (local, reversible). Defer Block I until
  ADR-0006 is accepted and DEPLOYMENT_RULES preflight passes. Record the
  Strategy → Orchestrator `Handoff:` in mission runtime files on acceptance.

### Data Intelligence Agent Local Tooling V1

- **Readiness status:** accepted by orchestrator on 2026-05-30; Linear
  structure created under `Semantic Context And Analytics Foundation` as
  ENG-286 with child issues ENG-287 through ENG-299.
- **Source candidate:** `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "Data Intelligence Agent Local Tooling V1"
- **Source strategy spec:**
  `.agents/strategy/DATA_INTELLIGENCE_AGENT_LOCAL_TOOLING_MISSION_SPEC.md`
- **Business goal:** Create a Linear-backed mission that operationalizes the
  internal Data Intelligence Agent as a safe local read-only data discovery and
  profiling lane. The agent should help the team understand real local data
  shape, source coverage, linkage quality, semantic gaps, and evidence
  readiness without direct database access, raw SQL, or raw provider payload
  output.
- **Why now:** The Semantic Context And Analytics Foundation is in place and
  connected to manager dashboard surfaces. The next high-leverage step is to
  let an internal agent inspect real local data through approved tools so new
  catalog terms, read models, query specs, and backend service tasks are based
  on observed evidence rather than assumptions.
- **Expected outcome:**
  1. The existing Linear umbrella `Semantic Context And Analytics Foundation`
     remains the parent, and a child mission/project or issue tree exists
     under it for Data Intelligence Agent Local Tooling V1.
  2. Mission runtime state records the Strategy to Orchestrator `Handoff:`.
  3. The Orchestrator creates issues for policy/allowlist, service contract,
     dataset discovery, field profiling, linkage profiling, evidence coverage,
     bounded masked samples, semantic mapping proposals, gap briefs, audit,
     workbench visibility, and verification.
  4. Workers are not launched until Linear issues exist and the human approves
     execution.
  5. The final implementation, when later approved, exposes only approved
     service/tool paths and proves denial of raw SQL, direct DB access, raw
     payload output, PHI output, uncapped samples, and writes.
- **Assumptions the Orchestrator must validate:**
  - ENG-279 remains contract-only; this mission is the implementation and
    operationalization follow-up.
  - Dashboard MSW fallback for real backend data has been removed by Claude
    Code, per human report; Orchestrator should verify current git state before
    any frontend issue is assigned.
  - Internal users are currently authorized for row-level visibility, but
    Data Intelligence row-level access must still go through caps, masks, and
    audit/logging.
  - PHI remains denied in V1.
  - Exports, XLSX, scheduled reports, and broader role matrices remain out of
    scope.
- **Architecture constraints:**
  - Follow root `CLAUDE.md` and `AGENTS.md`.
  - Follow `.agents/CLAUDE.md` and `.agents/AGENTS.md` for mission/runtime
    state.
  - Agents do not access the database directly.
  - No raw SQL from agents, LLM planners, dashboards, chat, or workbench code.
  - Tool calls go through `packages.tools`; tools call services only.
  - Tools must not call repositories or `session.execute(...)`.
  - PHI access goes through `PhiService` with audit; this V1 denies PHI output.
  - Raw provider payloads remain evidence storage and are not ordinary outputs.
  - Workbench visibility must be local/dev gated and must not make `.agents/`
    a product runtime dependency in production.
  - No deployment/env/secret/OAuth/CORS/Cloud Run/deploy workflow changes
    unless explicitly re-scoped after reading `docs/DEPLOYMENT_RULES.md`.
- **Suggested decomposition:**
  - **DIA-01 — Mission Setup And Linear Sync:** Create mission folder,
    runtime state, Linear mapping, board, decision log, and handoff event.
  - **DIA-02 — Tool Policy And Allowlist:** Define datasets, fields, data
    classes, limits, masks, denied fields, and audit fields.
  - **DIA-03 — Data Intelligence Service Contract:** Define service-owned DTOs
    and methods for discovery, profiling, linkage, evidence coverage, samples,
    mapping proposals, and gap briefs.
  - **DIA-04 — Query Registry And Dataset Discovery Tool:** Expose safe
    discovery of registry entries and profiling targets.
  - **DIA-05 — Field Profile Tool:** Return row counts, null rates, top values,
    distinct posture, warnings, and data-class markings for allowlisted fields.
  - **DIA-06 — Linkage And Source Coverage Tool:** Measure Salesforce lead to
    `person_uid`, `person_uid` to CareStack patient, and source-reference
    coverage with bounded masked gap examples.
  - **DIA-07 — Evidence Coverage Tool:** Profile consultation, treatment,
    payment, owner, location, campaign, and source evidence availability.
  - **DIA-08 — Bounded Masked Sample Tool:** Return small masked examples for
    local data-shape understanding while denying PHI/raw payload output.
  - **DIA-09 — Semantic Mapping Proposal Generator:** Produce review-only
    mapping proposals for source/campaign/channel/status normalization.
  - **DIA-10 — Gap Brief Writer:** Produce stable briefs with severity,
    affected questions, evidence summary, recommended Linear issue title,
    blockers, and suggested owner.
  - **DIA-11 — Audit And Tool Call Logging:** Log successful and denied calls
    with actor/session, tool, dataset, fields, filters, data classes, limits,
    masks, status, and timestamp.
  - **DIA-12 — Local Workbench Visibility:** Add or extend local-only workbench
    docs/status/output visibility without MSW dependency for real backend data.
  - **DIA-13 — Verification And Production Review:** Verify positive and
    denial paths, architecture invariants, local gating, and no raw output
    leakage.
- **Risks:**
  - Generic data-browser creep. Mitigation: deny-by-default allowlist and no
    SQL input.
  - Sensitive data leakage through logs or reports. Mitigation: masking,
    data-class markings, capped samples, and log redaction.
  - Tool outputs becoming product truth. Mitigation: mapping proposals and gap
    briefs are review-only until catalog/read-model issues accept them.
  - Row-level internal tooling policy leaking into manager chat. Mitigation:
    keep Data Intelligence Agent internal-builder only; manager chat remains
    query-registry and policy-preflight driven.
- **Human decisions needed:**
  1. Confirm default row sample limit `25` and hard cap `100`.
  2. Confirm default top-value cap `50` and hard cap `250`.
  3. Confirm whether DIA-12 is a child route or an extension of
     `/dev/semantic-analytics`.
  4. Confirm PHI denied for V1.
  5. Confirm exports denied for V1.
- **Notes for Orchestrator:**
  - Parent Linear umbrella:
    "Semantic Context And Analytics Foundation".
  - Recommended child Linear mission/project title:
    "Data Intelligence Agent Local Tooling V1".
  - Recommended mission folder:
    `.agents/orchestration/data-intelligence-agent-local-tooling-v1/`.
  - Continue under the existing Semantic Context And Analytics Foundation
    umbrella; do not create a second top-level umbrella for this work.
  - Create Linear issues before assigning any Worker.
  - Record the Strategy to Orchestrator `Handoff:` event before execution.
  - Do not launch Workers until the human approves execution after Linear issue
    creation.
  - Use the full task detail and acceptance criteria from
    `.agents/strategy/DATA_INTELLIGENCE_AGENT_LOCAL_TOOLING_MISSION_SPEC.md`.

### Semantic Context And Analytics Foundation

- **Readiness status:** needs decision
- **Source candidate:** `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "Semantic Context And Analytics Foundation"
- **Source strategy plan:**
  `.agents/strategy/SEMANTIC_CONTEXT_ANALYTICS_FOUNDATION_PLAN.md`
- **Business goal:** Build the shared semantic and analytics foundation that
  lets Fusion CRM reuse the same business definitions, query specs, policy
  checks, read models, and service-owned analytics across manager dashboards,
  manager AI chat, internal Data Intelligence agents, future reports, and
  workflow-ready context.
- **Why now:** The product is converging on analytics-heavy workflows:
  PM/Analyst dashboards, Salesforce-to-CareStack lead provenance, treatment
  and payment visibility, manager chat, and future agents. Without a shared
  semantic layer, each surface will reinterpret metrics and cohorts
  independently.
- **Expected outcome:**
  1. A first manager analytics question set exists and drives scope.
  2. A Semantic Analytics Catalog defines the first business terms and data
     class rules.
  3. A structured query spec lets LLM planners and UI clients express approved
     analytics requests without SQL.
  4. Policy preflight blocks or clarifies unsafe requests before execution.
  5. A typed query registry and analytics service layer execute allowlisted
     queries for dashboard, chat, and internal agent clients.
  6. First read models or service-computed views support lead conversion, paid
     leads, consultation follow-up, and treatment revenue.
  7. Data Intelligence Agent V1 can inspect local data only through approved
     read-only tools and produce mapping/gap briefs.
  8. Manager AI Chat V1 can use the same foundation to answer approved
     production questions with explainability and audit.
- **Assumptions the Orchestrator must validate:**
  - Existing provenance and raw-to-context strategy docs remain authoritative
    for evidence capture, semantic facts, and context packs.
  - The first execution slice should probably start with manager questions and
    semantic catalog before backend query services are built.
  - Local exploratory samples for builders are acceptable only through a
    read-only allowlisted Data Intelligence tool, not direct agent DB access.
  - Production manager chat should start from allowlisted query specs and
    policy preflight.
  - Treatment/payment and balance-related terms may be billing-sensitive or
    PHI-adjacent until classified.
- **Architecture constraints:**
  - Follow root `CLAUDE.md` and `AGENTS.md`.
  - Agents do not access the database directly.
  - No raw SQL from LLM planners, manager chat, dashboard code, or internal
    agents.
  - Routes call services; services call repositories; repositories are
    data-only.
  - PHI access goes through `PhiService` with audit.
  - `identity.person.id` remains the canonical `person_uid`.
  - Raw provider payloads are not ordinary production dashboard, chat, or agent
    outputs.
  - `ops` remains PHI-free.
  - Analytics business logic must live in backend services/read models, not
    browser-only filters.
  - No deployment/env/secret/OAuth/CORS/Cloud Run/deploy workflow changes
    unless explicitly re-scoped after reading `docs/DEPLOYMENT_RULES.md`.
- **Suggested decomposition:**
  - **Task A — Manager Analytics Questions V1:** Document 20 to 30 real
    manager questions and group them by lead source, consultation, follow-up,
    treatment, payment, owner, location, and risk.
  - **Task B — Semantic Analytics Catalog V1:** Define first business terms,
    synonyms, exact meanings, sources, data classes, permissions, row-level
    rules, allowed fields, versions, and review status.
  - **Task C — Structured Analytics Query Spec:** Define JSON schema,
    validation, examples, allowed intents, dimensions, metrics, outputs, and
    clarification behavior.
  - **Task D — Policy Preflight:** Define and implement checks for role, data
    classes, PHI, billing, row-level output, export, and audit requirements.
  - **Task E — Analytics Query Registry V1:** Create typed query registration
    with params schema, result schema, allowed roles, environments, data
    classes, row limits, sample policy, export policy, audit requirements, and
    AI-chat safety flags.
  - **Task F — Analytics Services V1:** Implement initial service-owned
    queries for lead source profile, conversion funnel, paid leads,
    consultation follow-up, and revenue evidence.
  - **Task G — Read Models V1:** Build service-computed or persisted read
    models for `lead_conversion`, `paid_leads`, `consultation_followup`, and
    `treatment_revenue`.
  - **Task H — Data Intelligence Agent V1:** Define the role, skill contract,
    local read-only data tool access, sample limits, masking behavior, and
    analytics brief output shape.
  - **Task I — Manager AI Chat V1:** Add chat planner flow, query-spec
    generation, policy preflight, service execution, result explanation, and
    audit.
  - **Task J — Exports And Saved Reports:** Add CSV/XLSX export, saved
    questions, scheduled reports, and export audit after result contracts are
    stable.
- **Risks:**
  - Starting with services before agreeing on manager questions may produce a
    technically clean layer that misses business value.
  - If planner prompts define metrics instead of the catalog, answers will
    drift and become hard to audit.
  - Row-level billing or PHI-adjacent drilldowns can expose sensitive data if
    policy preflight is weak.
  - Data Intelligence Agent local access can become a direct DB-access
    precedent unless the approved tool boundary is explicit.
  - Read models can prematurely freeze misunderstood provider fields. Keep
    early definitions versioned and reviewable.
- **Human decisions needed:**
  1. Choose first execution slice: questions/catalog only, or questions/catalog
     plus Data Intelligence Agent local read-only tool.
  2. Confirm the first manager question list owner and review cadence.
  3. Confirm production row-level access policy for billing-sensitive and
     PHI-adjacent results.
  4. Confirm whether manager chat v1 starts aggregate-only.
  5. Confirm whether local exploratory samples may include masked PHI-like or
     billing-sensitive fields for authorized builders.
  6. Confirm export policy and whether exports are out of scope until after
     chat/dashboard v1.
- **Notes for Orchestrator:**
  - This handoff is intentionally `needs decision`, not ready for execution,
    because the human must choose the first execution slice and access policy.
  - Recommended first Linear issue title:
    "Manager Analytics Questions and Semantic Catalog V1".
  - Recommended umbrella epic title:
    "Semantic Context And Analytics Foundation".
  - Do not assign Workers until Linear issues are created or linked under the
    Orchestrator protocol.
  - Strategy boundary respected: no workers were launched and no execution
    runtime state was created by Strategy.

### PM/Analyst Dashboard V1

- **Readiness status:** accepted by orchestrator on 2026-05-26; blocked on
  Linear issue creation/linking before worker assignment.
- **Source candidate:** `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "PM/Analyst Dashboard V1"
- **Source spec:** `/Users/eduardkarionov/Downloads/unified-patient-profile-spec.docx`
- **Business goal:** Build the first useful read-only PM/Analyst dashboard for
  human project operations and manual analysis. The dashboard should provide
  filtered pipeline visibility, consult funnel health, treatment/payment
  visibility, risk lists, sync health, and fast person lookup across
  Salesforce and CareStack evidence.
- **Why now:** The current staff dashboard is a basic summary, while project
  managers and analysts need a working surface now. Existing ingestion already
  provides enough canonical data for the first screen, and treatment/payment
  visibility is required for the team's operational view even if it needs a
  careful data-classification and canonical-domain step.
- **Expected outcome:**
  1. A dashboard v1 API contract exists for PM/Analyst filters, search, KPIs,
     funnel, breakdowns, risk rows, treatment/payment widgets, sync health, and
     drilldowns.
  2. A staff UI screen or tabbed dashboard implements the first view with global
     filters and search.
  3. The first slice uses existing canonical data where possible:
     `identity.person`, `identity.source_link`, `ops.lead`,
     `ops.consultation`, `interaction.event`, and `integrations.sync_run`.
  4. Person detail uses the operational timeline endpoint so users can see the
     normalized cross-system activity behind a person.
  5. Salesforce enrichment is added for the fields the dashboard needs:
     business unit, assigned center, preferred language, UTM fields, owner, and
     consultation scheduled date.
  6. CareStack treatment/payment work is not dropped. The Orchestrator must
     classify the data and implement the smallest read-only safe slice needed
     for treatment totals, accepted amounts, production/collection/payment
     totals, first/last payment dates, and AR-like risk flags.
  7. No provider write-back is implemented.
- **Assumptions the Orchestrator must validate:**
  - The uploaded DOCX is a requirements input, not a literal schema to copy.
  - Current repo architecture remains canonical: person spine is
    `identity.person.id`; provider payloads stay in `ingest.raw_event`; safe
    operational projections go through services.
  - Treatment/payment data is required for PM/Analyst work but is
    PHI-adjacent or billing-sensitive until classified.
  - Staff search by name/phone/email is acceptable only through authenticated
    staff APIs and should not become agent context or raw-payload exposure.
  - Existing CareStack docs under `docs/integrations/carestack/` should be
    checked before defining treatment/payment DTOs.
- **Architecture constraints:**
  - Follow root `CLAUDE.md` and `AGENTS.md`.
  - Do not create old-style `patients` / `patient_*` provider-shaped tables
    from the uploaded document.
  - No business logic in routes; dashboard metrics and filters must be produced
    by services/read models.
  - No raw provider payloads in dashboard responses.
  - `ops` remains PHI-free. If treatment/payment data requires a new canonical
    domain or `phi` service access, make that explicit before implementation.
  - CareStack and Salesforce remain read-only in this mission.
  - No deployment/env/secret/OAuth/Cloud Run/GitHub Actions changes unless
    explicitly re-scoped after reading `docs/DEPLOYMENT_RULES.md`.
- **Suggested decomposition:**
  - **Task A — Contract and filters:** Define query parameters and DTOs for
    date range, business unit, location/center, lead source/UTM, owner,
    normalized stage, consultation status, treatment/payment status, source
    provider, and text search.
  - **Task B — Existing-data dashboard API:** Build the first service/API read
    model from `ops.lead`, `ops.consultation`, `interaction.event`,
    `identity.source_link`, and `integrations.sync_run`.
  - **Task C — Drilldowns:** Add a drilldown response for metric clicks so PMs
    and analysts can see the rows behind counts.
  - **Task D — Staff UI:** Implement the dashboard view with global filters,
    search, KPI row, funnel, breakdowns, risk list, sync health, recent
    activity, and treatment/payment sections.
  - **Task E — Person timeline:** Wire person detail to
    `GET /persons/{uid}/operational-timeline`.
  - **Task F — Salesforce enrichment:** Extend Lead pull/projection for
    `Business_Unit__c`, `Assigned_Center__c`, `Preferred_Language__c`, UTM
    fields, `OwnerId`, owner display name, and `Consultation_Scheduled__c`.
  - **Task G — CareStack treatment/payment classification:** Verify available
    endpoints and payload shapes for treatment plans, treatment procedures,
    invoices, payment summary, and ledger-like data; decide canonical domain
    and dashboard-safe aggregate DTOs.
  - **Task H — CareStack treatment/payment slice:** Implement the minimum
    read-only ingestion/projection required for treatment/payment dashboard
    metrics. Keep raw details out of dashboard responses.
  - **Task I — Tests and docs:** Add backend filter/query tests, frontend
    schema/hook/render tests, no-raw-payload/no-PHI leakage checks, and update
    `docs/data-model/CATALOG.md` if schema changes land.
- **Risks:**
  - Treatment/payment scope can expand quickly. Keep the first slice focused on
    dashboard-safe aggregates and PM/Analyst questions.
  - Browser-only filtering will create metric drift. Keep business logic in
    backend services.
  - CareStack treatment/payment payloads may contain clinical or billing
    details that need stricter access than ordinary ops data.
  - The uploaded spec references older JS files and `shared/schema.ts`; workers
    must translate the intent into the current Python/FastAPI architecture.
- **Human decisions needed:**
  1. One dashboard route with PM/Analyst tabs versus separate PM and Analyst
     routes.
  2. Risk thresholds: stale lead, no next action, consult completed with no
     next step, and AR risk.
  3. Whether saved views are v1 or later. Default: later.
  4. Which staff roles may see treatment/payment aggregates and whether row
     details need an additional permission.
- **Notes for Orchestrator:**
  - Suggested Linear title: "PM/Analyst Dashboard V1 with filters, search,
    drilldowns, and treatment/payment visibility".
  - Mission spec folder:
    `.agents/orchestration/pm-analyst-dashboard-v1/`.
  - Runtime folder:
    `~/.fusion-agent-orchestrator/<repo-hash>/pm-analyst-dashboard-v1/`.
  - Current state: `Missing Linear`. No Worker may be assigned until a Linear
    issue is linked or the human explicitly approves a no-Linear exception.
  - Recommended first execution split: contract/API, staff UI, person timeline,
    Salesforce enrichment, CareStack treatment/payment classification, then
    CareStack treatment/payment implementation.
  - This handoff is intentionally separate from the broader agent context and
    workflow missions. It is a human operations dashboard first.
  - Strategy boundary respected: no workers were launched and no execution
    state was created by Strategy.

### Workflow Ready Ingest Foundation

- **Readiness status:** ready for orchestrator
- **Source candidate:** `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "Person Data And Event Provenance Foundation"
- **Source specs:**
  - `.agents/strategy/PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`
  - `.agents/strategy/RAW_TO_CONTEXT_NORMALIZATION_SPEC.md`
- **Business goal:** Convert the Salesforce and CareStack data we already pull
  into workflow-ready person-linked events and reviewable context inputs, so
  future workflow runners and agents can subscribe to normalized facts instead
  of reverse-engineering raw provider payloads.
- **Why now:** Scheduled Salesforce and CareStack ingestion already exists and
  is writing `ingest.raw_event`, identity/source-link rows, and some `ops`
  projections. The next product step needs Salesforce Tasks, call references,
  consultation lifecycle, and CareStack operational milestones to land in a
  consistent person timeline. If we do not add this layer now, the next sync
  objects will deepen raw/provider-shaped data drift.
- **Expected outcome:**
  1. Existing Salesforce Lead/Event and CareStack Patient/Appointment pullers
     remain idempotent and continue writing raw evidence first.
  2. Existing pullers emit normalized `interaction.event` rows for their
     workflow-relevant changes.
  3. The event taxonomy covers lead, consultation, task, and call-reference
     milestones needed by the first operational timeline.
  4. Scheduled and manual provider pulls write real `integrations.sync_run`
     rows with counts, status, object scope, and errors.
  5. Salesforce Task pull exists and classifies each task as action-oriented,
     historical activity, or call-related.
  6. Call references from Salesforce Tasks/Events are captured as person-linked
     evidence with source references, without downloading or transcribing audio
     in this mission.
  7. A person operational timeline read surface exists for UI/tools to fetch
     normalized events and safe summaries by `person_uid`.
  8. Tests prove no raw provider payload or clinical/free-text field leaks into
     ordinary timeline/context outputs.
- **Assumptions the Orchestrator must validate:**
  - Current scheduled ingestion entrypoints are
    `apps/worker/jobs/salesforce_pull.py`,
    `apps/worker/jobs/carestack_pull.py`, and
    `apps/worker/jobs/ingest_scheduled.py`.
  - Current pullers write raw and projections but do not reliably write
    `interaction.event` yet.
  - `context`, `workflow`, `encounter`, and `billing` packages are not part of
    this mission.
  - The first pass can store call references and task metadata without
    transcription. Call analysis is a later PHI-capable agent lane mission.
  - Existing PHI posture remains: development may classify/highlight sensitive
    data for authorized builders, while production enforcement must live in
    services/tools.
- **Architecture constraints:**
  - Root invariants apply: no DB access from agents, routes/jobs call services,
    services own logic, repositories stay data-only.
  - Raw provider payloads stay in `ingest.raw_event`; ordinary timeline and
    agent-facing outputs expose source references and safe summaries only.
  - `ops` stays marketing/operations-safe. Clinical notes, treatment details,
    insurance details, and raw patient-linked ledger payloads do not enter
    `ops`.
  - `PhiService` remains the only path for PHI domain writes/reads.
  - `interaction.event` remains append-only; re-pulls must be idempotent or
    no-op unless a watched provider field changed.
  - Repository files stay in English; user-facing discussion may be Russian.
  - No deployment/env/secret changes in this mission unless the Orchestrator
    explicitly re-scopes after reading `docs/DEPLOYMENT_RULES.md`.
- **Suggested decomposition:**
  - **Task A — Interaction event schema contract.**
    - Review current `packages/interaction/models.py`,
      `schemas.py`, and migration constraints.
    - Add only the minimum fields needed for workflow-ready events if current
      columns are insufficient: recommended candidates are `data_class`,
      `source_kind`, `source_external_id`, `projection_ref_type`,
      `projection_ref_id`, and `review_status`.
    - Expand event taxonomy for this mission only:
      `lead_created`, `lead_updated`, `consultation_scheduled`,
      `consultation_rescheduled`, `consultation_cancelled`,
      `consultation_completed`, `consultation_no_show`, `task_created`,
      `task_completed`, `call_logged`, `call_reference_found`.
    - Update migrations, DTOs, summary builder, and no-PII tests.
  - **Task B — Emit events from Salesforce Lead pull.**
    - Update `SfLeadIngestService.pull_recent` so `OpsService.upsert_lead`
      results produce `interaction.event`.
    - `was_created=True` emits `lead_created`; `was_changed=True` on an
      existing lead emits `lead_updated`; unchanged re-pulls emit nothing.
    - Event payload is allowlisted: lead status/source, external id, source
      timestamps, source references. No raw Lead payload.
  - **Task C — Emit events from Salesforce Event and CareStack Appointment.**
    - Update `SfEventIngestService` and
      `CareStackAppointmentIngestService` to emit consultation events after
      `OpsService.upsert_consultation_from_hint`.
    - Map statuses to scheduled/rescheduled/cancelled/completed/no-show.
    - Preserve source references to `raw_event_id` and `ops.consultation`.
    - Re-pulls that do not change watched fields emit no new event.
  - **Task D — Provider sync-run journaling.**
    - Wire `IntegrationService.open_sync_run` / `close_sync_run` into
      scheduled and manual Salesforce/CareStack pulls.
    - Record provider, object scope, direction, status, records_total,
      records_succeeded, records_failed, time window, and error summary.
    - Replace fake manual `sync_run_id` strings with real IDs.
    - Add audit summary rows where the existing `AuditService` contract expects
      them.
  - **Task E — Salesforce Task ingest.**
    - Add a bounded Salesforce Task SOQL pull service.
    - Capture every Task row into `ingest.raw_event` first.
    - Resolve `WhoId` and/or `WhatId` to `person_uid` via `identity.source_link`
      when possible; unresolved tasks remain reviewable and counted, not
      silently lost.
    - Classify Task:
      action-oriented task -> `ops.followup_task`;
      completed/historical activity -> `interaction.event`;
      call-like task -> `interaction.event` plus call reference extraction.
    - Keep Task free-text out of ordinary timeline payloads until reviewed.
  - **Task F — Call reference extraction, no transcription yet.**
    - Extract call/recording/transcript references from Salesforce Task/Event
      fields using allowlisted keys and provider metadata.
    - Store person-linked call evidence as `interaction.event` with
      `kind=call_reference_found` or `call_logged`.
    - Store only reference metadata: URL/ref, provider id, direction/duration
      when available, source object id, `raw_event_id`, data class, review
      status.
    - Do not download audio, generate transcripts, or call LLMs in this
      mission.
  - **Task G — Person operational timeline read surface.**
    - Add a service-level read model for a person timeline that merges
      normalized `interaction.event` rows with stable `ops` projections where
      needed.
    - Add API route and/or tool contract for
      `GET /persons/{uid}/operational-timeline` or the existing agreed route.
    - Output must include source references, data class badges, safe summaries,
      event kind, occurred_at, and review status.
    - Output must exclude raw provider payloads and unreviewed clinical/free
      text.
  - **Task H — Tests and fixtures.**
    - Unit tests for event taxonomy, summary builder, status mapping, and call
      reference extraction.
    - Integration tests for SF Lead, SF Event, SF Task, CareStack Patient, and
      CareStack Appointment pull paths.
    - Idempotency tests: repeated pulls do not duplicate projections or events.
    - Redaction tests: raw payload fields, SF Event `Description`, CareStack
      notes, Task free text, and call URLs classified as sensitive do not leak
      into ordinary timeline/context output.
    - Sync-run tests: success, partial, skipped credential, and provider error.
  - **Task I — Documentation and catalog sync.**
    - Update `docs/data-model/CATALOG.md` for any new table/column/kind.
    - Update package-local `CLAUDE.md` / `AGENTS.md` if new subareas land.
    - Reference `.agents/strategy/RAW_TO_CONTEXT_NORMALIZATION_SPEC.md` in the
      implementation plan or mission docs so future workers understand the
      layer model.
- **Out of scope:**
  - Full `workflow` package, workflow runner, timers, approval queue, and
    `workflow.agent_decision`.
  - Full `context` package and persistent `context.context_fact`.
  - Full `billing` domain.
  - CareStack treatment procedure, invoice, accounting transaction, and payment
    summary ingestion implementation. This mission prepares the timeline model;
    those feeds become a follow-up mission.
  - Audio download, transcription, call summarization, and LLM analysis.
  - Production deployment, env var, secret, Cloud Run, OAuth URL, or GitHub
    Actions deploy changes.
- **Acceptance criteria for verification:**
  1. Running the existing Salesforce pull with fixture data creates raw events,
     identity/source links, `ops.lead`, and the expected lead timeline events.
  2. Running Salesforce Event and CareStack Appointment pulls creates or updates
     `ops.consultation` and emits the correct consultation timeline events.
  3. Running Salesforce Task pull captures raw tasks and produces either
     `ops.followup_task`, historical `interaction.event`, or call-reference
     events according to deterministic classification.
  4. Re-running the same fixtures does not duplicate stable projections or
     timeline events.
  5. Every timeline output row has `person_uid`, event kind, occurred_at,
     source reference, data class, and safe summary.
  6. Timeline/API/tool outputs contain no raw provider payloads, clinical notes,
     SF Event `Description`, CareStack appointment notes, or unreviewed Task
     free text.
  7. Manual and scheduled provider pulls write real `integrations.sync_run`
     rows and close them with correct status/counts.
  8. `make lint`, `mypy .`, `make test`, and
     `cd packages/db && alembic check` are run, or any skipped check is
     documented with a blocker.
- **Risks:**
  - Event taxonomy may grow too broad in the first mission. Mitigation: limit
    implementation taxonomy to lead, consultation, task, and call-reference
    milestones; leave treatment/revenue labels documented but unimplemented.
  - Task free text may contain PHI or clinical context. Mitigation: raw-only
    capture plus safe summaries and review status; no ordinary timeline leak.
  - Call URLs may themselves be sensitive. Mitigation: classify them, restrict
    ordinary output, and do not fetch/download in this mission.
  - Sync-run journaling may require resolving active credential/account IDs
    across old and new credential storage surfaces. Mitigation: Orchestrator
    should validate the current credential source before assigning work.
  - Existing dashboard counts currently read some consultation counts from
    `phi.consultation` while provider appointments write `ops.consultation`.
    Mitigation: timeline work should not silently change dashboard semantics;
    open a separate UI/dashboard follow-up if needed.
- **Human decisions needed before or during orchestration:**
  1. Confirm the route name for the timeline read surface:
     `GET /persons/{uid}/operational-timeline` versus extending the planned
     `GET /persons/{uid}/timeline`.
  2. Confirm whether call URLs are shown to authorized builders in the first UI
     workbench, or stored only as source references until a PHI-capable call
     analysis lane is approved.
  3. Confirm whether Salesforce Task action-oriented rows should create
     `ops.followup_task` immediately, or first land as review-only events.
  4. Confirm whether event taxonomy uses existing snake_case values or adopts a
     dotted external API vocabulary while DB literals remain snake_case.
- **Notes for Orchestrator:**
  - Suggested Linear title: "Workflow-ready ingest foundation: timeline,
    sync-run journaling, Salesforce Tasks, and call references".
  - Orchestrator accepted this handoff on 2026-05-23 and created parent
    Linear issue ENG-235 with child issues ENG-236 through ENG-244.
  - Mission spec folder:
    `.agents/orchestration/workflow-ready-ingest-foundation/`.
  - This can be one parent ENG issue with child issues for Tasks A-I.
  - Recommended sequencing: A first, then B/C/D in parallel if ownership is
    disjoint, then E/F, then G/H/I.
  - Worker ownership should be split by package boundary:
    `packages/interaction` + migration; Salesforce ingest; CareStack ingest;
    sync-run journaling; API/tools timeline read; tests/docs.
  - Verifier must run the full repo verification loop because this touches
    migrations, services, worker jobs, and API/tool surfaces.
  - Strategy boundary respected: this handoff is a proposal; no workers were
    launched and no execution state was created.

### Orchestrator Launcher Reliability And Test Harness

- **Readiness status:** accepted by orchestrator on 2026-05-20T17:28:19Z
- **Linear:** ENG-213 — https://linear.app/fusion-dental-implants/issue/ENG-213/orchestrator-launcher-reliability-and-test-harness
- **Mission folder:** `.agents/orchestration/orchestrator-launcher-reliability/`
- **Handoff record:** `runtime.json` handoff `handoff-3193efd1`
- **Source candidate:** `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "Orchestrator Launcher Reliability And Test Harness"
- **Business goal:** Restore trust in the agent orchestration runtime so the
  human partner can run parallel Codex and Claude Code workers without silent
  failures. The current launcher dies on `--mode background` for both runtimes,
  writes 0-byte logs, and is not covered by tests; this blocks the entire
  parallel-wave model the orchestrator role exists to enable.
- **Why now:** Active incident recorded on 2026-05-20 in
  `.agents/orchestration/current/incidents.md` (entries for ENG-190 at
  04:33:18Z, 04:34:44Z, 04:35:25Z). Root cause is identified but unshipped.
  Until the launcher is fixed and covered by tests, every orchestrator run is
  one regression away from another silent failure.
- **Expected outcome:**
  1. `launch_worker.py --mode background` worker survives launcher exit for
     both `--runtime codex` and `--runtime claude-code`.
  2. Background log file is non-empty after a real launch.
  3. Launcher emits only flags accepted by the currently installed `codex
     exec` CLI; `--ask-for-approval` is removed; opt-in
     `--codex-bypass-approvals` is added.
  4. `pytest` suite at `.agents/skills/agent-orchestrator/tests/` covers unit,
     integration, SIGHUP-resilience, contract, schema, and wave-wrapper
     scenarios listed in the candidate mission decomposition (Tasks B–G).
  5. `incidents.md` carries a resolution entry pointing to the fix commit.
  6. `SKILL.md` and `.claude/commands/orchestrator.md` show only current,
     accepted flags.
  7. A single `make` target (or documented `pytest` invocation) runs the
     entire orchestrator test suite locally and in CI.
- **Assumptions the Orchestrator must validate:**
  - `codex` and `claude` are installed locally; CI uses a PATH shim for
    hermetic tests and gates real-binary contract tests behind an env var.
  - The current `.agents/orchestration/current/` mission is the prior
    integration-foundation wave (all ENG-204…212 merged); it should not be
    reused for this mission.
  - Repository files stay in English; conversation with the human partner may
    be in Russian.
  - No PHI, secrets, or `.env*` content enters fixtures, logs, or reports.
- **Architecture constraints:**
  - Dashboard remains read-only; tests must not invoke the dashboard server.
  - Mission folder layout stays as documented in
    `.agents/orchestration/CLAUDE.md`.
  - Launcher CLI surface changes are limited to the two minimal deltas
    (drop `--codex-approval`, add `--codex-bypass-approvals`). Broader CLI
    redesign requires a separate candidate mission.
  - Tests live under `.agents/skills/agent-orchestrator/tests/`; product
    `tests/` tree stays reserved for product code.
  - Linear gate enforced: no Worker assignment without `linear_issue_id` and
    `linear_issue_url` for every sub-task.
- **Suggested decomposition (ordered):**
  - **A — Launcher fix (blocker):** add `start_new_session=True` and
    `stdin=subprocess.DEVNULL` to background `subprocess.Popen`; remove
    `--ask-for-approval`; add `--codex-bypass-approvals`; verify `--cd` is
    still valid in current `codex exec` (drop if not, rely on Popen `cwd`).
  - **B — Unit tests** for `build_command`, `build_worker_prompt`,
    `update_runtime`, `refresh_tables`, Linear gate (depends on A).
  - **C — Integration test for background-launch survival** using PATH-shim
    fake binaries (depends on A).
  - **D — SIGHUP-resilience test:** parent shell exits before child writes;
    child must continue (depends on A, C).
  - **E — Contract drift tests** against real `codex --help` and `claude
    --help`, env-gated.
  - **F — `runtime.json` schema validator test** matching the documented
    contract.
  - **G — `run_wave.py` and `status_wave.py` smoke tests.**
  - **H — Documentation pass:** update `SKILL.md`,
    `.claude/commands/orchestrator.md`, add `tests/README.md` for the suite,
    add resolution entry to `incidents.md`.
- **Acceptance criteria for verification:**
  1. `python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py
     --runtime codex --mode background --task-id TEST-1 --linear-id TEST-1
     --linear-url https://example/TEST-1 --linear-title smoke
     --prompt "echo ok"` exits 0, leaves a worker PID alive long enough to
     write the log, and the log contains the worker output.
  2. The same invocation with `--runtime claude-code` produces non-empty log.
  3. `pytest .agents/skills/agent-orchestrator/tests/` is green.
  4. `grep -R "ask-for-approval" .agents .claude` returns nothing.
  5. New incident entry in `.agents/orchestration/<mission>/incidents.md`
     records the resolution and links to the fix commit / PR.
- **Risks:**
  - `start_new_session=True` creates orphans on launcher crash. Mitigation:
    `status_wave.py` must surface them and `incidents.md` must capture stuck
    PIDs.
  - Real-binary contract tests may flake if Codex / Claude Code ship
    silent breaking changes. Mitigation: env-gated tests with explicit
    `Contract drift:` marker on failure.
  - PATH-shim leakage between tests. Mitigation: per-test `monkeypatch.setenv`
    isolation.
  - Re-using `.agents/orchestration/current/` for this mission would pollute
    the archive of the prior wave. Mitigation: create a new mission folder
    (see Human decisions, item 1).
  - Reflex use of `--codex-bypass-approvals`. Mitigation: default off; docstring
    warning; orchestrator prompts reviewed during integration.
- **Human decisions needed before execution:**
  1. **Mission folder.** Recommendation: create
     `.agents/orchestration/orchestrator-launcher-reliability/`; archive the
     current `.agents/orchestration/current/` to
     `.agents/orchestration/archived/2026-05-19-integration-foundation/`
     before the Orchestrator opens the new mission.
  2. **Tests location.** Recommendation: `.agents/skills/agent-orchestrator/
     tests/` (skill-local). Confirm or override to `tests/orchestration/`.
  3. **Contract tests gate.** Recommendation: env-gated
     (`CODEX_CONTRACT_TESTS=1`, `CLAUDE_CONTRACT_TESTS=1`); skip when env
     missing.
  4. **`--codex-bypass-approvals` default.** Recommendation: off; explicit
     opt-in per worker invocation.
  5. **Linear scoping.** Recommendation: one ENG-issue with Task A as a
     hard blocker for B–H; tasks B–H may run sequentially on the same branch
     because they touch the same files.
- **Notes for Orchestrator:**
  - Linear gate: create one parent ENG-issue ("Orchestrator launcher
    reliability and test harness") and optionally child issues for Tasks A–H,
    or use checklist items inside the parent issue.
  - Ownership: a single Worker can carry A→H sequentially; do not parallelize
    A with B–H because B depends on the post-A flag surface.
  - Verifier role: required. Verifier must run the new pytest suite, run a
    real `--mode background` launch end-to-end, confirm the worker PID
    survives launcher exit by at least 2 seconds, and confirm the log file is
    non-empty.
  - Integrator role: confirm `grep -R "ask-for-approval"` is clean across
    `.agents/` and `.claude/`, confirm `incidents.md` has a resolution entry,
    confirm docs updated.
  - Dashboard visibility: the Orchestrator must record handoff events for
    `strategy → orchestrator` (this acceptance), `orchestrator → worker`
    (Task A start), `worker → verifier`, and `verifier → integrator`.
  - Strategy boundary respected: this handoff is a proposal; no code or
    runtime mutation has occurred at the Strategy layer.

### Process Supervision And Granular Activity States

- **Readiness status:** accepted by orchestrator on 2026-05-22T05:20:00Z
- **Linear:** ENG-226 — https://linear.app/fusion-dental-implants/issue/ENG-226/process-supervision-granular-activity-states-m-3
- **Mission folder:** `.agents/orchestration/process-supervision/`
- **Handoff record:** `runtime.json` handoff `handoff-eng226-001`
- Final mission of the 3-mission orchestrator-runtime cleanup arc.

### Worktree-As-Default For Workers Plus Self-Execute Guardrail

- **Readiness status:** accepted by orchestrator on 2026-05-22T04:26:00Z
- **Linear:** ENG-225 — https://linear.app/fusion-dental-implants/issue/ENG-225/worktree-as-default-for-workers-self-execute-guardrail-m-2
- **Mission folder:** `.agents/orchestration/worktree-as-default/`
- **Handoff record:** `runtime.json` handoff `handoff-eng225-001`
- M-3 (process supervision) remains blocked-by this mission landing.

### Move Session Runtime State Out Of The Repository

- **Readiness status:** accepted by orchestrator on 2026-05-22T02:56:00Z
- **Linear:** ENG-224 — https://linear.app/fusion-dental-implants/issue/ENG-224/move-orchestrator-session-runtime-state-out-of-the-repository-m-1
- **Mission folder:** `.agents/orchestration/runtime-state-out-of-repo/`
- **Handoff record:** `runtime.json` handoff `handoff-eng224-001`
- **Original status (preserved below):** ready for orchestrator
- **Source candidate:** `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "Move Session Runtime State Out Of The Repository"
- **Business goal:** Stop polluting git history with mission session
  ephemera. Repository keeps decision artifacts (goal, acceptance, contract,
  ownership, decision-log, lessons, incidents, reports); session state
  (`runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`, `prompts/`,
  `logs/`, `worktrees/`) moves to `~/.fusion-agent-orchestrator/<repo-hash>/
  <mission-id>/`.
- **Why now:** PR #78 just committed 30+ mission session files. Growing
  quadratically with mission count × worker count. Retrofit before PR-3
  and PR-4 produce more session noise. Also unblocks worktree-as-default
  (M-2) and process supervision (M-3) — both depend on a clean local
  runtime path.
- **Expected outcome (acceptance):**
  1. `launch_worker.py` writes `runtime.json`, `runlog.md`, `board.md`,
     `linear-sync.md`, `prompts/<task-id>-<sid>.md`, `logs/<task-id>-<sid>.log`
     to `~/.fusion-agent-orchestrator/<repo-hash>/<mission-id>/`.
     Decision artifacts (`goal.md`, `acceptance.md`, `verification.md`,
     `contract.md`, `ownership.yaml`, `decision-log.md`, `lessons.md`,
     `incidents.md`, `reports/`) stay in repo at
     `.agents/orchestration/<mission>/`.
  2. `run_wave.py` and `status_wave.py` read/write the new layout.
  3. Dashboard (`.agents/dashboard/server.py`) merges repo decision
     artifacts with local runtime state in its snapshot endpoint.
  4. `paths.py` helper centralises the path resolution.
  5. Test suite uses the new layout; `mission_dir` fixture splits into
     `mission_spec_dir` (repo) + `runtime_dir` (tmp under local root).
  6. Current mission (`orchestrator-launcher-reliability/`) is migrated:
     runtime files git-rm'd, decision artifacts preserved. Archive
     (`archived/2026-05-19-...`) left untouched as historical snapshot.
  7. `FUSION_AGENT_RUNTIME_HOME` env var overrides the default root.
  8. `.gitignore` includes `~/.fusion-agent-orchestrator/` no-op (already
     outside repo) but adds `.agents/orchestration/*/runtime.json`,
     `runlog.md`, `board.md`, `linear-sync.md`, `prompts/`, `logs/` so
     accidental local writes do not leak.
  9. Documentation updated: `.agents/CLAUDE.md`, `.agents/orchestration/
     CLAUDE.md`, `SKILL.md`, `tests/README.md` reference the new layout.
- **Decisions resolved (no human input needed):**
  - Local-path root: `~/.fusion-agent-orchestrator/`.
  - Migration scope: only current mission.
  - Env override: `FUSION_AGENT_RUNTIME_HOME`.
  - Reports stay in repo (decision artifacts).
- **Assumptions Orchestrator must validate:**
  - `git` is available on developer machine for repo-hash computation.
  - Dashboard server can read both repo and local-path filesystems.
  - No CI process currently depends on `runtime.json` paths inside the
    repo (verify via grep before merging).
- **Architecture constraints:**
  - No PHI, no secrets, no `.env*` reads.
  - Dashboard remains read-only.
  - Linear gate stays: no Worker without `linear_issue_id` + URL.
  - Tests use `tmp_path` for both `mission_spec_dir` and `runtime_dir`.
  - The migration of the current mission must not lose worker reports
    (they stay in repo per the resolved decision).
- **Suggested decomposition (sequential):**
  - **Task A:** `paths.py` helper with `runtime_root()`,
    `mission_runtime_dir(mission_id)`, `mission_spec_dir(mission_id)`,
    `worktree_dir(mission_id, task_id)` functions.
  - **Task B:** Migrate `launch_worker.py` to write runtime files to the
    new location; keep prompt and report path generation backward-aware
    so reports still land in repo's mission folder.
  - **Task C:** Migrate `run_wave.py` and `status_wave.py` to new paths.
  - **Task D:** Update `.agents/dashboard/server.py` snapshot endpoint
    to merge repo decision artifacts with local runtime state.
  - **Task E:** Update test suite: `conftest.py` `mission_dir` fixture
    splits, all integration tests use both dirs.
  - **Task F:** Migrate current mission folder: copy runtime files to
    new local path under a fresh `<repo-hash>/orchestrator-launcher-
    reliability/`, then `git rm` from repo; preserve decision artifacts
    and `reports/`.
  - **Task G:** `.gitignore` update + documentation pass.
- **Risks:**
  - Dashboard URL path resolution if `<repo-hash>` differs between
    contexts. Mitigation: `--runtime-root <path>` CLI override and clear
    env var precedence (env > flag > default).
  - Symlinked checkouts produce different hashes. Mitigation: hash
    `Path(repo_root).resolve()` not the raw string.
  - Migration losing worker reports. Mitigation: reports stay in repo
    by decision, not moved; Task F only moves runtime telemetry.
  - Test fixtures break if `paths.py` returns absolute paths into a
    real `$HOME`. Mitigation: tests `monkeypatch.setenv(
    "FUSION_AGENT_RUNTIME_HOME", str(tmp_path))`.
- **Notes for Orchestrator:**
  - This is M-1 of a 3-mission orchestrator-runtime cleanup arc.
    M-2 (worktree-as-default) and M-3 (process supervision + granular
    states) are documented in `CANDIDATE_MISSIONS.md` with decisions
    already resolved; promote them after M-1 lands.
  - Linear gate: create a new ENG-issue when scoping; suggested title
    "Move orchestrator session runtime state out of the repository".
  - Verifier sweep should confirm: (a) repo has no `runtime.json` or
    `runlog.md` files outside `archived/`; (b) dashboard snapshot still
    returns valid JSON for both empty and populated states; (c) all
    existing pytest tests still pass; (d) migration of the current
    mission preserved the verifier acceptance and worker reports
    written for ENG-213.
  - Integrator should NOT merge until the full launcher test suite is
    re-run end-to-end against the new layout.

### Read-Only Unified Person Lifecycle Foundation V1

- **Readiness status:** needs decision
- **Source candidate:** `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "Read-Only Unified Person Lifecycle Foundation V1"
- **Source strategy plan:**
  `.agents/strategy/UNIFIED_PERSON_LIFECYCLE_SEMANTIC_ANALYTICS_PLAN.md`
- **Business goal:** Convert the manager-provided unified patient / lead
  profile requirements into a Fusion CRM-native read-only lifecycle and
  profile foundation. The mission should align human workflow needs with the
  existing semantic analytics, provenance, context, and agent boundaries
  without creating a literal provider-shaped `patients` database as product
  truth.
- **Why now:** The current platform already captures the core Salesforce and
  CareStack evidence needed for a read-only lifecycle layer: leads, source and
  UTM fields, appointments, treatment procedures, invoices, accounting
  transactions, payment summaries, source links, operational timeline events,
  and aggregate analytics. The next value is to define stable semantics,
  coverage, read-model contracts, and chat/agent boundaries over this evidence.
- **Expected outcome:**
  1. The Orchestrator validates the planning scope and creates or links Linear
     issues before any Worker receives execution work.
  2. A documented requirements-alignment brief maps each manager-spec section
     to Fusion CRM architecture and marks literal schema proposals as adopted,
     adapted, rejected, or deferred.
  3. A coverage audit reports which existing Salesforce and CareStack feeds
     support each requested lifecycle/profile/analytics concept, including
     skipped rows, unlinked rows, raw-only evidence, and implemented aggregates.
  4. A source-of-truth precedence contract defines read-only Salesforce and
     CareStack field ownership.
  5. A lifecycle stage taxonomy is ready for semantic catalog review.
  6. Candidate semantic terms and read-model contracts are proposed for
     lifecycle stage, stage history, source linkage quality, revenue by source,
     outstanding balance, sync/reconcile health, and future write-back state.
  7. Manager Chat V2 boundaries are documented as registry-driven and
     policy-preflight-driven, with person context tools separated from
     aggregate analytics chat.
  8. Write-back remains deferred and is documented as a later governance
     mission with prerequisites.
- **Assumptions the Orchestrator must validate:**
  - `identity.person.id` remains the single canonical `person_uid`.
  - Current provider feeds are sufficient for a read-only coverage-audit and
    contract-definition mission.
  - Salesforce Contact and LeadHistory gaps should be treated as discovery or
    follow-up tasks, not blockers to planning.
  - CareStack treatment, production, collection, balance, and surgery semantics
    require reviewed mapping before row-level outputs or manager chat answers.
  - Manager Chat V1 remains aggregate-only while this mission plans V2.
  - Data Intelligence Agent outputs remain review-only.
- **Architecture constraints:**
  - Follow root `CLAUDE.md` and `AGENTS.md`.
  - Follow `.agents/CLAUDE.md` and `.agents/AGENTS.md` for handoff and runtime
    visibility if the mission is accepted.
  - Strategy proposes; Orchestrator disposes.
  - Do not launch Workers until Linear issues exist and the human approves
    execution scope.
  - Do not implement a literal manager-spec `patients` schema as product
    truth.
  - Keep provider payloads in `ingest.raw_event`; production surfaces consume
    service-owned projections, timeline events, context packs, and read
    models.
  - `ops` remains PHI-free; PHI access goes through `PhiService` with audit.
  - Agents and chat do not access the database directly.
  - No raw SQL from agents, dashboards, chat, workbench, or LLM planners.
  - No provider write-back, external side effects, deployment changes, secrets,
    OAuth/CORS, Cloud Run, deploy scripts, or GitHub Actions changes in this
    mission.
- **Suggested decomposition:**
  - **UPL-01 — Mission Setup And Linear Sync:** Accept or reject the handoff,
    create mission runtime state, Linear mapping, board, decision log, and
    visible `Handoff:` event.
  - **UPL-02 — Requirements Alignment Brief:** Map manager spec sections to
    Fusion CRM architecture and mark adopted/adapted/rejected/deferred items.
  - **UPL-03 — Evidence Coverage Audit:** Inspect existing feeds, services,
    timeline events, analytics tools, and sync/backfill posture. Report
    coverage and gaps without changing product code.
  - **UPL-04 — Source-Of-Truth Precedence Contract:** Define Salesforce versus
    CareStack ownership for read-only fields and conflict handling.
  - **UPL-05 — Lifecycle Stage Taxonomy:** Define stage values, transition
    inputs, source evidence, ambiguities, and catalog-review needs.
  - **UPL-06 — Semantic Catalog Extension Candidates:** Prepare proposal-ready
    term definitions for lifecycle, linkage, source, revenue, balance, sync,
    and write-back state terms.
  - **UPL-07 — Read Model V2 Contracts:** Draft contracts for lifecycle
    summary, lifecycle funnel, stage history, revenue by source, outstanding
    balance, identity linkage quality, and sync/reconcile health.
  - **UPL-08 — Manager Chat V2 Scope:** Define aggregate-first chat expansion,
    bounded row-level prerequisites, clarification behavior, and person
    context/tool separation.
  - **UPL-09 — Write-Back Deferral Brief:** Document prerequisites and risk
    controls before any write router or agent write surface is scoped.
- **Risks:**
  - Literal schema adoption would duplicate domain meaning and violate the
    canonical `person_uid` architecture.
  - Coverage assumptions can create false confidence in lifecycle and revenue
    analytics.
  - Row-level billing outputs can leak sensitive data without allowlists,
    caps, roles, and audit.
  - Chat V2 can become raw data browsing unless it remains query-registry and
    policy-preflight driven.
  - Early write-back could create external side effects before source
    precedence, approval, retry, and audit contracts are stable.
- **Human decisions needed:**
  1. Attribution model: catalog default, first touch, last touch, or reviewed
     alternative.
  2. `paid_lead` semantics for V2: any payment, deposit, paid in full, or
     separate variants.
  3. Billing-sensitive row-level worklist audience and field allowlist owner.
  4. Manager Chat V2 posture: aggregate-only first or bounded row-level for
     authorized users.
  5. Galleria OMS/CareStack coverage posture.
  6. Manual merge ownership: admin-only, TC-facing, or operator queue.
  7. Confirmation that write-back remains deferred until read-only contracts
     stabilize.
- **Notes for Orchestrator:**
  - Recommended parent Linear umbrella:
    "Semantic Context And Analytics Foundation".
  - Recommended child mission/project title:
    "Read-Only Unified Person Lifecycle Foundation V1".
  - Recommended mission folder:
    `.agents/orchestration/read-only-unified-person-lifecycle-foundation-v1/`.
  - This is a planning and contract mission first. If implementation tasks are
    discovered, split them into follow-up missions after the coverage audit
    and human decisions are complete.
  - Record the Strategy to Orchestrator `Handoff:` event before execution.
  - Do not launch Workers until the human approves the accepted Linear scope.
