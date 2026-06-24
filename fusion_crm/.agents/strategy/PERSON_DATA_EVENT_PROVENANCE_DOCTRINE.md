# Person Data And Event Provenance Doctrine

## Purpose

Fusion CRM is starting to ingest raw Salesforce and CareStack data for people,
events, and provider objects. This doctrine defines how those observations
become governed, traceable, agent-usable knowledge without letting agents reason
directly over raw provider schemas.

The core problem is not only ingestion. It is controlled meaning:

```text
provider data
-> durable evidence
-> canonical person identity
-> domain projection
-> semantic interpretation
-> agent-safe context
```

## Current Position

The repository already has the building blocks:

- `identity.person.id` is the canonical `person_uid`.
- `ingest.raw_event` stores raw provider payloads as immutable evidence.
- `ingest.normalized_person_hint` extracts provider-neutral matching signals.
- `identity.source_link` records provider-object provenance for a person.
- `identity.match_candidate` records explainable identity decisions.
- `ops` stores PHI-free CRM projections such as leads and consultations.
- `phi` stores clinical data behind `PhiService` and audit.
- `interaction.event` is the normalized event timeline direction.
- `context` is the future semantic layer consumed by workflows and agents.

The missing piece is an explicit operating doctrine tying those parts together
for every Salesforce and CareStack object or event.

## Doctrine

### 1. Raw Evidence First

Every provider signal is captured before interpretation:

```text
Salesforce CDC / API pull / webhook
CareStack sync row / API pull
-> ingest.raw_event
```

Raw events preserve the provider payload for replay, debugging, compliance, and
parser correction. They are not an agent interface. Raw payloads may contain
PHI and must not be exposed to production dashboards, agent prompts, logs, or
tool responses except through explicitly gated local-dev inspector surfaces.

### 2. One Person Graph, Not Provider Silos

Fusion CRM must not create provider-shaped domain tables such as
`salesforce_lead_person` or `carestack_patient_person`.

Every provider person-like object resolves to:

```text
identity.person.id == person_uid
```

The provider-specific origin is recorded through:

```text
identity.source_link(
  person_uid,
  source_system,
  source_instance,
  source_kind,
  source_id
)
```

Identifiers used for lookup belong in `identity.person_identifier`. Provenance
belongs in `identity.source_link`. Ambiguous matches belong in
`identity.match_candidate`.

### 3. Provider Objects Become Domain Projections

After identity resolution, provider objects are projected into the appropriate
canonical domain:

| Provider object | First canonical home | Notes |
|---|---|---|
| Salesforce Lead | `ops.lead` | PHI-free CRM projection |
| Salesforce Event | `ops.consultation` and/or `interaction.event` | only marketing-safe fields |
| Salesforce Task | `ops.followup_task` or `interaction.event` | depends on lifecycle semantics |
| Salesforce Account | `ops.account` when implemented | not a person |
| CareStack Patient | `identity.person` plus `phi.patient_profile` via `PhiService` | PHI-gated; safe projection only outside `phi` |
| CareStack Appointment | `ops.consultation` and `interaction.event` | consultation attendance, no-show, cancellation, and schedule changes; clinical notes stay out of `ops` |
| CareStack Treatment Procedure | `phi.treatment_case` / future treatment procedure table, plus ops-safe status context | procedure detail is PHI; agents may receive safe stage/outcome summaries |
| CareStack Invoice | future `billing.invoice`, plus ops-safe `ops.revenue_event` when allowed | patient-linked financial data is PHI-adjacent; raw invoice fields are not an agent interface |
| CareStack Accounting Transaction | future `billing.accounting_transaction`, plus ops-safe `ops.revenue_event` | payments, refunds, reversals, balances; preserve ledger evidence and expose safe financial milestones |
| CareStack Payment Summary | future `billing.payment_summary`, plus ops-safe person revenue summary | mixed sensitivity; amount/status may be safe only through an approved projection |
| Rare provider object | `integrations.external_entity` | promote only when it earns a real domain lifecycle |

Provider payloads stay in `ingest.raw_event`; domain projections store the
smallest stable operational representation needed by the product.

### 4. Events Are Normalized Before Agents See Them

Agents should not inspect raw Salesforce or CareStack event names. Every
workflow-relevant signal should become a normalized timeline event:

```text
interaction.event(
  person_uid reference through from_person_uid / to_person_uid,
  event_type,
  source_system,
  occurred_at,
  raw_event_id,
  contains_phi,
  meta
)
```

