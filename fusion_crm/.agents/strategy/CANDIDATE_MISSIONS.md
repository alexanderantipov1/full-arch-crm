# Candidate Missions

This file records Strategy and Architecture candidate missions before the
Orchestrator accepts them for execution.

Strategy and Architecture agents may add and refine entries here. They must not
launch workers, assign execution tasks directly, or modify product code.

Handoff rule:

```text
Strategy proposes, Orchestrator disposes.
```

## Template

### <candidate mission title>

- **Readiness status:** draft / needs decision / ready for orchestrator
- **Business goal:** <what business outcome this mission supports>
- **Why now:** <why this should be considered now>
- **Expected outcome:** <what should be true after execution>
- **Assumptions:** <known assumptions>
- **Architecture constraints:** <hard constraints and relevant doctrine>
- **Suggested decomposition:** <suggested mission/workstream split>
- **Risks:** <business, technical, operational, and compliance risks>
- **Human decisions needed:** <decisions required before execution>
- **Orchestrator handoff:** <link or reference when added to HANDOFF_TO_ORCHESTRATOR.md>

## Active Candidate Missions

### Revenue Intelligence Analytics Platform V1

- **Readiness status:** ready for orchestrator; Linear project "Revenue
  Intelligence Analytics Platform V1" + epic ENG-504 + children ENG-505..ENG-529
  created under team Engineering (operator explicitly directed Linear creation).
  Mission folder: `.agents/orchestration/revenue-intelligence-analytics-v1/`.
- **Source spec:** `market.md`. Strategy plan:
  `.agents/strategy/REVENUE_INTELLIGENCE_ANALYTICS_PLATFORM_PLAN.md`.
- **Business goal:** Build a unified Revenue Intelligence Platform that traces
  every patient from advertising spend to collected revenue and functions as an
  executive operating system — 14 analytics pages + a `fact_patient_journey` fact
  table + derived metrics + global filters (incl. per-location) + CSV/Excel
  export, on top of the existing analytics surface.
- **Why now:** Five analytics pages already exist and the marketing-first funnel
  is the current priority; the operator provided the full `market.md` spec.
  Multi-location data, money metrics (ENG-283), attribution schema (ENG-446), and
  person-anchored funnel dating (ENG-481) already exist, so the foundation can be
  assembled now.
- **Expected outcome:** new `analytics` schema + `fact_patient_journey`
  (person-anchored, rebuildable, nullable+provenance), a shared filter/metric
  contract, the 14 spec pages, missing-field enablement (caller/coordinator/
  doctor/treatment-accepted/surgery/marketing-cost via auto-resolver OR manual
  enrichment), and export/drill-down.
- **Assumptions:** read-only staff surface; dev-phase full-visibility; person
  spine `identity.person.id`; analytics logic in `packages/analytics` composed in
  `apps/api`; agents never touch DB; logs PHI-free; raw payloads stay in
  `ingest.raw_event`.
- **Architecture constraints:** new `analytics` schema is an operator-approved
  invariant #1 addition (rebuildable projection, never a source of truth);
  migrations immutable; no business logic in routes.
- **Suggested decomposition:** B0 foundation (ENG-505..508) → B1 missing-field
  enablement (ENG-509..513) alongside → B2 14 pages (ENG-514..527) → B3 closeout
  (ENG-528..529).
- **Risks:** treatment-accepted/surgery classification gap (ENG-511) is
  discovery-gated; operational cost basis (ENG-522) needs operator input;
  attribution maturity caps vendor/campaign richness; new schema must not become
  a second source of truth; new pages must reconcile with existing dashboards on
  real data.
- **Human decisions needed:** CareStack acceptance/surgery semantics; operational
  cost basis; provenance precedence confirmation; Marketing page extend-vs-new.
- **Orchestrator handoff:** `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` →
  "Revenue Intelligence Analytics Platform V1".

### Interactive Corporate Messenger Layer (Mattermost) V1

- **Readiness status:** accepted by orchestrator on 2026-06-15; dedicated Linear
  project "Interactive Corporate Messenger Layer (Mattermost) V1" created under
  team ENG with epic ENG-433 and children ENG-434 (A) through ENG-442 (I).
  Mission folder: `.agents/orchestration/interactive-messenger-layer-v1/`.
- **Source strategy spec:**
  `.agents/strategy/INTERACTIVE_MESSENGER_LAYER_DOCTRINE.md`
- **Business goal:** Stand up an interactive corporate messenger layer that is
  both (1) an internal team channel (replacing scattered WhatsApp/SMS used to
  discuss patients/operations) and (2) a bidirectional interface for automation
  and AI agents (human-in-the-loop: the system pushes events; humans push
  commands, approvals, and manual enrichment back). Provider is self-hosted
  Mattermost, treated as an external provider behind a thin `ChatProvider`
  adapter.
- **Why now:** The team already negotiates about patients over uncontrolled
  WhatsApp/SMS, which the mission ("operate as if HIPAA were enforced today")
  is meant to eliminate. Full-fidelity ingestion now holds every source field,
  so field-condition notification rules are feasible. Self-hosting Mattermost
  keeps data in our perimeter/GCP, making the layer PHI-future-proof without a
  vendor BAA, while a marketing-first, de-identified default lets it ship in the
  current phase.
- **Expected outcome:**
  1. A provider-agnostic messenger core: `ChatProvider` interface with a
     `MattermostAdapter`; per-tenant credentials in
     `tenant.integration_credential` (`provider_kind="mattermost"`).
  2. Outbound: domain events write `integrations.notification_outbox` in-txn;
     a worker drains and posts; rules in `integrations.notification_rule`
     (event + field-condition predicates + channel + template + enabled) with
     seeds for `lead.created`, `opportunity.stage_changed`, `ownership.changed`,
     `ingest.sync_failed`.
  3. Inbound: signed public endpoint(s) (Interactivity + outgoing-webhook/Events,
     mandatory signature/URL verification) capture verbatim to
     `ingest.raw_event` (`source="mattermost"`) and map to curated domain writes.
  4. Manual enrichment via a `record_annotation` store, writable from chat and
     the staff frontend through one path.
  5. Agent human-in-the-loop approve/reject through services/tools only.
  6. Governance: ADR-0006, audit actions `notification.mattermost.send`/`.response`,
     `actor_identifier` (`mattermost_user_id`).
  7. Local infrastructure under compose profile `chat`; production infrastructure
     deferred to a separate, DEPLOYMENT_RULES-gated block.
- **Assumptions:**
  - Marketing-first: only contact data not linked to medical records at the
    start; notifications de-identified (`person_uid` + deep link) by default with
    a reserved `phi_mode` flag.
  - Mattermost is not patient-facing; it does not replace WhatsApp/SMS for
    talking *with* patients.
  - Self-hosted Mattermost Team Edition, official image, not forked, pinned
    version, English DB locale.
  - Mattermost runs its own database, physically separate from the canonical
    8-schema DB (invariant #1 preserved).
  - Local and prod environments stay separate (no shared server).
- **Architecture constraints:**
  - Follow root `CLAUDE.md`, `AGENTS.md`, `.agents/CLAUDE.md`, `.agents/AGENTS.md`.
  - Invariants #5 (no business logic in routes; use outbox+worker), #6 (no DB
    access from agents; services/tools only), #10 (tenant creds in
    `tenant.integration_credential`, not Cloud Run env).
  - Inbound must verify request signature/token and URL challenge.
  - Production infra only after ADR-0006 and per `docs/DEPLOYMENT_RULES.md`,
    split from feature work; Mattermost is stateful (not scale-to-zero Cloud Run).
  - Provider-agnostic core; Mattermost specifics isolated to the adapter.
- **Suggested decomposition:** Blocks A–I in the doctrine — A local infra,
  B adapter+outbound, C outbox+rules schema+dispatch, D rules engine+event
  wiring, E signed inbound+mapping, F `record_annotation` enrichment, G agent
  human-in-the-loop, H governance/ADR/audit, I production infra (later).
- **Risks:**
  - Compliance: de-identified default must be enforced in templates; a leaked
    name/phone in a message would put PII into chat.
  - Operational: self-hosting adds a stateful service (backup/upgrade/monitor);
    low at clinic scale but non-zero for a solo dev.
  - Security: a public inbound endpoint without correct signature verification is
    an injection surface.
  - Contract: new schema (`notification_rule`, `notification_outbox`), new
    provider kind, new `raw_event` source, new audit actions, and a public route
    are shared contracts.
- **Human decisions needed:** `record_annotation` domain placement; Mattermost
  version pin + upgrade cadence; prod host shape and `chat.*` hostname/TLS; prod
  Mattermost DB placement; canonical `event_type` taxonomy; retention/footprint.
- **Orchestrator handoff:** `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` →
  "Interactive Corporate Messenger Layer (Mattermost) V1".

### Data Intelligence Agent Local Tooling V1

- **Readiness status:** accepted by orchestrator on 2026-05-30; Linear
  structure created under `Semantic Context And Analytics Foundation` as
  ENG-286 with child issues ENG-287 through ENG-299.
- **Source strategy spec:**
  `.agents/strategy/DATA_INTELLIGENCE_AGENT_LOCAL_TOOLING_MISSION_SPEC.md`
