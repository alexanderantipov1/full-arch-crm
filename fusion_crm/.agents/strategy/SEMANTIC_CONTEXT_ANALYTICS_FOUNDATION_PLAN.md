# Semantic Context And Analytics Foundation Plan

## Purpose

Fusion CRM needs one shared semantic and analytics foundation that can serve
three different consumers without redefining business meaning in each surface:

1. manager dashboards;
2. manager AI chat;
3. internal Data Intelligence agents that help the team discover data, define
   metrics, and prepare implementation work for the Orchestrator.

The goal is not to build a universal SQL interface. The goal is to create a
safe, typed, policy-aware analytics layer where business questions are mapped
to approved semantic definitions, structured query specs, read models, and
audited services.

This foundation should let the team answer questions such as:

- Which lead sources are producing paid patients?
- Which Facebook leads reached consultation?
- Which consultations have no next step?
- Which leads accepted treatment after consultation?
- Which sources have the highest no-show rate?
- Which patients have outstanding balance?
- Which hot leads have no follow-up?
- Which campaigns produce revenue evidence?

The same definitions and query contracts must be reusable from multiple
angles: visual dashboards, chat answers, drilldown tables, scheduled reports,
agent context packs, internal data exploration, and future workflow triggers.

## Strategic Rationale

The platform already receives evidence from Salesforce, CareStack, and future
systems. Raw provider data is valuable, but raw provider fields are not product
truth. The business needs stable meanings such as `paid_lead`,
`converted_to_consultation`, `facebook_source`, `treatment_accepted`,
`payment_received`, `balance_outstanding`, `no_next_action`, and
`reactivation_candidate`.

If these meanings are implemented separately in the dashboard, chat bot,
agents, reports, and workflow code, the product will drift quickly. The same
question will return different answers depending on which surface asked it.

The strategic direction is:

```text
raw provider evidence
-> minimal review/index fields
-> canonical projections and interaction events
-> persistent context facts when needed
-> semantic analytics terms
-> structured query specs
-> policy preflight
-> approved analytics services and read models
-> dashboard, manager AI chat, internal Data Intelligence agent
```

This plan extends the existing strategy documents:

- `PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`
- `RAW_TO_CONTEXT_NORMALIZATION_SPEC.md`

Those documents define how raw provider observations become person-linked
evidence, normalized events, semantic facts, and agent-safe context packs. This
plan defines how those facts and projections become business analytics,
dashboard metrics, manager chat answers, and development-time data discovery.

## Business Outcomes

The foundation should support these outcomes:

1. Managers can ask operational questions in natural language and receive
   trustworthy answers with the applied definition visible.
2. Dashboards and chat answers use the same metric definitions.
3. Analysts can drill from aggregate metrics into allowed row-level cohorts
   when their role permits it.
4. Internal Data Intelligence agents can inspect local data through approved
   read-only tools, find gaps, and propose new semantic mappings or query
   specs.
5. New dashboards, tables, charts, and reports can be added by registering
   typed queries instead of writing ad hoc SQL per feature.
6. PHI, billing, and operational data classes are handled consistently through
   policy and audit.
7. The Orchestrator can split implementation into focused missions with clear
   scope, dependencies, and verification gates.

## Consumers

### Manager Dashboard

The dashboard uses approved analytics queries to render stable tables, charts,
filters, KPI cards, drilldowns, and exports.

Example queries:

- `lead_source_profile`
- `conversion_funnel`
- `paid_leads`
- `revenue_by_source`
- `owner_performance`
- `consultation_followup`
- `treatment_revenue`
- `unmatched_salesforce_leads`

The dashboard should not contain metric business logic in browser code.
Business logic belongs in backend services and read models.

### Manager AI Chat

The manager chat bot interprets a user question, maps it to a structured query
spec, runs policy preflight, calls an approved analytics service, and explains
the result in plain language.

The chat bot must not generate raw SQL. It selects from allowed intents,
semantic terms, filters, dimensions, metrics, and output shapes.

The answer should show how the system understood the question, for example:

