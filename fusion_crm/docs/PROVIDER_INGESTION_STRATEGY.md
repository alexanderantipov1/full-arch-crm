# Provider Ingestion Strategy

This document defines how Fusion CRM receives, stores, interprets, and acts on
provider data from Salesforce, CareStack, and future systems.

It operationalizes the repository strategy:

```text
Raw Data
-> Events
-> Semantic Interpretation
-> Workflow Intelligence
-> Agent Decisions
-> Controlled Actions
```

## Core Rule

Fusion CRM must not operate directly on raw provider schemas.

Provider data enters the platform as immutable raw evidence, then becomes
canonical records, semantic context, workflow state, and finally controlled
actions.

## Ingestion Pipeline

Every provider signal follows this path:

```text
Provider signal
-> ingest.raw_event
-> optional hydration from provider API
-> canonical upsert
-> semantic context
-> workflow trigger
-> audited tool/action
```

Definitions:

- **Provider signal:** Salesforce CDC event, Salesforce webhook, CareStack sync
  row, inbound form, or scheduled API pull result.
- **Raw event:** the original provider payload, stored exactly as received in
  `ingest.raw_event`.
- **Hydration:** immediate provider API fetch of the full object when the event
  is only a change notification or lacks the fields needed for context.
- **Canonical upsert:** idempotent update to `identity`, `ops`, `phi`, or
  `integrations.external_entity`.
- **Semantic context:** stable business meaning derived from provider fields.
- **Workflow trigger:** a controlled transition or task, never a direct agent
  side effect.

## Raw Event First

The first durable write for every inbound provider signal is
`ingest.raw_event`.

Do not normalize, scrub, reshape, or drop fields on the way into
`ingest.raw_event`. The raw event is the forensic record that allows replay
when provider payloads change or our parser is wrong.

Raw events can contain PHI. Production systems must not expose verbatim raw
payloads to dashboards, agents, or logs.

## Hydrated Snapshot

For time-sensitive workflows, a CDC/webhook event is often not enough. It
identifies what happened, but the action needs the full operational context.

For Salesforce `Lead` creation, the fast path must:

```text
LeadChangeEvent
-> store raw CDC event
-> fetch full Lead by Id via REST/SOQL
-> store raw hydrated Lead snapshot
-> build speed-to-lead context
```

This protects the call/SMS context from event payload quirks and ensures agents
see the source, UTM fields, campaign fields, custom dental intent fields,
phone/email, location hints, and financing/interest markers needed for the
first interaction.

Hydrated snapshots are also raw provider data and must be treated with the same
privacy restrictions as the original event.

## Speed-to-Lead Fast Path

Speed-to-lead is a business-critical path and is allowed to be more real-time
than the rest of provider sync.

Initial scope:

- Salesforce `LeadChangeEvent`.
- `CREATE` events only.
- Single-account production org first.
- Seconds-level target latency from Salesforce lead creation to Fusion workflow
  trigger.
- No write-back to Salesforce in this phase.
- No unrestricted agent actions.

Pipeline:

```text
/data/LeadChangeEvent
-> ingest.raw_event(source="salesforce", event_type="lead.change")
-> hydrate Lead by Salesforce Id
-> ingest.raw_event(source="salesforce", event_type="lead.snapshot")
-> upsert identity.person and ops.lead
-> emit interaction.event(kind="lead.created")
-> build speed_to_lead_context
-> enqueue controlled call/SMS workflow
-> write audit rows
```

The workflow may call or text quickly, but it must do so through approved
service/tool boundaries with audit. Agents consume `speed_to_lead_context`,
not raw Salesforce field names.

## Other Salesforce Objects

Contacts, Accounts, Tasks, Events, Opportunities, Cases, and custom objects
should use the same raw-event and hydration pattern, but they do not all need
the same latency.

Recommended split:

- **Live now:** `Lead.created` for speed-to-lead.
- **Near real-time next:** important Contact/Account changes that alter call
  context or ownership.
- **Scheduled/reconciled:** Tasks, Events, Opportunities, Cases, and historical
  backfill unless a workflow proves they need seconds-level latency.

Every Salesforce CDC subscriber must store replay cursor state and run a
scheduled reconciliation query by `SystemModstamp` to recover from gaps.

## CareStack