- **Business goal:** Operationalize the internal Data Intelligence Agent as a
  safe local read-only discovery and profiling lane for real Fusion CRM data,
  so semantic catalog, read-model, and analytics service work can be grounded
  in observed Salesforce, CareStack, identity, ops, interaction, and billing
  evidence without direct database access by agents.
- **Why now:** The Semantic Context And Analytics Foundation has manager
  questions, catalog terms, query specs, policy preflight, query registry,
  service-owned analytics, read models, frontend docs, and manager dashboard
  integration. The next bottleneck is understanding real local data coverage
  and gaps without relying on ad hoc SQL or raw provider payload inspection.
- **Expected outcome:**
  1. Orchestrator continues under the existing Linear umbrella
     `Semantic Context And Analytics Foundation` and creates a child
     mission/project or issue tree for this work.
  2. Approved local tools can discover datasets, list query registry entries,
     profile fields, compute null rates/top values, inspect linkage rates,
     inspect evidence coverage, and return bounded masked samples.
  3. The tooling can produce semantic mapping proposals and gap briefs for
     future catalog, data quality, service, and read-model tasks.
  4. Every tool call is logged or audited with actor/session, dataset, fields,
     filters, data classes, row limits, masks, result posture, and status.
  5. Local workbench visibility is added or extended if Orchestrator includes
     that issue in scope.
- **Assumptions:**
  - The ENG-279 Data Intelligence Agent contract remains the role baseline.
  - Human-confirmed current direction allows row-level local samples for
    authorized internal users when accessed through approved tools with caps,
    masking, and audit/logging.
  - PHI remains denied in V1.
  - Raw provider payloads remain denied as ordinary output.
  - Export expansion, XLSX, scheduled reports, and broad production role
    matrices remain later work.
- **Architecture constraints:**
  - Follow root `CLAUDE.md`, `AGENTS.md`, `.agents/CLAUDE.md`, and
    `.agents/AGENTS.md`.
  - Agents do not access the database directly.
  - No raw SQL from agents, LLM planners, dashboard code, or chat.
  - Tools call services only; tools do not call repositories or
    `session.execute(...)`.
  - PHI access goes through `PhiService` with audit; PHI is denied for this V1
    mission unless separately approved.
  - Raw provider payloads are not ordinary dashboard, chat, report, or agent
    output.
  - `.agents/` must not become a product runtime dependency.
- **Suggested decomposition:**
  - **DIA-01:** Mission Setup And Linear Sync.
  - **DIA-02:** Tool Policy And Allowlist.
  - **DIA-03:** Data Intelligence Service Contract.
  - **DIA-04:** Query Registry And Dataset Discovery Tool.
  - **DIA-05:** Field Profile Tool.
  - **DIA-06:** Linkage And Source Coverage Tool.
  - **DIA-07:** Evidence Coverage Tool.
  - **DIA-08:** Bounded Masked Sample Tool.
  - **DIA-09:** Semantic Mapping Proposal Generator.
  - **DIA-10:** Gap Brief Writer.
  - **DIA-11:** Audit And Tool Call Logging.
  - **DIA-12:** Local Workbench Visibility.
  - **DIA-13:** Verification And Production Review.
- **Risks:**
  - The tool can become a generic data browser unless deny-by-default
    allowlists, caps, masks, and no-SQL constraints are enforced.
  - Local samples can leak sensitive details into logs or reports unless output
    DTOs and logging policy are explicit.
  - Tool outputs can drift from the semantic catalog unless proposals remain
    review-only and reference catalog term ids/versions.
  - Row-level local access can accidentally shape manager chat/dashboard policy.
    Keep this mission internal-builder only.
- **Human decisions needed:**
  1. Confirm default row sample limit `25` and hard cap `100`.
  2. Confirm default top-value cap `50` and hard cap `250`.
  3. Confirm whether local workbench visibility should be a child route or an
     extension of `/dev/semantic-analytics`.
  4. Confirm that PHI and exports remain denied for this mission.
- **Orchestrator handoff:** Added to
  `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` as
  "Data Intelligence Agent Local Tooling V1".

### Semantic Context And Analytics Foundation

- **Readiness status:** needs decision
- **Source strategy plan:**
  `.agents/strategy/SEMANTIC_CONTEXT_ANALYTICS_FOUNDATION_PLAN.md`
- **Business goal:** Create one reusable semantic and analytics foundation for
  manager dashboards, manager AI chat, internal Data Intelligence agents,
  future reports, and workflow-ready context. The foundation should prevent
  metric drift by defining business terms, query specs, policy checks, read
  models, and service-owned analytics once, then reusing them across surfaces.
- **Why now:** Fusion CRM already ingests Salesforce and CareStack evidence,
  and the team is beginning to build PM/Analyst dashboards, operational
  timelines, agent context, and manager-facing analytics. Without a shared
  semantic layer, dashboards, chat, agents, and reports will each interpret
  terms such as `paid_lead`, `facebook_source`, `treatment_accepted`,
  `payment_received`, and `no_next_action` differently.
- **Expected outcome:**
  1. The first 20 to 30 manager analytics questions are documented.
  2. A Semantic Analytics Catalog defines business terms, synonyms, exact
     meanings, data sources, data classes, permission rules, row-level versus
     aggregate behavior, allowed fields, versions, and review status.
  3. A structured analytics query spec lets LLM planners and UI surfaces express
     requests without raw SQL.
  4. Policy preflight checks role, PHI, billing, row-level access, export, and
     audit requirements before execution.
  5. Allowlisted analytics services and query registry provide typed backend
     execution for dashboard, chat, and agent clients.
  6. Initial read models cover lead conversion, paid leads, consultation
     follow-up, and treatment revenue.
  7. A Data Intelligence Agent can profile real local data through approved
     read-only tools and prepare new mappings or handoffs.
  8. Manager AI chat can use the same query registry and semantic catalog to
     answer approved production questions with explainability.
- **Assumptions:**
  - Raw provider evidence remains evidence-first and is not product truth until
    named, classified, reviewed, and promoted.
  - `context.context_fact` and analytics terms are related but separate:
    context facts record person-linked meaning, while analytics terms define
    cohorts and metrics over facts and projections.
  - The first implementation can compute some read models through services over
    current canonical tables; materialized views can come later.
  - Internal local data exploration may be allowed for authorized builders, but
    only through approved read-only tools with masking, allowlists, row limits,
    and logging.
  - Production manager chat starts from approved query specs and policy
    preflight, not free-form SQL.
- **Architecture constraints:**
  - Follow root `CLAUDE.md` and `AGENTS.md`.
  - Agents do not access the database directly.
  - Routes and jobs call services; services call repositories.
  - PHI access goes through `PhiService` with audit.
  - `identity.person.id` remains the canonical `person_uid`.
  - `ops` remains PHI-free.
  - Raw provider payloads stay in evidence storage and are not ordinary
    production dashboard, chat, or agent outputs.
  - Billing-sensitive and PHI-adjacent data must be classified before
    surfacing.
  - No business logic in browser-only dashboard filtering.
- **Suggested decomposition:**
  - **Mission 1:** Manager Analytics Questions V1.
  - **Mission 2:** Semantic Analytics Catalog V1.
  - **Mission 3:** Structured Analytics Query Spec.
  - **Mission 4:** Analytics Policy Preflight.
  - **Mission 5:** Analytics Services And Query Registry V1.
  - **Mission 6:** Manager Analytics Read Models V1.
  - **Mission 7:** Data Intelligence Agent V1.
  - **Mission 8:** Manager AI Chat V1.
  - **Mission 9:** Exports And Saved Reports.
- **Risks:**
  - Overbuilding a generic analytics engine before real questions are captured.
    Mitigation: start with 20 to 30 manager questions.
  - Letting the LLM infer metric definitions. Mitigation: catalog-driven terms
    and structured query specs only.
  - Accidentally exposing PHI, billing, or raw provider payloads through
    dashboards or chat. Mitigation: policy preflight, result contracts, audit,
    and service-level redaction.
  - Duplicating business meaning between context facts, dashboard services, and
    chat prompts. Mitigation: define facts and analytics terms separately and
    version both.
  - Treating local exploratory data access as permission for production raw
    data access. Mitigation: local-only exploratory mode and stricter
    production policies.
- **Human decisions needed:**
  1. Confirm whether the first execution slice should be manager questions plus
     semantic catalog only, or whether the Data Intelligence Agent local tool
     should be built in parallel.
  2. Confirm the first 20 to 30 manager questions and their priority order.
  3. Confirm production row-level access rules for billing-sensitive and
     PHI-adjacent results.
  4. Confirm whether manager AI chat v1 starts aggregate-only.
  5. Confirm export policy for billing and PHI-adjacent cohorts.
- **Orchestrator handoff:** Added to
  `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` as
  "Semantic Context And Analytics Foundation".

### PM/Analyst Dashboard V1

- **Readiness status:** accepted by orchestrator on 2026-05-26; blocked on
  Linear issue creation/linking before worker assignment.
- **Business goal:** Give project managers and analysts a practical human
  operations dashboard for daily manual work: filtered pipeline visibility,
  consult funnel health, treatment/payment visibility, risk lists, sync health,
  and fast person lookup across the Salesforce and CareStack data Fusion CRM
  ingests.
- **Why now:** The staff UI already has a basic dashboard and person card, and
  the ingest layer already captures Salesforce Leads, Events, Tasks, CareStack
  Patients, Appointments, source links, interaction events, and sync-run
  telemetry. The team now needs a useful working screen before the deeper
  agent/workflow surface is built. This is intentionally a human-ops dashboard
  mission, not a rewrite of the canonical data model.
