# Raw To Context Normalization Spec

## Purpose

This spec defines how Fusion CRM stores, normalizes, reviews, and promotes
provider data from Salesforce, CareStack, and future systems.

It exists to prevent two failure modes:

1. dumping raw provider payloads into agent prompts or product UI;
2. over-normalizing vendor fields before the team understands their business
   meaning.

The strategy is:

```text
capture everything
-> normalize the minimum needed to find, sort, filter, and review
-> let humans and approved agents interpret meaning
-> promote stable meaning into canonical projections and context packs
```

## Core Rule

Every provider field starts as evidence, not product truth.

A field becomes product truth only after it has a defined meaning, data class,
source reference, owner, and consumer.

## Layer Model

### Layer 0: Raw Evidence

Purpose: preserve everything as received for replay, audit, debugging, and
future reinterpretation.

Canonical storage:

- `ingest.raw_event`

Required fields:

- `tenant_id`
- `source`
- `event_type`
- `external_id`
- `received_at`
- `payload`
- processing status/error metadata

Rules:

- Store the payload before interpretation.
- Do not drop provider fields during capture.
- Do not expose raw payloads to ordinary production UI or agent prompts.
- Raw payloads may contain PHI or PHI-adjacent data.

### Layer 1: Minimal Index / Review Staging

Purpose: make raw evidence visible and reviewable without pretending the whole
provider payload is normalized.

Typical fields:

- `tenant_id`
- `person_uid` when resolved
- `raw_event_id`
- `source_system`
- `source_instance`
- `source_kind`
- `source_id`
- `observed_at`
- obvious display/status fields
- `data_class`
- `review_status`
- `payload_sha256` or equivalent evidence hash

Examples of acceptable minimal fields:

- appointment start time;
- provider status code;
- invoice amount;
- transaction date;
- treatment procedure status id;
- external object id;
- deleted/tombstone flag.

Rules:

- Keep this layer narrow.
- Prefer generic fields and typed metadata over provider-specific domain
  tables.
- Fields here support tables, filters, sorting, and human review.
- A field in staging does not automatically become part of agent context.

### Layer 2: Canonical Projections

Purpose: store stable product-facing entities and facts.

Canonical homes:

- `identity` for person identity and source links;
- `ops` for PHI-free CRM and operational projections;
- `phi` for clinical data through `PhiService`;
- future `billing` for patient-linked financial ledger;
- `interaction` for normalized person timeline events;
- `integrations.external_entity` for rare provider objects without a stable
  domain home.

Promotion criteria:

- The field has a known business meaning.
- The data class is known.
- The consumer is known.
- The value is needed for UI, workflow, search, reporting, or agent context.
- The source reference is preserved.
- Tests can prove redaction/allowlist behavior.

Rules:

- Do not mirror vendor schemas as domain tables.
- Do not add columns just because the provider has fields.
- Prefer additive promotion: raw evidence remains the replay source.

### Layer 3: Semantic Interpretation

Purpose: turn data into controlled meaning.

Storage direction:

- `context.context_fact` when persistent context is needed;
- versioned taxonomy artifacts when a label becomes operational;
- human review/workbench decisions while labels are still being designed.

Examples:

- `statusId=3` -> `treatment_stage=accepted`
- completed consultation with no surgery scheduled -> `reactivation_candidate`
- accounting transaction credit -> `payment_received`
- unpaid invoice amount -> `balance_status=outstanding`

Rules:

- Deterministic mapping comes first.
- Ambiguous interpretation needs human review or a specialized semantic agent.
- Interpretations that affect workflow, marketing, PHI visibility, or external
  actions require approval before production behavior changes.
- Interpretations are versioned and source-linked.

### Layer 4: Agent Context Packs

Purpose: provide task-specific, least-privilege context to agents.

Examples:

- `speed_to_lead_context`
- `person_timeline_context`
- `consultation_context`
- `treatment_status_context`
- `revenue_status_context`
- `workflow_context`

Required fields:

- task purpose;
- `person_uid`;
- allowed data classes;
- included facts and events;
- source references;
- confidence/review status;
- PHI/PHI-adjacent status;
- approved AI route/lane;
- allowed tools;
- approval boundary.

Rules:

- Context packs are not SQL result dumps.
- Context packs are assembled by services.
- Agents do not read raw provider payloads or repositories directly.
- PHI-capable packs require a PHI-capable agent lane.

## Human Table / Workbench Contract

Humans need a table-oriented surface before full semantic certainty exists.

The review table should show:

- source;
- object type;
- external id;
- resolved person;
- observed/occurred time;
- obvious status/date/amount fields;
- data class badge;
- review status;
- source link/raw event reference;
- derived labels, if any;
- whether the item is safe for marketing/ops context.

The workbench must distinguish:

- raw evidence fields;
- minimal index fields;
- canonical projection fields;
- derived semantic labels;
- approved agent-context fields.

## Promotion Workflow

Provider fields move through this lifecycle:

```text
observed
-> captured
-> indexed
-> reviewed
-> named
-> classified
-> used
-> promoted
```

Promotion questions:

1. What business question does this field answer?
2. Is it PHI, PHI-adjacent, ops-safe, or public?
3. Is it needed by a human table, workflow, report, or agent?
4. Is the meaning deterministic or review-based?
5. What source event proves it?
6. What happens when the provider value changes or is deleted?
7. Does this field need a durable column, a JSON projection, or only a context
   label?

## CareStack Initial Scope

CareStack objects should start as raw evidence plus minimal index rows, then
promote only the stable operational meaning.

| Source | Minimal index | Candidate projection/context |
|---|---|---|
| Patient | `person_uid`, `carestack_patient_id`, contact hints | `identity.person`, `phi.patient_profile`, safe person summary |
| Appointment | `person_uid`, appointment id, time, status, location | `ops.consultation`, `interaction.event`, `consultation_context` |
| Treatment Procedure | `person_uid`, procedure id, status id, appointment id, dates | `treatment_status_context`, future `phi.treatment_case` / procedure model |
| Invoice | invoice id, patient/person, amount, date, type, deleted flag | future `billing.invoice`, `revenue_status_context` |
| Accounting Transaction | transaction id, person, amount, type, invoice id, date, reversal flag | future `billing.accounting_transaction`, `ops.revenue_event` |
| Payment Summary | person, amount/status summary, payment type | `revenue_status_context`, safe revenue summary |
| Payment Type / Procedure Code | catalog id, code/name, active flag | catalog/reference data, non-person context |

Initial agent-safe labels may include:

- `consultation_scheduled`
- `consultation_completed`
- `consultation_no_show`
- `treatment_proposed`
- `treatment_accepted`
- `treatment_declined`
- `surgery_scheduled`
- `surgery_completed`
- `invoice_issued`
- `payment_received`
- `payment_failed`
- `refund_issued`
- `balance_outstanding`
- `reactivation_candidate`

## Salesforce Initial Scope

| Source | Minimal index | Candidate projection/context |
|---|---|---|
| Lead | `person_uid`, lead id, status, created date, source/campaign hints | `ops.lead`, `interaction.event`, `speed_to_lead_context` |
| Contact | `person_uid`, contact id, contact hints | `identity.source_link`, person identity enrichment |
| Event | `person_uid`, event id, start/end, type/status | `ops.consultation`, `interaction.event` |
| Task | `person_uid`, task id, subject/status/due date/owner | `ops.followup_task` or `interaction.event`; decide by lifecycle |
| Account | account id, name, owner | `ops.account` |

## Decision Points Before Implementation

1. Whether Layer 1 needs a generic persisted staging table beyond
   `normalized_person_hint`, or whether each source handler owns its own narrow
   index/projection until repeated patterns justify a shared table.
2. Whether billing objects land first in future `billing` tables or remain
   raw/staged with only `ops.revenue_event` projections.
3. Which labels are approved for marketing-safe context.
4. Which labels require human review before agent use.
5. Which PHI-capable agent lane and AI vendor routes are approved.
6. Which UI/workbench screens are allowed to show raw evidence during
   development.

## Verification Expectations

Every implementation mission using this spec should verify:

- raw payload captured before mapping;
- raw payload excluded from ordinary timeline/context outputs;
- every displayed/projection row has a source reference;
- unresolved person records remain reviewable instead of silently dropped;
- PHI/PHI-adjacent fields carry data-class markings;
- marketing-safe context does not include raw clinical, insurance, or ledger
  payloads;
- PHI-capable agent context uses only approved routes and writes audit rows.