CareStack starts as read-only scheduled sync unless a specific endpoint proves
it needs faster handling.

The CareStack path is:

```text
CareStack sync API result
-> ingest.raw_event
-> canonical projection
-> semantic event
```

CareStack Patient data is PHI-sensitive and must enter `phi` only through
`PhiService`. Operationally safe summaries can be projected into `ops` or
`interaction`, but raw clinical context must not leak into ops dashboards,
agent prompts, or logs.

## Context Is the Agent Interface

Agents must not reason directly over raw Salesforce or CareStack schemas.

Context architecture and semantic interpretation rules live in:

- `docs/architecture/CONTEXT_ARCHITECTURE.md`
- `docs/architecture/SEMANTIC_INTERPRETATION.md`
- `docs/governance/TAXONOMY_GOVERNANCE.md`

They receive stable context objects such as:

- `speed_to_lead_context`
- `person_timeline`
- `lead_operational_context`
- `consultation_context`
- `workflow_context`

Context objects can include interpreted values such as:

- lead source
- UTM campaign/source/medium/content/term
- treatment intent
- financing signal
- location/market
- preferred language
- contactability
- urgency
- attribution confidence

The semantic mapping must be versioned when it becomes operationally important.
Agents may propose new labels or strategy changes, but production taxonomy and
workflow-changing strategies require human approval before rollout.

## Runtime Implications

Seconds-level Salesforce ingestion requires a runtime decision separate from
normal scheduled sync.

Allowed early implementation options:

1. **Dedicated live-intake runtime:** a narrow Salesforce subscriber for
   `LeadChangeEvent`, deployed separately from the general worker.
2. **Salesforce outbound HTTP path:** Flow/Apex sends a create notification to a
   Fusion API endpoint, which then hydrates the Lead.
3. **Fusion-first form path:** landing pages submit to Fusion first, Fusion
   acts immediately, then writes to Salesforce. This is preferred when Fusion
   controls the form.

Do not reintroduce the generic `fusion-worker` Cloud Run Service as a catch-all
long-running process. Live intake needs its own explicit runtime, health,
preflight, cursor, replay, and smoke checks.

## Tenant-Owned Credentials

Provider credentials are company settings, not deploy-time production env vars.

Salesforce, CareStack, Twilio, HubSpot, mailbox, payment, and AI vendor
credentials must be managed per tenant through the Settings / Integrations UI
and stored in `tenant.integration_credential`.

The expected flow is:

```text
operator opens Settings / Integrations
-> enters or connects provider credentials
-> backend validates/test-connects
-> backend encrypts payload
-> tenant.integration_credential row is upserted
-> audit row is written
-> UI receives metadata only
```

Provider jobs and agents resolve credentials by `tenant_id`:

```text
tenant_id
-> IntegrationCredentialService.read_for(...)
-> provider client
-> raw event / action
-> audit
```

Environment variables for provider credentials are allowed only as temporary
bootstrap/local-dev fallbacks. Production should not depend on operators moving
company keys from local `.env` into Cloud Run.

## Reconciliation

Live ingestion must be paired with reconciliation.

If a subscriber is down, replay retention expires, credentials fail, or a
payload cannot be processed, the system must recover through scheduled pulls.

Minimum reconciliation for Salesforce:

- Query recently created/updated Leads by `SystemModstamp`.
- Compare against `integrations` cursor/state and canonical lead records.
- Backfill missing raw snapshots and canonical projections.
- Emit audit and sync_run summaries.

## Audit and Safety

Every provider ingestion batch or live event must leave audit evidence:

- provider
- object type
- external id
- event type
- replay/cursor id when available
- sync_run id when available
- canonical entity ids created/updated
- workflow trigger id when applicable

Logs must never contain raw payload bodies, tokens, PHI, patient names, DOB,
phone numbers, email addresses, clinical notes, or full DSNs.

## Planning Consequences

Deploy stabilization remains the first dependency. After that, the earliest
provider work should be:

1. Company Settings / Integrations credential UI backed by
   `tenant.integration_credential`.
2. Speed-to-lead live intake for Salesforce Lead creation.
3. Read-only Salesforce/CareStack scheduled sync for broader context.
4. Semantic context builders for agent workflows.
5. Runtime ADR for any long-running subscriber or worker model.
6. Write-back to providers only after workflow controls and audit are ready.