- **Expected outcome:**
  1. PM/Analyst dashboard v1 ships as a read-only staff surface with a global
     filter bar, search, KPI row, funnel, breakdowns, risk list, sync health,
     treatment/payment visibility, and drilldowns.
  2. Filters include date range, business unit, center/location, lead source or
     UTM source, owner/TC owner when available, normalized stage, consultation
     status, treatment/payment status where available, and source provider.
  3. Search supports name, phone, email, Salesforce id, and CareStack patient
     id through authenticated staff APIs only.
  4. The first dashboard uses existing canonical data first:
     `ops.lead`, `ops.consultation`, `interaction.event`,
     `identity.source_link`, and `integrations.sync_run`.
  5. Person detail uses the existing operational timeline endpoint instead of
     rendering an empty timeline.
  6. Salesforce Lead enrichment follows for business unit, center, owner, UTM
     fields, and consultation scheduled date.
  7. CareStack treatment and payment data is included as a required read-only
     dashboard track. The Orchestrator must classify the data, confirm the
     correct canonical domain and service boundary, then implement the smallest
     safe slice that answers PM/Analyst questions without leaking raw payloads
     or clinical free text.
  8. Provider write-back remains out of scope for this mission.
- **Assumptions:**
  - Conversation and product planning may happen in Russian; repository files
    stay in English.
  - PM/Analyst dashboard v1 is a staff-only human workflow tool. It is not the
    final agent context architecture and should not block future agent-specific
    context packs.
  - Existing canonical architecture remains authoritative. The uploaded
    `unified-patient-profile-spec.docx` is a requirements source, not a schema
    prescription.
  - Treatment/payment data is business-critical for PMs and analysts, but it is
    PHI-adjacent or billing-sensitive by default until classified.
  - PII search is allowed only on authenticated staff surfaces. Raw provider
    payloads and PHI-bearing content must not be exposed through ordinary
    dashboard outputs.
- **Architecture constraints:**
  - Do not implement the old `patients` / `patient_*` schema from the uploaded
    document literally.
  - Keep using `identity.person.id` as the canonical `person_uid`.
  - Provider payloads stay in `ingest.raw_event`; dashboard reads canonical
    service outputs, not raw payloads.
  - `ops` remains PHI-free. If treatment or payment fields are classified as
    PHI or billing-sensitive, they need an approved canonical domain and
    service boundary before surfacing.
  - CareStack treatment/payment ingestion must be read-only and audited through
    the service layer; no dashboard code may call CareStack hot-path APIs
    directly.
  - No provider write-back in this mission.
  - No deployment, secrets, OAuth URL, Cloud Run, or GitHub Actions changes
    unless explicitly re-scoped after reading `docs/DEPLOYMENT_RULES.md`.
- **Suggested decomposition:**
  - **Task A:** Define dashboard v1 contract: filters, search params, response
    shape, KPI cards, funnel buckets, breakdown dimensions, risk-list rows,
    treatment/payment widgets, and drilldown row shape.
  - **Task B:** Add service/API read model for dashboard v1 using existing
    canonical tables first. Suggested route shape:
    `GET /dashboard/pm` and/or `GET /dashboard/analytics` with shared filter
    parameters.
  - **Task C:** Add drilldown endpoint or route contract so clicking a metric
    returns the filtered person/lead/consultation/treatment/payment rows behind
    that number.
  - **Task D:** Build the staff UI dashboard v1 with global filters, search,
    KPI row, funnel, breakdowns, risk list, recent activity, sync health, and
    treatment/payment sections.
  - **Task E:** Wire person detail to
    `GET /persons/{uid}/operational-timeline` so the profile view shows the
    safe normalized timeline already produced by ingestion.
  - **Task F:** Salesforce enrichment: extend Lead pull and ops-safe
    projections for `Business_Unit__c`, `Assigned_Center__c`,
    `Preferred_Language__c`, UTM fields, `OwnerId`, owner display name, and
    `Consultation_Scheduled__c`.
  - **Task G:** CareStack treatment/payment discovery and classification:
    confirm endpoint availability for treatment plans, treatment procedures,
    invoices, payment summary, and ledger-like data; decide canonical domain
    placement; define read-only DTOs and dashboard-safe aggregates.
  - **Task H:** CareStack treatment/payment implementation slice: ingest or
    cache the minimum required fields for treatment totals, accepted amounts,
    production/collection/payment totals, first/last payment dates, and AR-like
    risk flags, using canonical services and no raw-payload dashboard exposure.
  - **Task I:** Tests: backend filter/query tests, frontend schema/hook tests,
    dashboard rendering tests, and no-raw-payload/no-PHI leakage checks.
- **Risks:**
  - If v1 tries to model every treatment/payment detail, it can turn into a
    full billing/PHI platform mission. Mitigation: implement dashboard-safe
    aggregates first and keep raw/procedure detail behind explicit service
    boundaries.
  - If filtering is calculated only in the browser, the dashboard will drift
    from authoritative business logic and become slow as data grows.
  - If Salesforce enrichment is bundled into the first UI slice, delivery may
    slip. Mitigation: build v1 on existing data, then add enrichment as a
    narrow follow-up slice.
  - Name/phone/email search is useful but sensitive. Mitigation: authenticated
    staff API only, no raw payload exposure, no agent context exposure.
  - CareStack treatment/payment semantics may differ from the uploaded spec.
    Mitigation: verify against the local CareStack docs and live payload shape
    before creating schema or analytics contracts.
- **Human decisions needed:**
  1. Confirm whether PM and Analyst are tabs on one `/dashboard` route or two
     routes (`/dashboard/pm`, `/dashboard/analytics`).
  2. Confirm the first risk-list definitions: stale lead threshold, no next
     action definition, consult-completed-with-no-next-step threshold, and AR
     risk threshold.
  3. Confirm whether saved views are out of scope for v1. Default: out of
     scope.
  4. Confirm who may see treatment/payment aggregates in the staff UI and
     whether any row-level details require an additional permission.
- **Orchestrator handoff:** Added to
  `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` as
  "PM/Analyst Dashboard V1". Accepted mission folder:
  `.agents/orchestration/pm-analyst-dashboard-v1/`.

### Person Data And Event Provenance Foundation

- **Readiness status:** partially promoted — first execution slice ready for
  orchestrator as "Workflow Ready Ingest Foundation"; broader treatment,
  billing, persistent context, and workflow-engine work remains needs decision.
- **Business goal:** Prevent Salesforce and CareStack ingestion from becoming
  an unstructured provider-data swamp before agents begin consuming person
  timelines and context. Every person-linked provider signal should become
  traceable evidence, a canonical identity/source-link decision, a safe domain
  projection, a normalized event, and eventually an agent-safe context pack.
- **Why now:** Raw provider data is already entering the platform, and the next
  stage is pulling events and objects connected to the same people. If the
  taxonomy and context boundaries are not fixed before that expansion, future
  agents will either over-read raw payloads or receive inconsistent,
  provider-shaped context.
- **Expected outcome:**
  1. `PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md` is reviewed and accepted as the
     source doctrine for person-linked provider observations.
  2. `RAW_TO_CONTEXT_NORMALIZATION_SPEC.md` is reviewed and accepted as the
     technical layer model for raw capture, minimal indexing, human review,
     canonical projection, semantic interpretation, and agent context packs.
  3. Salesforce Lead/Event and CareStack Patient/Appointment/Treatment/Billing
     milestones are mapped from `ingest.raw_event` through identity resolution,
     `source_link`, domain projection, normalized timeline event, and
     context-pack output.
  4. The first event taxonomy and data-class allowlists are documented.
  5. A minimal person timeline contract is defined for UI and MCP/tool use.
  6. The first agent context-pack contracts are defined without exposing raw
     provider payloads.
  7. Verification includes tests or review checks that raw payloads and PHI do
     not leak into agent-facing timeline/context outputs.
- **Assumptions:**
  - `identity.person.id` remains the canonical `person_uid` across all domains.
  - Raw provider payloads continue to land first in `ingest.raw_event`.
  - Provider-specific domain tables are forbidden; provider objects are
    projected into canonical domains or `integrations.external_entity`.
  - CareStack patient, treatment, insurance, and patient-linked billing data is
    PHI-sensitive or PHI-adjacent by default.
  - The platform may support PHI-capable agents because the approved AI vendor
    route and cloud/database infrastructure can be BAA-covered; those agents
    still require minimum-necessary context packs, permission checks, audit, and
    output classification.
  - Salesforce custom fields and notes are not automatically safe merely
    because they come from CRM.
  - Agents receive service-built context packs, not direct database or raw-event
    access.