The person timeline is not a dump of all source data. It is an ordered,
minimum-necessary event stream with source references back to raw evidence.

For CareStack, the operational timeline must eventually cover the full
person-linked lifecycle, not only appointments:

```text
consultation scheduled
-> consultation completed / no-show / cancelled
-> treatment proposed / accepted / declined
-> surgery scheduled / completed
-> invoice issued
-> payment received / failed / refunded
-> outstanding balance changed
```

Some of these events originate in PHI or PHI-adjacent feeds. The timeline entry
that agents see must be an ops-safe projection with a source reference, not the
raw clinical, treatment, insurance, or ledger payload.

### 5. Semantic Interpretation Is A Separate Layer

Provider fields and normalized events are still not enough for agents. They
must be interpreted into a controlled taxonomy:

```text
raw_event
-> domain projection
-> interaction.event
-> semantic interpretation
-> context.context_fact
```

Examples:

- `utm_source=google`, `utm_medium=cpc` -> `source_channel=paid_search`
- CareStack appointment status -> `consultation_status=scheduled|completed|no_show`
- Salesforce custom field -> `treatment_intent=full_arch`
- message transcript -> `intent=schedule`, `objection=financing`, `urgency=high`

Deterministic mapping comes first. Specialized semantic agents may classify
ambiguous text, but their output is structured, versioned, reviewed when needed,
and never allowed to silently mutate production taxonomy.

### 6. Agent Context Packs Are Task-Specific

Agents receive context packs assembled by services, not raw tables.

A context pack must declare:

- target `person_uid`;
- task purpose;
- allowed data classes;
- source event references;
- semantic facts and confidence;
- PHI status and redaction policy;
- review status;
- available tools;
- approval boundary.

Examples:

- `speed_to_lead_context`
- `person_timeline_context`
- `lead_operational_context`
- `consultation_context`
- `workflow_context`

The same person can produce different context packs for different agents. A
growth agent may receive PHI-free lead and consultation signals. A clinical
agent may require `PhiService`-gated context with audit and tighter approval.

PHI is not categorically forbidden from agent input. Fusion CRM may support a
separate PHI-capable agent lane when all of the following are true:

- the AI vendor account and model/API route are covered by an executed BAA and
  approved for PHI workloads;
- the storage, logs, traces, and runtime environment used by that lane are also
  covered by the clinic's compliance posture;
- the context pack is minimum-necessary for the clinical or operational task;
- the tool/service boundary performs permission checks before assembly;
- the tool call and any PHI access are audited;
- the agent output is classified before it can be reused by non-PHI workflows.

In other words, the rule is not "agents never see PHI." The rule is "only
PHI-authorized agents, running on PHI-authorized vendors and infrastructure,
receive purpose-built PHI context packs through audited services."

### 7. Data Class And PHI Boundaries Are First-Class

Every projection or context object must be classified:

- `raw_provider`
- `ops_safe`
- `phi`
- `redacted`
- `derived_context`
- `agent_input`
- `agent_output`

CareStack patient data is assumed PHI-sensitive unless explicitly allowlisted.
Salesforce data is not assumed PHI-free merely because it comes from CRM; custom
fields and notes can contain clinical or sensitive content.

### 8. Development Visibility Versus Production Enforcement

During the development phase, before real users have broad product access, the
platform may use a classification-first visibility mode:

- show PHI-sensitive or PHI-adjacent operational facts to authenticated internal
  builders when needed for development, verification, taxonomy design, and
  agent-behavior design;
- visibly mark those facts with data-class badges such as `PHI`,
  `PHI-adjacent`, `ops-safe`, or `redacted`;
- provide an authorized human review/workbench surface where builders with an
  explicit pass can inspect source facts, classify meaning, and define what can
  become an ops-safe or marketing-safe interpretation;
- keep raw provider payloads out of ordinary agent prompts, logs, dashboards,
  and tool responses unless the surface is explicitly local-dev gated;
- preserve source references so every displayed fact can be traced back to the
  raw evidence and projection path;
- treat every such display as temporary development posture, not the production
  access model.

Before real production access expands beyond the internal build group, the same
surfaces must switch from classification-only to enforcement:

- server-side permission checks before PHI or PHI-adjacent data is returned;
- role/capability-scoped staff access;
- audit rows for successful and denied PHI reads;
- least-privilege agent context packs, including PHI-capable packs only on
  BAA-covered AI routes;
- deny-by-default behavior for unknown data classes.

UI highlighting is helpful, but it is not a security boundary. The production
boundary must live in services and tools.

