# Workflow-Ready Timeline

This document describes how provider evidence becomes safe, workflow-ready
`interaction.event` rows for a person's operational timeline.

Strategic context:

- `.agents/strategy/RAW_TO_CONTEXT_NORMALIZATION_SPEC.md`
- `.agents/strategy/PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`

## Layer Model

Workflow-ready ingest follows the raw-to-context layering model:

```text
Salesforce / CareStack provider rows
  -> ingest.raw_event
  -> identity resolution and source-link provenance
  -> canonical projection in ops / phi / integrations.external_entity
  -> interaction.event
  -> GET /persons/{uid}/operational-timeline
```

The timeline is not a raw provider browser. It is an append-only semantic
surface that preserves source references while exposing only the minimum
fields needed for operational workflow, review, and future context assembly.

## Layer 0: Raw Evidence

Every provider row is captured first as `ingest.raw_event` with the verbatim
payload:

- Salesforce Lead uses `source='salesforce'`, `event_type='lead.pull'`.
- Salesforce Event uses `source='salesforce'`,
  `event_type='salesforce.event.upsert'`.
- Salesforce Task uses `source='salesforce'`,
  `event_type='salesforce.task.upsert'`.
- CareStack Patient uses `source='carestack'`,
  `event_type='carestack.patient.upsert'`.
- CareStack Appointment uses `source='carestack'`,
  `event_type='carestack.appointment.upsert'`.

Raw payloads may contain PHI or provider-specific fields whose meaning is not
yet governed. They stay in `ingest.raw_event` for replay, audit, debugging, and
future reinterpretation. Product UI, workflow agents, and operational timeline
reads must not treat raw payloads as context.

## Layer 1: Identity And Provenance

Provider person-like rows resolve to the canonical person graph before they
become workflow events.

The ingest handlers capture narrow `ingest.normalized_person_hint` rows for
matching signals and then call identity services. Provider provenance is kept
as source-link evidence rather than provider-shaped domain tables.

Common source kinds include:

- `lead` for Salesforce Lead identity hints;
- `patient` for CareStack Patient identity hints;
- provider object kinds such as Salesforce Event, Salesforce Task, and
  CareStack Appointment when they are emitted as timeline event sources.

This keeps `identity.person.id` as the single `person_uid` used by downstream
domains.

## Layer 2: Canonical Projections

After identity resolution, stable business meaning is projected into canonical
schemas:

| Provider object | Projection |
|---|---|
| Salesforce Lead | `ops.lead` |
| Salesforce Event | `ops.consultation` when it represents a consultation |
| Salesforce Task | `ops.followup_task` for actionable tasks; `interaction.event` for call/history events |
| CareStack Patient | identity/source-link evidence, and PHI projections only through `PhiService` when authorized |
| CareStack Appointment | `ops.consultation` |

Provider payloads still remain the evidence source. Projections keep only the
stable, product-facing fields needed by the CRM.

## Layer 3: Timeline Events

Workflow-ready handlers append `interaction.event` rows for person timeline
semantics. Each event carries:

- `person_uid`;
- `kind`;
- `source_provider`;
- `source_event_id` pointing back to `ingest.raw_event.id`;
- `data_class`;
- `source_kind`;
- `source_external_id`;
- optional `projection_ref_type` and `projection_ref_id`;
- `review_status`;
- `occurred_at`;
- no-PII `summary`;
- no-PII structured `payload`.

Current workflow-ready event kinds are:

- `lead_created`
- `lead_updated`
- `consultation_scheduled`
- `consultation_rescheduled`
- `consultation_cancelled`
- `consultation_completed`
- `consultation_no_show`
- `task_created`
- `task_completed`
- `call_logged`
- `call_reference_found`

The `consultation_timeline.py` helper centralises consultation status mapping
so Salesforce Event and CareStack Appointment rows produce the same event
vocabulary. `call_reference.py` centralises safe call/meeting reference
detection; it records pointers only and never fetches recordings or meeting
content.

## Layer 4: Operational Timeline Read Surface

The operational read surface is:

```text
GET /persons/{uid}/operational-timeline
```

That endpoint reads normalized `interaction.event` rows and returns safe
timeline entries with optional allowlisted projection snapshots. It does not
return `ingest.raw_event.payload`, provider notes, clinical text, names,
emails, phones, DOB, addresses, transcripts, recordings, or arbitrary provider
metadata.

The endpoint is the forward-compatible surface for workflow agents and operator
UI because it is already shaped around data class, review status, source
reference, and projection reference. Future context packs should build from
this service layer and governed context facts, not direct raw-event queries.

## Review And Promotion

Timeline events can be emitted automatically when the handler has deterministic
meaning, or marked for review when the evidence is only a pointer or needs
human interpretation. Promotion from raw evidence to workflow context must keep
the source reference intact and must preserve the PHI boundary:

- raw evidence remains replayable in `ingest.raw_event`;
- PHI-bearing data stays behind `PhiService`;
- operational projections stay PHI-free;
- timeline summaries and payloads remain no-PII;
- ambiguous semantic labels use `review_status` before becoming workflow
  automation input.