- **Architecture constraints:**
  - Respect root `CLAUDE.md` invariants: services own business logic,
    repositories are data-only, agents never touch the DB directly, and PHI
    access goes through `PhiService` with audit.
  - `ops` and `phi` separation stays strict. Marketing-safe projections may
    live in `ops`; clinical facts stay in `phi` or gated context.
  - `ingest.raw_event` is append-only evidence and is not a production agent
    interface.
  - `interaction.event` and future `context.context_fact` must carry source
    references, data class, PHI flags, and version/review semantics where they
    affect workflow or agents.
  - During development, PHI-sensitive and PHI-adjacent facts may be visible to
    authenticated internal builders with explicit data-class badges, but this is
    classification-only posture. Before real production access expands, service
    and tool layers must enforce permissions server-side and audit PHI reads.
  - Development needs an authorized human review/workbench lane where approved
    builders can inspect PHI evidence, classify meaning, and define
    ops-safe/marketing-safe projections before agents depend on them.
  - Production agent access must distinguish PHI-free agent lanes from
    PHI-capable agent lanes. PHI-capable lanes require BAA-covered AI routes,
    BAA-covered storage/runtime, permission checks, minimum-necessary context,
    audit, and classified outputs.
  - Repository files are written in English.
- **Suggested decomposition:**
  - **Block A — Doctrine and inventory:** review
    `PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md` and
    `RAW_TO_CONTEXT_NORMALIZATION_SPEC.md`; inventory Salesforce and CareStack
    objects currently ingested or planned next, including CareStack
    appointments, treatment procedures, invoices, accounting transactions,
    payment summaries, and payment types; map each to raw evidence, minimal
    index fields, human review fields, identity/source link, domain projection,
    event type, and context output.
  - **Block B — Taxonomy baseline:** define controlled values for
    `source_system`, `source_instance`, `source_kind`,
    `interaction.event_type`, `context_type`, `context_key`, data class, and
    identity match rule categories.
  - **Block C — Person timeline contract:** specify service/API/MCP behavior
    for `GET /persons/{uid}/timeline` and `get_person_timeline`, including
    ordering, source references, PHI redaction, and raw-payload exclusion.
  - **Block D — Context-pack contracts:** define
    `speed_to_lead_context`, `person_timeline_context`, and
    `consultation_context`, then decide whether `treatment_status_context` and
    `revenue_status_context` are in this mission or the next one. Each context
    pack needs allowed fields, denied fields, source references, confidence,
    review status, and audit expectations.
  - **Block E — PHI-capable agent lane contract:** define which context packs
    may include PHI, which BAA-covered AI routes can receive them, what audit
    rows are required, and how outputs are classified before downstream use.
  - **Block F — Human review/workbench contract:** define the authorized
    development surface for inspecting PHI/PHI-adjacent evidence, creating
    semantic labels, approving ops-safe/marketing-safe projections, and keeping
    source references for every derived fact.
  - **Block G — Implementation readiness:** once A-F are accepted, the
    Orchestrator can split schema/API/service/tool/test work into Linear-backed
    execution tasks.
- **Risks:**
  - If the timeline is treated as a raw-provider dump, agents will inherit
    Salesforce/CareStack field chaos and PHI leakage risk.
  - If taxonomy is too loose, agents and workflows will drift into incompatible
    labels.
  - If identity matching auto-accept rules are too aggressive, unrelated people
    may be merged. If they are too conservative, agents will see fragmented
    histories.
  - If CareStack allowlists are vague, clinical, treatment, insurance, or
    patient-linked billing data can leak into `ops`, timeline, or agent
    prompts.
  - If context packs are built before source references are standardized,
    agent decisions will be hard to explain or replay.
- **Human decisions needed:**
  1. Initial object scope: only Salesforce Lead/Event and CareStack
     Patient/Appointment, or include CareStack treatment procedures, invoices,
     accounting transactions, payment summaries, and payment types in the first
     design pass.
  2. Whether this first Orchestrator mission should be documentation/taxonomy
     only, or include schema/API/service implementation.
  3. CareStack allowlist for `ops.consultation`, timeline, billing/revenue
     projections, and agent context.
  4. Salesforce custom-field allowlist for `ops.lead`, timeline, and
     speed-to-lead context.
  5. Owner for identity match candidate review and taxonomy-change approval.
  6. Whether `interaction.event` ships before persistent `context`, with early
     context packs built on demand from events and domain projections.
  7. Which environments are allowed to run in classification-only mode, and what
     concrete gate flips the product to server-side PHI enforcement before
     broader production use.
  8. Which AI vendor routes are approved for PHI-capable agents, and where that
     approval is recorded so workers do not accidentally use a non-BAA route.
  9. Who is allowed into the human review/workbench lane during development,
     and which derived labels are approved for marketing-safe agent context.
- **Orchestrator handoff:** First scoped handoff created in
  `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` as
  "Workflow Ready Ingest Foundation". The broader candidate remains open for
  later treatment/billing/context/workflow missions.

### Materialize Agent Orchestration Runtime Layer

- **Readiness status:** needs decision
- **Business goal:** Turn the current read-only Mission Control dashboard from
  an empty-state cockpit into a useful development control surface for
  strategic planning, mission handoff, worker coordination, and verification
  visibility.
- **Why now:** The dashboard, strategy protocol, candidate mission file, and
  orchestrator handoff file now exist, but the execution runtime is not yet
  materialized. The current dashboard can detect missing mission folders and
  missing orchestrator source scripts, but it cannot display live mission
  progress until the runtime contract exists on disk.
- **Expected outcome:** A minimal `.agents/orchestration/<mission>/` structure
  exists with real mission files, a clear board, runtime metadata, report
  locations, decision log, runlog, and ownership contract. The dashboard can
  show real mission state, open issues, reports, changed files, verification
  status, and handoff readiness without inventing data.
- **Assumptions:** The agent development layer remains separate from Fusion CRM
  product code. Source files stay in English. The initial runtime is read-only
  from the dashboard perspective. Linear integration can remain a markdown
  fallback until the Orchestrator owns synchronization.
- **Architecture constraints:** Strategy and Architecture agents may create
  candidate missions and handoff requests, but must not launch workers, assign
  execution tasks directly, or modify product code. The Orchestrator validates
  scope, creates mission folders, syncs Linear, defines ownership, assigns
  workers, runs verification, and integrates worker output. The dashboard must
  remain localhost-only and read-only.
- **Suggested decomposition:** First define the mission folder contract and
  create one sample current mission folder. Then restore or recreate the
  minimal orchestrator source providers for ownership checks, launch command
  discovery, and wave/run metadata. Then update the dashboard snapshot to read
  those providers when present. Finally, add focused smoke tests for empty
  state, populated mission state, and decision inbox extraction.
- **Risks:** If the dashboard starts writing state too early, it can become a
  second source of truth. If the runtime contract is too broad, this becomes a
  separate product instead of a development cockpit. If orchestrator providers
  are inferred from `__pycache__` traces instead of real source, behavior may
  diverge from the original design.
- **Human decisions needed:** Confirm whether the first execution mission
  should be named `current`, `mission-control-runtime`, or tied to a Linear
  issue. Confirm whether old orchestrator source scripts should be restored
  from another worktree/source or recreated from the visible protocol. Confirm
  whether dashboard localization should remain external/runtime-only for now.
- **Orchestrator handoff:** Not created yet. Promote this candidate to
  `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` only after the human decisions
  above are resolved.

### Orchestrator Launcher Reliability And Test Harness

- **Readiness status:** ready for orchestrator
- **Business goal:** Make the agent orchestration runtime trustworthy so the
  human partner can launch parallel Codex and Claude Code workers without
  silent failures. Today background launches die immediately, write 0-byte
  logs, and only foreground sessions succeed. This blocks any parallel wave
  larger than the one human seat, which is the whole point of the orchestrator.
- **Why now:** Active incident on 2026-05-20 (mission `current/incidents.md`)
  shows the failure is reproducible on both `codex` and `claude-code` runtimes
  and is not caught by any test. Root cause was located but no fix has shipped,
  and the codex CLI flag deprecation will keep biting until the launcher is
  updated. Without this, the Orchestrator role itself is unreliable.
- **Expected outcome:**
  1. `python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py
     --runtime codex --mode background ...` produces a worker process that
     survives launcher exit, writes a non-empty log, and updates `runtime.json`.
  2. Same is true for `--runtime claude-code`.
  3. The launcher uses only flags accepted by the currently installed
     `codex exec` CLI; deprecated `--ask-for-approval` is removed; an explicit
     opt-in `--codex-bypass-approvals` flag exists when full bypass is needed.
  4. A `pytest` suite under `.agents/skills/agent-orchestrator/tests/` covers
     unit, integration, contract, and end-to-end behavior with at least the
     scenarios listed in the suggested decomposition below.
  5. `make test` (or a documented sub-target) runs the new suite locally and in
     CI; failures block merge.
  6. `incidents.md` carries a resolution entry pointing to the fix commit.
  7. `SKILL.md` for `agent-orchestrator` and `.claude/commands/orchestrator.md`
     show only valid current flags.
- **Assumptions:**
  - Both `codex` and `claude` are available on PATH in local dev. CI may rely on
    a PATH shim (fake binary) for hermetic runs; contract tests that hit the
    real binaries are gated behind an environment variable so CI does not fail
    when the binaries are absent.
  - The dashboard remains read-only. Tests must not invoke the dashboard.
  - Mission folder shape stays as defined in `.agents/orchestration/CLAUDE.md`.
  - The launcher already has the right responsibilities; this mission fixes
    correctness and adds coverage, not new features.
- **Architecture constraints:**
  - Strategy proposes, Orchestrator disposes — execution must not start without
    a Linear issue and `linear-sync.md` mapping.
  - Repository files must stay in English.
  - No PHI, no secrets, no `.env*` reads inside tests or fixtures.
  - The fix must not change the launcher's public CLI surface beyond the two
    minimal deltas required (drop `--codex-approval`, add
    `--codex-bypass-approvals`). Anything broader requires a new candidate
    mission.
  - Tests live under `.agents/skills/agent-orchestrator/tests/` so they ship
    with the skill and travel with the orchestrator runtime. Root `tests/`
    remains reserved for product code.