The human review/workbench lane is the bridge between PHI evidence and
marketing interpretation:

```text
PHI / PHI-adjacent source fact
-> authorized human review
-> semantic label / taxonomy proposal
-> ops-safe or marketing-safe projection
-> agent context pack for non-clinical workflows
```

Examples:

- treatment procedure details may support a safe label such as
  `treatment_stage=accepted` or `surgery_status=scheduled`;
- a completed consultation with no surgery scheduled may support
  `reactivation_candidate=true`;
- payment ledger details may support `balance_status=outstanding` or
  `payment_received`, without exposing clinical or raw ledger payloads to a
  marketing agent.

The workbench must make it obvious which fields are raw evidence, which fields
are derived interpretations, and which derived outputs are safe for downstream
marketing or ops agents.

### 9. Replay And Reprocessing Must Be Possible

The system should be able to reprocess old evidence when mappings, taxonomy, or
prompts improve:

```text
raw_event
-> same identity/source-link result or explicit match_candidate drift
-> new projection version if needed
-> new context_fact version
```

No workflow-changing interpretation should be overwritten in place. New meaning
is versioned, linked to source evidence, and reviewable.

## Required Taxonomy Surfaces

Before agent workflows rely on this layer, the platform needs controlled
taxonomies for:

- `source_system`: `salesforce`, `carestack`, `twilio`, `vapi`, `web_form`,
  `manual`, `import`.
- `source_instance`: tenant/provider instance slug.
- `source_kind`: `lead`, `contact`, `patient`, `appointment`, `task`, `event`,
  `caller`, `sms_sender`, `submitter`, plus approved additions.
- `interaction.event_type`: normalized business event names.
- `context_type` and `context_key`: stable semantic vocabulary.
- data class: PHI and agent-visibility categories.
- identity match rules: auto-accept, open candidate, manual review, reject.

Taxonomy changes that affect routing, agent prompts, PHI exposure, workflow
state, or external actions require human approval.

## Proposed Task Block

### Block A: Doctrine And Inventory

Goal: make the data path explicit before more provider objects land.

- Inventory Salesforce and CareStack objects currently ingested or planned
  next, including CareStack appointments, treatment procedures, invoices,
  accounting transactions, payment summaries, and payment types.
- Map each object to raw evidence, identity, source link, domain projection,
  interaction event, and context output.
- Identify fields that are PHI, sensitive, ops-safe, or unknown.
- Document the first event taxonomy for Phase 1 and Phase 2.

### Block B: Person Timeline Foundation

Goal: create a stable, queryable person event surface.

- Define the minimum `interaction.event` taxonomy for Salesforce Lead/Event and
  CareStack Patient/Appointment/Treatment/Billing milestones.
- Ensure each normalized event links to `person_uid`, `raw_event_id`,
  `source_system`, `occurred_at`, and `contains_phi`.
- Define `GET /persons/{uid}/timeline` behavior as service-owned and
  PHI-aware.
- Add tests that verify raw provider payloads do not leak into timeline output.

### Block C: Agent Context Pack Foundation

Goal: make agents consume governed context instead of raw data.

- Define the first context pack contracts:
  `speed_to_lead_context`, `person_timeline_context`,
  `consultation_context`, `treatment_status_context`,
  `revenue_status_context`.
- Define allowed fields, denied fields, source references, confidence, and
  review status for each pack.
- Add service-level builders for context packs.
- Add audit coverage for agent tool reads.

### Block D: Taxonomy Governance

Goal: prevent taxonomy drift as agents and provider fields expand.

- Create a versioned taxonomy registry for event types and context keys.
- Define approval flow for taxonomy changes that affect workflow or agent
  behavior.
- Add reprocessing rules for changed mappings.
- Add evaluation fixtures so new taxonomy versions can be tested against known
  Salesforce and CareStack examples.

## Decisions Needed

1. Initial scope: only Salesforce Lead/Event and CareStack Patient/Appointment,
   or all near-term Salesforce/CareStack objects.
2. Whether `interaction.event` ships before the full `context` schema, or the
   first context pack is built on demand from existing projections.
3. Which CareStack fields are allowed in `ops.consultation` and timeline output.
4. Which Salesforce custom fields are safe for `ops` and agent context.
5. Who approves identity merge candidates and taxonomy changes.
6. Whether the first mission should be documentation-only or include schema/API
   implementation work.

## Recommended Next Move

Promote a candidate mission named
`Person Data And Event Provenance Foundation` to the Orchestrator after the
scope and PHI-boundary decisions above are resolved.