```text
Understood as: paid_leads from facebook_source during the last 30 days.
Definition version: paid_lead v1, facebook_source v1.
Output: aggregate table with allowed drilldown.
```

### Data Intelligence Agent

The Data Intelligence Agent is an internal planning and discovery agent. It is
not a production manager-facing chatbot.

Its responsibilities:

- inspect schemas, DTOs, services, migrations, tests, and provider docs;
- use approved local read-only data tools to profile real local data;
- identify fields, joins, source systems, data classes, gaps, and quality
  issues;
- propose semantic mappings and analytics terms;
- propose new query specs, read models, and dashboard panels;
- prepare candidate missions and Orchestrator handoffs.

It must not access the database directly. Local data inspection should go
through approved read-only Data Intelligence tools with table/query allowlists,
row limits, redaction, and audit/logging.

## Layer Model

### Layer 1: Manager Analytics Questions V1

Before building a generic system, collect 20 to 30 real manager questions.
These questions define which terms, read models, services, and UI workflows
matter first.

Seed questions:

- Show paid leads from the last 30 days.
- Show Facebook leads that reached consultation.
- Show consultations without a next step.
- Show who paid after consultation.
- Show no-shows by source.
- Show Google Ads leads that accepted treatment.
- Show patients with outstanding balance.
- Show hot leads without follow-up.
- Show revenue by lead source.
- Show leads linked to CareStack but missing a next appointment.
- Show Salesforce leads that could not be linked to a person.
- Show campaigns with the best consultation conversion rate.
- Show owners with stale leads.
- Show treatment accepted but not paid.
- Show payment evidence by campaign.

Output artifact:

- `Manager Analytics Questions V1`

### Layer 2: Semantic Analytics Catalog

The catalog defines business terms and how they map to data.

Each term should include:

- human phrases and synonyms;
- exact business definition;
- source systems and canonical fields;
- source evidence references;
- data class: ops, billing, PHI, PHI-adjacent, integration metadata;
- required permission;
- whether row-level output is allowed;
- whether aggregate-only output is required;
- allowed returned fields;
- version;
- owner and review status.

Example terms:

- `paid_lead`
- `converted_to_consultation`
- `facebook_source`
- `treatment_accepted`
- `payment_received`
- `balance_outstanding`
- `no_next_action`
- `reactivation_candidate`
- `no_show`
- `carestack_linked`

The catalog prevents LLM guessing. The LLM may choose from catalog terms, but
must not invent production definitions silently.

### Layer 3: Context Facts And Analytics Terms

`context_fact` and analytics terms are related but not the same.

`context_fact` records person-linked or event-linked semantic facts, for
example:

- lead source evidence exists;
- consultation was completed;
- appointment was no-show;
- payment evidence exists;
- balance is outstanding;
- follow-up is stale.

Analytics terms define business metrics and cohorts over facts and projections,
for example:

- `paid_lead` equals a lead with payment evidence inside an attribution window;
- `converted_to_consultation` equals a lead linked to a completed
  consultation;
- `facebook_source` equals raw source values mapped to paid social Facebook
  semantics;
- `no_next_action` equals a completed consultation without a scheduled next
  step after a configured threshold.

This separation lets the same facts support agent context, workflow triggers,
analytics cohorts, and dashboard metrics without duplicating interpretation.

### Layer 4: Structured Analytics Query Spec

The LLM and UI should produce structured query specs, not SQL.

Example:

```json
{
  "intent": "list_cohort",
  "cohort": "paid_leads",
  "filters": {
    "source_channel": "facebook",
    "date_range": "last_30_days"
  },
  "dimensions": ["location"],
  "metrics": ["lead_count", "payment_total"],
  "output": "table"
}
```

The query spec is the contract between the planner, policy layer, services,
and UI. It should be validated before execution.

Initial intent candidates:

- `summarize_metric`
- `list_cohort`
- `compare_periods`
- `breakdown_by_dimension`
- `trace_conversion`
- `find_gaps`
- `drilldown`
- `export_allowed_rows`

Initial dimensions:

- date range;
- lead source;
- semantic source channel;
- campaign;
- location or center;
- owner;
- provider;
- consultation status;
- treatment status;
- payment status.