- **Suggested decomposition:**
  - **Task A: Fix launcher detachment and codex flag drift.**
    - Add `start_new_session=True` and `stdin=subprocess.DEVNULL` to the
      background `subprocess.Popen` call.
    - Remove `--ask-for-approval` from the codex command builder.
    - Add `--codex-bypass-approvals` argparse flag (default `False`); when
      truthy, append `--dangerously-bypass-approvals-and-sandbox` to the codex
      command.
    - Verify `--cd` is still supported by current `codex exec`; if not, rely on
      `cwd=args.worktree` in Popen and drop `--cd` from the argument list.
    - Update `SKILL.md` and `.claude/commands/orchestrator.md` snippets.
    - Update `incidents.md` with a resolution entry referencing the fix.
  - **Task B: Build unit test suite for launcher internals.**
    - `build_command` for `runtime=codex`: returns expected flag set, omits
      deprecated flags, includes bypass flag only when opt-in is set.
    - `build_command` for `runtime=claude-code`: returns expected flag set.
    - `build_worker_prompt`: includes Linear id, URL, mission-relative paths,
      and required rules block.
    - `update_runtime`: deduplicates by `session_id`, appends handoff entry
      with required fields, truncates handoffs at the documented cap.
    - `refresh_tables`: renders `board.md` and `linear-sync.md` with stable
      column order and escaped pipes.
    - Linear gate: missing `--linear-id` or `--linear-url` raises `SystemExit`.
  - **Task C: Integration test for background-launch survival.**
    - Use a fake worker script (a 3-line shell that sleeps 2s, echoes a
      sentinel, exits 0) on a tmp PATH shim called `codex` (and a second
      called `claude`).
    - Run the launcher via `subprocess.run(["python3", LAUNCHER, ...,
      "--runtime", "codex", "--mode", "background", ...])` and assert:
      - the launcher exits 0 within 1 second;
      - the worker PID is still alive 2 seconds after launcher exit
        (`os.kill(pid, 0)` succeeds while the sentinel write window is open);
      - the log file becomes non-empty and contains the sentinel;
      - `runtime.json` records `pid`, `status=running`, `launch_mode=background`.
    - Repeat with `--runtime claude-code`.
  - **Task D: SIGHUP-resilience test.**
    - Spawn the launcher under a parent shell that itself exits immediately
      after launching; confirm the worker continues to write to the log file.
    - This is the regression guard for the current incident.
  - **Task E: Contract / drift tests against installed binaries.**
    - When `CODEX_CONTRACT_TESTS=1` is set, parse `codex exec --help` and
      assert every flag the launcher emits is present in the help output.
    - When `CLAUDE_CONTRACT_TESTS=1` is set, do the same for `claude --help`.
    - Skip cleanly otherwise; print a clear xfail/skip reason.
  - **Task F: Runtime.json schema test.**
    - Validate that after a launch, `runtime.json` matches the schema documented
      in `.agents/orchestration/CLAUDE.md`: `mission_id`, `updated_at`,
      `sessions[]` with required keys, `handoffs[]` with required keys, and an
      allowed `status` enum.
  - **Task G: Status/wave wrappers smoke test.**
    - `run_wave.py` with a 2-task JSON file should call the launcher twice
      and produce two sessions in `runtime.json`.
    - `status_wave.py` should print the two sessions, including stale-heartbeat
      detection when `last_activity` is older than threshold.
  - **Task H: Documentation pass.**
    - README pointer in `.agents/skills/agent-orchestrator/` describing how to
      run the new tests locally and in CI.
    - One paragraph in `.agents/orchestration/CLAUDE.md` linking to the test
      suite as the runtime contract enforcement layer.
- **Risks:**
  - `start_new_session=True` produces orphaned processes that are harder to
    clean up if a launcher run is interrupted. Mitigation: `status_wave.py`
    must show these workers and `incidents.md` must capture stuck PIDs.
  - Real-binary contract tests can become flaky if Codex or Claude Code ships
    breaking changes silently. Mitigation: env-gated, with a clear `Contract
    drift:` marker emitted when they fail.
  - Tests that depend on PATH shims can leak across the test process. Mitigation:
    use `monkeypatch.setenv("PATH", ...)` style isolation in `pytest`.
  - The `current` mission folder is an archive of the prior wave; running the
    test suite against it will pollute live runtime files. Mitigation: every
    integration test must use a `tmp_path`-based mission folder, never
    `.agents/orchestration/current/`.
  - The `--dangerously-bypass-approvals-and-sandbox` opt-in could be enabled
    everywhere by reflex. Mitigation: keep default off and add a docstring
    warning; review opt-in usage in any orchestrator prompt.
- **Human decisions needed:**
  1. New mission folder for this work: `current/` is stale.
     Recommendation: create
     `.agents/orchestration/orchestrator-launcher-reliability/` and archive
     today's `current/` into `archived/2026-05-19-integration-foundation/`
     before execution starts.
  2. Tests location confirmed as `.agents/skills/agent-orchestrator/tests/`
     (skill-local), not `tests/orchestration/`. Confirm or override.
  3. Contract tests against real `codex` and `claude` binaries: gate on env
     var (recommended) or hard-require in CI.
  4. Default value of `--codex-bypass-approvals`: stay off (recommended,
     safe) or default on (pragmatic, matches current de-facto state).
  5. Linear scope: one issue with sub-tasks, or one issue per Task A–H?
     Recommendation: one ENG-issue with A as the blocker for B-H; merge in
     sequence, not in parallel, because B depends on the new flag surface.
- **Orchestrator handoff:** Promoted to
  `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` under
  "Orchestrator Launcher Reliability And Test Harness".

### Move Session Runtime State Out Of The Repository

- **Readiness status:** ready for orchestrator
- **Business goal:** Stop polluting git history with mission session ephemera
  (`runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`, `prompts/`,
  `logs/`, `reports/`) so the repository remains a clean record of decision
  artifacts and code, not a transcript of every parallel worker tick. Inspired
  by ComposioHQ/agent-orchestrator's split: repo = config + mission truth;
  local FS = sessions/logs/pids/worktrees.
- **Why now:** PR #78 just landed 30+ mission session files in git history.
  Every additional mission and every parallel worker will commit more of the
  same. This grows quadratically with mission count and worker count, makes
  diffs noisy, makes `git log` useless for grep, and locks us into committing
  runtime state on every dashboard heartbeat. Cheaper to retrofit now (one
  more mission) than after five more missions land.
- **Expected outcome:**
  1. Mission **decision artifacts** stay in repo at
     `.agents/orchestration/<mission>/`: `goal.md`, `acceptance.md`,
     `verification.md`, `contract.md`, `ownership.yaml`, `decision-log.md`,
     `lessons.md`, `incidents.md`. These are the parts a future reader needs.
  2. Mission **session state** moves to
     `~/.fusion-agent-orchestrator/<repo-hash>/<mission-id>/`:
     `runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`, `prompts/`,
     `logs/`, `reports/`, `worktrees/`. These are ephemera.
  3. Launcher (`launch_worker.py`) writes runtime to the local path.
  4. Dashboard reads from the local path with a per-repo lookup.
  5. `status_wave.py` follows the local path.
  6. `.gitignore` keeps any accidental local-path leftovers out of git.
  7. The two existing missions (archived integration-foundation; current
     orchestrator-launcher-reliability) are migrated as part of the same
     mission — runtime files in repo are git-rm'd, decision artifacts stay.
- **Assumptions:**
  - Local path is `~/.fusion-agent-orchestrator/` (configurable env var
    `FUSION_AGENT_RUNTIME_HOME` if needed). Repo hash is a stable SHA of the
    canonical repo root path.
  - The dashboard remains read-only; it reads from both repo and local-path.
  - We do not migrate the prior wave's runtime files retroactively — they
    are historical, leave them in `archived/`.
- **Architecture constraints:**
  - Dashboard, launcher, status, and wave scripts must continue to function
    after the move. No silent breakage.
  - The migration must be a single coherent change so dashboard and launcher
    do not drift.
  - Worktree paths under the new layout are still git worktrees (created via
    `git worktree add`), so they stay linkable to the canonical repo.
  - No PHI, no secrets, no `.env*` content under the new local path.
- **Suggested decomposition:**
  - **Task A:** Define the local-path schema and a small `paths.py` helper in
    `.agents/skills/agent-orchestrator/scripts/` returning runtime root and
    mission paths given a mission id.
  - **Task B:** Update `launch_worker.py` to write `runtime.json`, `runlog.md`,
    `board.md`, `linear-sync.md`, `prompts/`, `logs/` to the new local path.
    Keep decision-artifact paths in repo as-is.
  - **Task C:** Update `run_wave.py` and `status_wave.py` to read/write the
    new paths.
  - **Task D:** Update `.agents/dashboard/server.py` snapshot endpoint to
    accept both a repo mission folder and a local runtime folder; merge them
    in the snapshot view.
  - **Task E:** Update the test suite to use the new path layout
    (`mission_dir` fixture splits into `mission_spec_dir` + `runtime_dir`).
  - **Task F:** Migrate the current mission folder
    (`.agents/orchestration/orchestrator-launcher-reliability/`) — git-rm
    the runtime files, keep decision artifacts. Migration script for solo
    dev (one-shot) is enough; no need for general-purpose migration tool.
  - **Task G:** Documentation pass: `.agents/CLAUDE.md`,
    `.agents/orchestration/CLAUDE.md`, README, SKILL.md, tests/README.md.
- **Risks:**
  - Dashboard URL changes if `<repo-hash>` resolution differs from user
    expectation. Mitigation: also accept `--runtime-root <path>` override.
  - Local path collision when two checkouts of the same repo exist (e.g.
    worktrees). Mitigation: hash the canonical real-path, not the symlink.
  - Migration of the current mission must not lose the verifier and worker
    reports. Mitigation: copy first, verify, then git-rm.
  - The orchestrator skill description in `.agents/orchestration/CLAUDE.md`
    references repo-relative paths heavily. Re-wording required.
- **Human decisions (resolved 2026-05-20):**
  1. Local-path root: **`~/.fusion-agent-orchestrator/`**.
  2. Migration scope: **only the current mission**; archived wave stays as
     historical snapshot.
  3. Env-var override: **`FUSION_AGENT_RUNTIME_HOME`**.
  4. Reports location: **stay in repo** as decision artifacts; only runtime
     telemetry (`runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`,
     `prompts/`, `logs/`, `worktrees/`) moves to the local path.
- **Orchestrator handoff:** Promoted to
  `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` under
  "Move Session Runtime State Out Of The Repository".

### Worktree-As-Default For Workers Plus Self-Execute Guardrail

- **Readiness status:** ready for orchestrator (blocked-by M-1 landing)
- **Business goal:** Make parallel worker waves safe by default. Each worker
  gets an isolated git worktree on its own branch so concurrent workers cannot
  trample each other's file changes. Constrain the orchestrator's ability to
  self-execute in the current checkout — protect against the easy "I'll just
  do it myself" shortcut that hides decision points and produces oversized
  commits.
- **Why now:** Today the launcher defaults `--worktree` to the current
  repository root. Two parallel workers in `--mode background` would write
  into the same checkout, with predictable file-stomping consequences. We
  haven't been bitten yet only because we have been running sequentially.
  Once we start using parallel waves seriously (which is the point of the
  whole orchestrator), this becomes a guaranteed failure mode. Better to fix
  before the failure happens than after.
- **Expected outcome:**
  1. New flag `--workspace worktree|self`; default for `--role worker` is
     `worktree`.
  2. When `--workspace worktree`, the launcher creates a git worktree under
     the new local-runtime path
     (`~/.fusion-agent-orchestrator/<repo-hash>/<mission-id>/worktrees/<task-id>/`)
     on a fresh branch derived from `--branch-base` (default `main`) with
     name `<linear-id>-<task-id>` and runs the worker there.
  3. When `--workspace self`, the worker runs in the current checkout. This
     requires `--allow-self-execute` to also be set, otherwise the launcher
     refuses with a clear error.
  4. Self-execute guardrail: even with `--allow-self-execute`, the launcher
     rejects when (a) the worker prompt is over a configurable byte size, OR
     (b) the orchestrator did not assert `--scope tiny|bugfix|docs` for the
     handoff. Forces the orchestrator to make an explicit decision about
     blast radius.
  5. Worktree cleanup helper:
     `python3 .agents/skills/agent-orchestrator/scripts/cleanup_worktrees.py`
     prunes worktrees whose linked branch is merged or whose mission is
     archived.
- **Assumptions:**
  - Local runtime path layout from the M-1 mission is in place.
  - `git worktree` is available on the developer machine (standard since
    git 2.5; we use it elsewhere).
  - Branch naming convention follows the Linear-suggested
    `eduardk/<linear-id>-<task-id>` pattern.
  - The `superpowers:using-git-worktrees` skill from the local plugin
    library captures the safety-verification pattern; the launcher should
    apply the same pre-flight (working tree clean check, etc.).
- **Architecture constraints:**
  - The launcher must not create a worktree without a Linear issue id and
    URL — Linear gate stays.
  - Self-execute mode must record the decision in `decision-log.md` with
    `Scope:` marker so the audit trail explains why the orchestrator chose
    to bypass worktree isolation.
  - Worktree paths live under the local runtime root (M-1 dependency), not
    in the repository tree, so they do not appear in `git status`.
  - The launcher must not delete a worktree it did not create; cleanup
    helper requires explicit confirmation of mission archive or merge.
- **Suggested decomposition:**
  - **Task A:** `paths.py` (from M-1) gets a `worktree_dir(mission, task)`
    function.
  - **Task B:** `launch_worker.py`: add `--workspace`,
    `--allow-self-execute`, `--scope`, `--branch-base` argparse. When
    workspace=worktree, run `git worktree add <path> -b <branch>
    <base>` before launch.
  - **Task C:** Guardrail logic: if workspace=self and not allow-self-execute
    → SystemExit. If allow-self-execute and prompt > threshold or scope
    missing → SystemExit with clear message.
  - **Task D:** `cleanup_worktrees.py` walks the local runtime path,
    matches each worktree to mission archive status and branch merge
    status, prompts before pruning.
  - **Task E:** Tests: unit (argparse rules), integration (worktree
    creation, isolation between two parallel workers writing the same
    file), guardrail rejection cases.
  - **Task F:** Documentation pass; update orchestrator prompt examples
    to show worktree mode.