Initial metrics:

- lead count;
- consultation count;
- consultation conversion rate;
- no-show count and rate;
- treatment accepted count;
- payment count;
- payment total;
- outstanding balance total;
- stale follow-up count.

### Layer 5: Policy Preflight

Before execution, the backend checks:

- authenticated user;
- role and permissions;
- requested data classes;
- whether PHI is needed;
- whether billing data is needed;
- whether row-level people data is allowed;
- whether aggregate-only output is required;
- whether export is allowed;
- whether audit is required;
- whether the request is ambiguous and requires clarification.

If the request is unsafe or unclear, the system should clarify rather than
guess.

Example clarification:

```text
Do you want aggregate counts only, or are you asking for row-level people?
Row-level output may require additional permission because this query touches
billing or PHI-adjacent data.
```

### Layer 6: Analytics Services And Query Registry

The backend exposes approved typed queries through services. The services own
business logic and repositories remain data-only.

Candidate services:

- `LeadAnalyticsService`
- `ConsultationAnalyticsService`
- `RevenueAnalyticsService`
- `TreatmentAnalyticsService`
- `PersonCohortService`
- `DataCatalogService`
- `DataIntelligenceService`

The query registry describes each allowed query:

- query id;
- description;
- params schema;
- result schema;
- allowed roles;
- allowed environments;
- data classes touched;
- whether PHI is possible;
- whether billing is possible;
- max row count;
- sample policy;
- export policy;
- audit requirements;
- safe for manager AI chat;
- safe for internal Data Intelligence agent.

The registry makes queries discoverable by UI and agents while preventing raw
SQL execution.

### Layer 7: Read Models

Initial read models should focus on the first manager questions:

1. `lead_conversion`
   - leads, sources, consultations, conversion rate.
2. `paid_leads`
   - lead plus payment or invoice evidence.
3. `consultation_followup`
   - completed, no-show, cancelled, next action, stale records.
4. `treatment_revenue`
   - treatment proposed, accepted, completed, invoice, payment, balance.

The first implementation may calculate through services over current canonical
tables. Materialized views or dedicated read-model tables can follow when the
query contracts stabilize.

### Layer 8: LLM Planner

The LLM planner receives:

- allowed intents;
- semantic catalog terms;
- query spec schema;
- example manager questions;
- clarification rules;
- policy summary;
- available output shapes.

The planner returns only a structured query spec or a clarification question.
It does not execute SQL and does not decide final authorization.

### Layer 9: Explainability, Audit, And Result Contracts

Every analytics result should be explainable.

Result contracts should include:

- query id;
- generated timestamp;
- applied semantic definitions and versions;
- applied filters;
- data classes touched;
- aggregation level;
- row count;
- result rows;
- gaps or warnings;
- drilldown availability;
- export availability.

Audit should record:

- user;
- original natural language question, when applicable;
- structured query spec;
- data classes touched;
- permission decision;
- row count;
- whether PHI or billing was accessed;
- whether export occurred;
- service/query id;
- timestamp.

### Layer 10: Expansion

After the first 20 to 30 manager questions and initial read models are stable,
expand into:

- saved questions;
- scheduled reports;
- CSV/XLSX export;
- period comparisons;
- "why?" drilldowns;
- cohort snapshots;
- semantic source mapping workbench;
- quality and gap dashboards;
- context facts for smarter workflow agents;
- manager AI chat history and answer citations.

## Local Data Intelligence Tooling

The Data Intelligence Agent needs to see real local data to understand how
provider fields actually look. This should be implemented through an approved
read-only local tool, not direct database access.

Allowed local capabilities:

- list available query registry entries;
- describe fields and source systems;
- profile distinct values;
- compute null rates;
- sample limited rows;
- inspect source distribution;
- inspect linkage rates between Salesforce, Fusion person, and CareStack;
- detect missing owner/source/campaign mappings;
- detect whether revenue evidence is present;
- propose semantic mappings.

Safety controls:

- local/dev environment only for exploratory samples;
- read-only database user;
- no writes;
- no migrations;
- no full table dumps;
- row limits by default;
- allowlisted schemas, tables, services, and query ids;
- masking or redaction for PHI and sensitive billing fields;
- local audit/log trail;
- no `.env*` access;
- no raw payload exposure to production manager UI or chat.

Production manager chat and dashboard should use the same query registry and
service layer, but with stricter role policy, aggregate defaults, audit, and
export controls.

## Architecture Constraints

- Follow root `CLAUDE.md` and `AGENTS.md`.
- Agents do not access the database directly.
- Routes and jobs call services; services call repositories.
- Repositories are data-only.
- PHI access goes through `PhiService` with audit.
- Raw provider payloads stay evidence-first and are not ordinary production UI
  or agent interfaces.
- `identity.person.id` remains the canonical `person_uid`.
- `ops` remains PHI-free.
- Billing-sensitive and PHI-adjacent data must be classified before surfacing.
- No business logic in API routes or browser-only filtering.
- No deployment, environment variable, secret, OAuth/CORS, Cloud Run, deploy
  script, or GitHub Actions changes unless explicitly scoped under
  `docs/DEPLOYMENT_RULES.md`.

## Candidate Mission Arc

### Mission 1: Manager Analytics Questions V1

Create the first 20 to 30 real manager questions and group them by business
workflow: lead source, consultation, follow-up, treatment, payment, owner,
location, and risk.

Readiness: ready to start after human confirms initial question list owner.

### Mission 2: Semantic Analytics Catalog V1

Define the first semantic terms, synonyms, exact business meanings, data
sources, data classes, permissions, row-level rules, and allowed fields.

Readiness: depends on Mission 1.

### Mission 3: Structured Analytics Query Spec

Define JSON schema, validation, examples, clarification behavior, and planner
constraints.

Readiness: can start after first catalog draft exists.

### Mission 4: Analytics Policy Preflight

Implement policy checks for data class, role, PHI, billing, row-level access,
export, and audit requirements.

Readiness: depends on query spec and initial catalog rules.

### Mission 5: Analytics Services And Query Registry V1

Build allowlisted typed query registry and first service methods for lead
source profile, conversion funnel, consultation follow-up, paid leads, and
revenue evidence.

Readiness: depends on query spec and policy preflight design.

### Mission 6: Manager Analytics Read Models V1

Build or compute the first read models:

- `lead_conversion`;
- `paid_leads`;
- `consultation_followup`;
- `treatment_revenue`.

Readiness: depends on service/query contracts and data classification.

### Mission 7: Data Intelligence Agent V1

Create an internal agent role and local read-only tool access for profiling
real local data, proposing semantic mappings, identifying gaps, and preparing
handoffs.

Readiness: can start after query registry direction and local data tool
safety rules are accepted.

### Mission 8: Manager AI Chat V1

Add chat UI and planner flow that maps manager questions to approved query
specs, runs policy preflight, executes analytics services, and explains
results.

Readiness: depends on catalog, query spec, policy, and first services.

### Mission 9: Exports And Saved Reports

Add CSV/XLSX exports, saved questions, scheduled reports, and audit behavior
for export events.

Readiness: depends on stable result contracts and policy.

## Human Decisions Needed

1. Confirm whether the first scope is manager analytics only, or whether the
   Data Intelligence Agent local tool should be built in parallel.
2. Confirm first 20 to 30 manager questions and priority order.
3. Confirm which roles may see billing-sensitive aggregates and row-level
   records.
4. Confirm whether production manager chat may access row-level people data or
   must start aggregate-only.
5. Confirm whether local exploratory samples may include masked PHI-like
   fields for authorized builders.
6. Confirm export policy for billing and PHI-adjacent results.
7. Confirm naming for the umbrella epic and the first execution mission.

## Recommended First Practical Step

Start with `Manager Analytics Questions V1` and `Semantic Analytics Catalog
V1` as the first planning slice.

This creates stable business meaning before backend services, chat planning,
dashboard panels, read models, exports, or agents depend on those meanings.

The Orchestrator can then split implementation into focused missions with
Linear issues, ownership boundaries, and verification gates.