- **Risks:**
  - Worktree creation against a dirty main branch fails; this is good
    (prevents tainted starts) but produces a confusing error. Mitigation:
    pre-flight check with explicit message ("main has uncommitted changes
    in apps/web/page.tsx; stash or commit first").
  - Two workers on the same branch will conflict. Mitigation: branch name
    includes session id suffix for collisions.
  - Self-execute guardrail can be circumvented if the orchestrator just
    passes `--scope tiny` for non-tiny work. This is policy, not technical;
    decision-log audit catches abuse.
  - Cleanup helper deleting active worktrees is destructive. Mitigation:
    confirmation prompt + dry-run mode default.
- **Human decisions (resolved 2026-05-20):**
  1. Prompt-size threshold for self-execute guardrail: **5,000 chars**.
  2. Valid `--scope` values: **`tiny`, `bugfix`, `docs`, `none`**; default
     must be explicit (no implicit value).
  3. Cleanup default mode: **`--dry-run`**; explicit `--apply` for
     destructive worktree pruning.
  4. Branch-base default: **always `main`**; orchestrator can override
     per-task with `--branch-base`.
- **Orchestrator handoff:** Decisions resolved. Will be promoted to
  `HANDOFF_TO_ORCHESTRATOR.md` after M-1 lands and the local runtime path
  layout is in place.

### Process Supervision And Granular Activity States

- **Readiness status:** ready for orchestrator (blocked-by M-2 landing)
- **Business goal:** Make running workers fully controllable from the
  orchestrator surface (attach to tail, kill, resume, status), and make the
  dashboard tell the truth about whether a worker is actually alive vs
  whether the `runtime.json` says so. Today the orchestrator launches and
  forgets; the dashboard echoes a `status: running` that may be stale by
  hours.
- **Why now:** With M-1 (clean runtime path) and M-2 (worktree isolation)
  in place, the orchestrator becomes a real multi-worker control plane and
  needs the supervision surface ComposioHQ already provides. Without it,
  every "is that worker still working or stuck?" question requires manual
  `ps aux` and `tail -f` invocations. Solo dev does not scale.
- **Expected outcome:**
  1. `launch_worker.py` (or a sibling `worker_ctl.py`) supports:
     - `--attach <session-id>`: tail the worker log in foreground.
     - `--kill <session-id>`: SIGTERM the worker process (with 10s grace
       then SIGKILL), update `runtime.json` status to `cancelled`, write
       a runlog entry.
     - `--status <session-id>`: print a compact status block (execution
       status, runtime status, last activity, log tail).
     - `--list`: show all active sessions for the current mission.
  2. Split status dimensions in `runtime.json` (per session):
     - `execution_status` (current `status` field): workflow state from
       the documented enum.
     - `runtime_status`: `alive` | `exited` | `missing` from `ps` check
       on `pid`.
     - `agent_activity`: `active` | `idle` | `waiting_input` | `blocked`
       inferred from log-file growth and last-write heuristic
       (configurable threshold, e.g. no log growth for 60s = `idle`).
     - `linear_status`: read from Linear (current behavior).
     - `pr_status`: optional, read from GitHub when a PR exists.
  3. `start_control_plane.py`: convenience wrapper that runs
     `status_wave.py`, starts the dashboard, prints the local URL, and
     checks that the local runtime path is mounted.
  4. Dashboard surface: each row gets the three new state columns
     alongside `execution_status`.
  5. Worker reports include the final `runtime_status` (exited cleanly
     vs killed) for forensic completeness.
- **Assumptions:**
  - M-1 and M-2 missions have landed.
  - `ps`-style PID check works on macOS and Linux (we are not running on
     anything else).
  - GitHub status is fetched via `gh pr view --json` when a PR ref exists;
     no GraphQL needed.
  - The agent-activity heuristic is best-effort, not authoritative. Workers
     can self-report when they think they are waiting for input by writing
     `Needs decision:` to `runlog.md`; the dashboard already routes this
     marker into the decision inbox.
- **Architecture constraints:**
  - The supervision surface remains read-mostly: `--kill` is the only
     write action and it must require an explicit session id (no
     `--kill-all`).
  - Dashboard stays read-only. The supervision CLI is a separate process.
  - `runtime_status` is derived state. It is not persisted in
     `runtime.json` between runs; it is computed on demand.
  - `agent_activity` is heuristic. The dashboard must label it as such so
     readers do not treat it as authoritative.
- **Suggested decomposition:**
  - **Task A:** `pid_check.py` helper: given a pid, return `alive` |
     `exited` | `missing`.
  - **Task B:** Activity heuristic: given a log file, infer
     `active|idle|waiting_input|blocked` based on age and pattern.
  - **Task C:** `worker_ctl.py` with `--attach`, `--kill`, `--status`,
     `--list` subcommands.
  - **Task D:** Update `runtime.json` schema to carry the new state
     dimensions; backfill on launcher run.
  - **Task E:** Update `status_wave.py` to surface the new dimensions.
  - **Task F:** Update dashboard snapshot endpoint to expose the new
     dimensions; UI column order discussion deferred.
  - **Task G:** `start_control_plane.py` wrapper.
  - **Task H:** Tests for each new helper; integration test for the full
     `launch → status → kill → status` cycle.
- **Risks:**
  - Activity heuristic produces false positives (long pause is not always
    blocked). Mitigation: heuristic only — paired with the worker's own
    `Needs decision:` marker; humans look at marker before heuristic.
  - `--kill` could be misused to interrupt a worker mid-write. Mitigation:
    SIGTERM first with 10s grace; worker contract should write its
    current state to `runlog.md` and exit cleanly.
  - `gh pr view` is slow if invoked per session every dashboard refresh.
    Mitigation: cache for 30s; refresh on demand only.
  - Cross-platform `ps` differences. Mitigation: use `os.kill(pid, 0)`
    pattern instead of shelling out — already used in `status_wave.py`.
- **Human decisions (resolved 2026-05-20):**
  1. `--attach` semantics: **tail-only** (simpler, no terminal hand-off).
  2. Idle-vs-active threshold: **60s** of no log growth.
  3. `--kill` grace period: **10s default**, `--grace <seconds>` override.
  4. `start_control_plane.py` browser open: **yes**, with `--no-open`
     opt-out.
- **Orchestrator handoff:** Decisions resolved. Will be promoted to
  `HANDOFF_TO_ORCHESTRATOR.md` after M-1 and M-2 land.

### Tenant Integrations: SF + CareStack Reconnect / Edit / Disconnect UI

- **Readiness status:** superseded on 2026-05-22 — scope shipped via PR #83
  (ENG-215 "bootstrap credential forms for SF + CareStack"). Validation by
  Orchestrator on 2026-05-22T17:00Z found Tasks A–G all already implemented:
  - Reconnect handler wired (`page.tsx:431,504`).
  - `CredentialEditModal`, `DisconnectConfirmModal`, `BootstrapCredentialModal`
    components exist under `apps/web/components/integrations/`.
  - `last_refreshed_at` / `expires_at` rendered with `formatRelative` +
    `formatDateTime` on hover (`page.tsx:477-488`).
  - Callback URL hint with `navigator.clipboard.writeText` synthesizing from
    `NEXT_PUBLIC_OAUTH_REDIRECT_BASE_URL` (`page.tsx:362-393`).
  - Vitest coverage exists at `apps/web/tests/unit/{CredentialEditModal,
    DisconnectConfirmModal, BootstrapCredentialModal, useCredentials}.test.*`
    (3 + 3 + 5 + 2 cases respectively).
  Strategy did not re-sync after ENG-215 landed. No Linear issue opened for
  this proposal; rejection logged in
  `.agents/orchestration/current/decision-log.md`.
- **Business goal:** Restore actionable credential management for Salesforce
  and CareStack in `/settings/tenant?tab=integrations`. Today the page lists
  providers as `Active` but every action button is a disabled placeholder
  (`title="Reconnect flow ships with ENG-128"` — stale reference to a
  long-closed schema ticket). If a token expires or an API key rotates, the
  operator has nowhere in the UI to fix it. The old standalone
  `/integrations/*` pages were removed during the settings-tab consolidation
  (PR #77) without migrating the management surface.
- **Why now:** Production incident posture: an OAuth refresh failure or a
  CareStack key rotation today would silently break ingest until someone
  edits the database row by hand. The frontend rails are already in place
  (706-line `(staff)/settings/tenant/page.tsx` renders the provider rows and
  the disabled buttons); the backend exposes `GET/POST/PUT/DELETE
  /tenant/credentials` and the OAuth-start flow already used by the recently
  merged #68 fix. The gap is just wiring — half a day of focused work.
- **Expected outcome:**
  1. **Salesforce Reconnect** — the existing button stops being a tooltip
     placeholder and starts the canonical OAuth flow (the same one used by
     the original `/integrations/salesforce` page that PR #77 removed). On
     return the operator lands back on `/settings/tenant?tab=integrations&connected=salesforce`.
  2. **CareStack Edit API key** — a modal that lets the operator paste a new
     API key (and any related metadata: subdomain, location alias) and saves
     via `PUT /tenant/credentials/{id}`. Masked input; never echoes the
     stored secret.
  3. **Disconnect** — destructive button gated behind a confirm modal that
     calls `DELETE /tenant/credentials/{id}` and re-fetches the integration
     list.
  4. **Refreshed at / Expires at** — surface `refreshed_at` and `expires_at`
     from the existing `IntegrationCredentialOut` response instead of the
     hard-coded "—". Relative time as the primary display ("2h ago",
     "in 14 days"), full ISO on hover.
  5. **Callback URL hint** — for Salesforce, show the exact
     `OAUTH_REDIRECT_BASE_URL + /api/integrations/salesforce/callback` URL
     with a copy button, plus a one-line tip explaining where to paste it
     in the provider's Connected App config.
- **Assumptions:**
  - All four backend routes (`GET/POST/PUT/DELETE /tenant/credentials`) are
    on main and tenant-scoped; verified during the audit above.
  - OAuth start flow uses the existing endpoint surface; no new API needed
    for Salesforce reconnect.
  - The `useTenantCurrent` hook + credential list already drives the page;
    new mutation hooks fit the same TanStack Query pattern as `useSync*`.
  - PHI is not stored in `integration_credential` — only operator-facing
    secrets. UI masks secrets at the input layer; no PHI surface.
- **Architecture constraints:**
  - Repository files stay in English. UI labels may stay English (matching
    the rest of the staff app) unless the user explicitly asks to localize.
  - No new backend endpoints — use the existing four routes.
  - No secret values rendered to the DOM after save (return path from the
    API must omit them, or UI must avoid binding them).
  - Modals follow whatever modal primitive the rest of the staff app uses
    (likely a shadcn or in-house Dialog component); do not introduce a new
    modal library.
  - Disconnect must require explicit confirmation (typed-provider-name or
    explicit "I understand" checkbox in the modal) — destructive operation.
  - Tests added on the web side via vitest using the existing pattern from
    other settings-page tests. No backend changes → no Python tests in
    scope unless a contract bug surfaces during integration.
  - No PHI. No secrets in logs. No commits or pushes from Worker.
- **Suggested decomposition:**
  - **Task A:** Wire Salesforce Reconnect button to the OAuth-start URL.
    Drop the stale `ENG-128` tooltip. Verify it works locally end-to-end
    with the already-fixed redirect from PR #68.
  - **Task B:** `useTenantCredentialUpdate` and `useTenantCredentialDelete`
    TanStack mutation hooks under
    `apps/web/lib/api/hooks/useTenantCredentials.ts` (or co-located).
    Invalidate the credential list query on success.
  - **Task C:** `CredentialEditModal` component — masked input(s), validation,
    submit handler that calls the update hook. Used by CareStack row's
    "Edit" action.
  - **Task D:** `DisconnectConfirmModal` component — destructive intent,
    typed confirmation, submit handler that calls the delete hook.
  - **Task E:** Surface `refreshed_at` / `expires_at` with a relative-time
    helper (re-use or extract the dashboard's `formatRelative`).
  - **Task F:** Callback URL hint block on the Salesforce row — read
    `OAUTH_REDIRECT_BASE_URL` from a server-rendered env exposure or hard-
    code the canonical staff URL pattern; add a copy-to-clipboard control.
  - **Task G:** Vitest coverage for the new hooks and the two modals (open
    / submit happy path / error path).
  - **Task H:** Smoke pass: manual end-to-end check in `127.0.0.1:3000` —
    reconnect SF (OAuth happy path), edit CS key, disconnect with confirm,
    timestamps render, callback URL copyable.
- **Risks:**
  - Modal libraries may diverge between pages; investigate first before
    building.
  - Disconnect is destructive — a UI bug could revoke a working credential.
    Mitigation: typed confirmation; backend keeps audit trail
    (already implemented via existing AuditService writes on credential
    DELETE).
  - PUT `/credentials/{id}` semantics — confirm during implementation
    whether the endpoint accepts partial updates or expects the full
    credential payload. Adjust hook accordingly.
  - "Test connection" is intentionally out of scope; if the user later
    asks for one-click validation, open a sibling issue. Not adding stub
    endpoints to avoid scope creep.
  - Localization: UI stays English. If product team wants Russian later,
    a separate i18n mission picks that up.
- **Human decisions (resolved 2026-05-21):**
  1. Modal confirmation pattern for Disconnect: **typed provider name**
     (e.g. user types "Salesforce" to confirm) — explicit, prevents misclick.
  2. Reconnect flow: **redirect** in-place (not popup) — matches existing
     Salesforce OAuth pattern, simpler.
  3. Refreshed/Expires display: **relative primary, ISO on hover** —
     matches the dashboard simplified-view convention shipped in #80.
  4. Callback URL source: **synthesize from `OAUTH_REDIRECT_BASE_URL`** on
     the client (env exposed via Next.js public config) or read from a new
     `GET /tenant/integrations/<provider>/callback-info` endpoint. Default:
     synthesize on client — avoids new endpoint, matches what server.py
     does internally in `_redirect_uri_for`.
- **Orchestrator handoff:** Will be promoted to
  `HANDOFF_TO_ORCHESTRATOR.md` when the Orchestrator picks up this mission
  and creates the Linear issue. Mission folder name:
  `.agents/orchestration/tenant-integrations-reconnect-ui/`.

### Read-Only Unified Person Lifecycle Foundation V1

- **Readiness status:** needs decision.
- **Source strategy plan:**
  `.agents/strategy/UNIFIED_PERSON_LIFECYCLE_SEMANTIC_ANALYTICS_PLAN.md`
- **Business goal:** Translate the manager-provided unified patient / lead
  profile requirements into Fusion CRM's existing person, provenance, semantic
  analytics, context, and agent architecture. The first outcome should be a
  read-only lifecycle and profile foundation that lets dashboards, manager
  chat, reports, Data Intelligence tooling, and future context packs reuse the
  same `person_uid`-centric evidence and business meanings.
- **Why now:** Salesforce and CareStack evidence is already flowing through
  the platform, including leads, source/UTM fields, appointments, treatment
  procedure evidence, invoices, accounting transactions, payment summaries,
  operational timeline events, and aggregate analytics. The manager spec
  confirms that the next value is not another raw-provider pull, but a stable
  lifecycle/profile contract over the data already being captured.
- **Expected outcome:**
  1. The manager spec is recorded as a business input, not a literal schema
     prescription.
  2. A source-of-truth precedence contract defines which Salesforce and
     CareStack signals are authoritative for read-only analytics and profile
     views.
  3. A lifecycle stage taxonomy is defined for `new`, `qualified`,
     `consult_scheduled`, `consult_completed`, `treatment_accepted`,
     `surgery_scheduled`, `closed_won`, and `closed_lost` or reviewed
     successors.
  4. Semantic catalog extension candidates are documented for lifecycle,
     linkage, source precedence, revenue, balance, sync, and write-back state.
  5. Read-model gaps are defined for lifecycle summary, lifecycle funnel,
     stage history, revenue by source, outstanding balance, identity linkage
     quality, and sync/reconcile health.
  6. Existing evidence coverage is audited before implementation claims are
     made: Salesforce leads/events/tasks/opportunities/cases, CareStack
     patients/appointments/treatments/invoices/accounting transactions/payment
     summaries, source-link coverage, and skipped/unlinked rows.
  7. Manager Chat V2 boundaries are defined: approved query specs and policy
     preflight only; no raw SQL, raw provider payload output, or unrestricted
     full person profile dumps.
  8. Write-back remains explicitly deferred until read-only contracts,
     lifecycle semantics, row-level policy, source-link quality, and audit
     requirements are stable.
- **Assumptions:**
  - `identity.person.id` remains the canonical `person_uid`.
  - Existing raw-to-context and person provenance strategy documents remain
    authoritative.
  - Current provider feeds are sufficient for a read-only planning and
    coverage-audit slice.
  - Billing and PHI-adjacent data may be visible only through reviewed service
    contracts, field allowlists, data-class markings, and audit.
  - Manager Chat V1 remains aggregate-only while V2 is planned.
  - Data Intelligence Agent outputs remain review-only; they do not approve
    catalog meaning or start execution.
- **Architecture constraints:**
  - Do not create a literal manager-spec `patients` database as product truth.
  - Keep provider payloads in `ingest.raw_event`; product surfaces consume
    service-owned projections, timeline events, context packs, and read models.
  - `ops` remains PHI-free; clinical content stays behind `PhiService`.
  - Agents do not access the database directly.
  - No raw SQL from chat, dashboards, agents, or workbench surfaces.
  - Routes/jobs call services; services call repositories; repositories stay
    data-only.
  - No provider write-back, external side effects, deployment changes, secrets,
    OAuth/CORS, Cloud Run, deploy scripts, or GitHub Actions changes in this
    mission.
- **Suggested decomposition:**
  - **Task A:** Requirements alignment brief: map manager spec sections to
    Fusion CRM architecture and mark literal-schema items that are rejected or
    deferred.
  - **Task B:** Evidence coverage audit: report which existing feeds and
    services support each requested lifecycle/profile/analytics concept and
    where data is missing, skipped, unlinked, or only raw.
  - **Task C:** Source-of-truth precedence contract for Salesforce and
    CareStack read-only fields.
  - **Task D:** Lifecycle stage taxonomy and stage-transition semantics.
  - **Task E:** Semantic catalog extension candidate proposals for lifecycle,
    linkage, source, revenue, balance, sync, and write-back terms.
  - **Task F:** Read-model V2 contract draft for lifecycle, revenue, balance,
    linkage quality, and sync/reconcile health.
  - **Task G:** Manager Chat V2 scope brief: aggregate-first, bounded
    row-level later, person context tools separate from analytics chat.
  - **Task H:** Write-back deferral brief: define prerequisites and risks
    before any write router or external write tools are scoped.
- **Risks:**
  - Treating the manager's proposed schema as authoritative would violate the
    repo architecture and duplicate domain meaning.
  - Claiming data completeness without coverage audit could produce misleading
    lifecycle or revenue analytics.
  - Row-level billing worklists can expose sensitive data if field allowlists
    and audit are weak.
  - Manager Chat V2 can drift into raw data browsing unless it stays registry
    and policy driven.
  - Write-back too early can create external side effects before source
    precedence, approval, retry, and audit behavior are stable.
- **Human decisions needed:**
  1. Confirm attribution model: catalog default, first touch, last touch, or a
     reviewed alternative.
  2. Confirm `paid_lead` semantics for V2: any payment, deposit, paid in full,
     or separate variants.
  3. Confirm who may see billing-sensitive row-level worklists.
  4. Confirm whether Manager Chat V2 starts aggregate-only or may include
     bounded row-level worklists for authorized users.
  5. Confirm whether Galleria OMS has CareStack access or remains Salesforce
     only until another adapter exists.
  6. Confirm manual merge ownership: admin-only, TC-facing, or operator queue.
  7. Confirm write-back remains deferred until read-only profile and lifecycle
     contracts stabilize.
- **Orchestrator handoff:** Added to
  `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` as
  "Read-Only Unified Person Lifecycle Foundation V1".

### Household Identity Grouping, Duplicate Alerting & Merge

- **Readiness status:** needs decision (operator open items 1-5 below). Linear
  epic ENG-552 + foundation ENG-341 (A) + children ENG-553 (B) / ENG-554 (C) /
  ENG-555 (D) / ENG-556 (E1) / ENG-557 (E2) created under team Engineering
  (operator directed Linear creation). Design spec:
  `.agents/strategy/HOUSEHOLD_IDENTITY_GROUPING_DESIGN.md`.
- **Business goal:** Represent shared household contacts correctly: distinct
  persons may share a phone/email, are linked into a family/account block, and
  only genuine same-person duplicates get merged — with operator visibility
  (Messenger alert) and a merge mechanism.
- **Why now:** Follows the ENG-541 dedup epic + ENG-550 prod live pass, which
  left 1,144 ambiguous shared-contact candidates open. The global
  `UNIQUE(kind,value)` on phone/email is the structural blocker (ENG-340 only
  band-aided it by dropping the 2nd person's contact).
- **Expected outcome:** (A) phone/email non-unique; (B) household grouping over
  persons; (C) marketing "one phone = one outreach target" projection; (D)
  Messenger alert on suspicious duplicate; (E1) operator merge on our side; (E2)
  provider-side merge push (later).
- **Architecture constraints:** hard identity invariant (global person,
  identifier uniqueness, append-only merge_event, DOB/SSN never logged),
  propose-before-implement, real patient data, migrations immutable; keep the
  marketing projection (C) out of `identity`; provider write-back (E2) gated hard.
- **Suggested decomposition:** A -> (B, D in parallel) -> E1 -> C -> E2.
- **Risks:** one-way constraint drop (pre-check dupes); layer leakage (marketing
  editing identity); alert noise (1,144 existing open candidates — no retro-blast);
  E2 is a new external-write surface (BAA/consent).
- **Human decisions needed:**
  1. Household-block anchor (CareStack accountId + fallback?).
  2. Marketing contact = separate projection?
  3. Alert trigger (new-on-shared / open-duplicate / both — recommend the latter).
  4. Provider-side merge push = later phase?
  5. "Suspicious" tie-break rules (same name + missing DOB => alert; different
     DOB => household, no alert).
- **Orchestrator handoff:** pending — promote to HANDOFF_TO_ORCHESTRATOR.md once
  operator resolves decisions 1-5 (status flips to "ready for orchestrator").
