# Full-Fidelity Ingestion Doctrine

## Purpose

This doctrine defines how Fusion CRM captures data from every external source
system — Salesforce, future CRMs, CareStack, and any other clinical or
operational system. It is the companion to
`PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`: that doctrine governs how raw
evidence becomes governed *meaning*; this one governs the *completeness* of the
raw evidence itself.

The rule it establishes is deliberately strong and source-agnostic:

```text
When we pull ANY object from ANY external system — lead, contact, event, task,
appointment, invoice, payment, patient, or any future object — we capture 100%
of the fields that exist on that object at pull time. When the source adds new
fields, we still capture 100%, automatically. Our raw store becomes the complete
forensic copy of the source object, so that a later need for any field is served
from our own raw data — never by going back to interrogate the source system.
```

This includes clinical / PHI data. Our database is closed to end users; access
is governed separately by the policies in
`PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md` (data-class boundaries, gated
surfaces, audited PHI lanes). Full-fidelity capture does not weaken those
boundaries — it strengthens the case for keeping raw access gated, because raw
now holds everything.

## Core Principle: Completeness At Raw, Curation At Domain

The single idea that makes this affordable ("control everything without
straining the system"):

```text
Full fidelity lives at the RAW layer only.
Domain mapping stays CURATED and on-demand.
```

- `ingest.raw_event.payload` must contain every field the source object exposes.
- The domain projections (`ops.lead.extra`, `interaction.event`, future
  `phi`/`billing` tables) continue to map only the fields the product needs
  today.
- A newly appeared source field automatically lands in raw, but does **not**
  automatically require a domain model change. We model it the day a product
  feature needs it, reading historical values back out of raw.

This decoupling is what lets us "get everything, always" without modelling
everything.

## Current Position

The building blocks exist, but the capture is not full-fidelity:

- `ingest.raw_event` stores provider payloads verbatim — but "verbatim" today
  means verbatim of what we *requested*, not the full object.
- **Salesforce**: SOQL has no `SELECT *`. Each object service
  (`sf_lead_service.py`, `sf_account_service.py`, `sf_opportunity_service.py`,
  `sf_event_service.py`, `sf_task_service.py`, `sf_case_service.py`,
  `sf_contact_service.py`, `sf_opportunity_history_service.py`) carries a
  hand-maintained static field projection (`_SF_LEAD_PROJECTION` and siblings,
  ~40 fields each). Any field not listed is absent from raw permanently.
  Example: `CreatedById` (who created the lead) and most standard/custom fields
  are never captured; only `CreatedDate` rides along.
- **CareStack / REST**: REST endpoints generally return the full object body and
  we capture it verbatim, so completeness is closer — but it is uncontrolled. We
  do not request available sub-resources/expansions deliberately, and we do not
  track the observed schema, so field drift is invisible.
- There is no schema registry: we cannot answer "what fields does this object
  have, and which ones are we missing?" without going back to the source system
  — exactly the dependency this doctrine removes.

## Doctrine

### 1. Capture Is Complete By Construction

Every source object is captured with all of its currently-existing fields. The
field list is **derived from the source**, never hand-maintained:

- **Salesforce**: build the SOQL projection dynamically from the object
  `describe`. Select every queryable scalar field (skip non-queryable, base64,
  and compound-parent fields whose components are selected individually). Cache
  the field list plus a content hash; refresh on a low cadence, not per pull.
- **REST sources (CareStack, future)**: never restrict fields (no sparse
  `fields=` parameters); request the full object plus the deliberately-chosen
  expansions; capture the entire response body verbatim.

Static, hand-written field lists are prohibited for full-fidelity objects.

### 2. The Source Schema Is Known And Recorded

We must always be able to answer "what fields exist on this object" from our own
store. A schema registry records, per `(provider, object, field)`:

```text
field api name, type, queryable/readable flag,
first_seen_at, last_seen_at, active
```

It is populated from `describe` (Salesforce) and from the union of observed
payload keys (REST). This registry is the durable answer to "what fields are
there" and the input to drift detection.

### 3. New Fields Are Detected And Absorbed Automatically

A low-frequency schema-refresh job re-derives the field set and diffs it against
the registry:

- **new field** → recorded, logged as a structured drift event, and
  automatically included in the next pull (the projection is dynamic, so no code
  change is needed for Salesforce);
- **removed / type-changed field** → recorded and logged;
- the job is cheap (one `describe` per object per refresh, or key-union over
  rows already captured) so "control" does not mean "strain".

Drift events are visible operational signals, not silent.

### 4. Visibility Of What We Cannot See

For Salesforce, the ordinary `describe` is filtered by the integration user's
Field-Level Security: a field the integration user cannot read does not appear,
so a naive describe-projection silently under-captures. To make the blind spot
visible, the full field list is read from the **Tooling API**
(`EntityDefinition` / `FieldDefinition`, or `/tooling/sobjects/<Object>/describe`)
which is not FLS-filtered, and compared against the FLS-filtered describe. The
difference is the precise list of fields blocked by FLS — surfaced so a
Salesforce admin can be given an exact remediation list instead of "open
everything".

### 5. Raw Is The Source Of Truth For Fields

Because capture is complete, a later need for any field is served from
`ingest.raw_event` — replay/backfill from raw, never a fresh interrogation of
the source system for "a field we forgot". This is the payoff of the doctrine
and the reason completeness is worth its storage cost.

### 6. Full Fidelity Includes PHI, Under The Existing Boundaries

Clinical and PHI-adjacent fields are captured in full at the raw layer. This
does not change the access model in
`PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`:

- raw payloads remain out of production dashboards, agent prompts, logs, and
  tool responses except through explicitly gated surfaces;
- access is governed by data-class boundaries, server-side permission checks,
  and audit;
- "our database is closed to users; access is organized separately by rules"
  is the operating assumption that justifies storing everything in raw.

Completeness raises, not lowers, the bar for guarding raw.

### 7. Completeness Is Verified, Not Assumed

Each full-fidelity object must have a check that asserts the captured field set
equals the source's currently-readable field set (within the FLS reality of
principle 4). A regression that silently narrows capture must fail
verification, the same way a contract drift would.

## Source Mechanics

### Salesforce

- Add `describe` and Tooling-API field-listing to the Salesforce client (today
  it supports only get-by-id and pre-built SOQL `query`).
- A projection builder turns a cached describe into an all-queryable-fields
  SELECT per object.
- Compound fields (Address, Geolocation) are captured via their components;
  non-queryable and base64 fields are skipped by design and recorded as such.
- Relationship/name expansion (e.g. `Owner.Name`, `CreatedBy.Name`) is a
  deliberate, minimal add-on: the object's own scalar foreign keys (all `*Id`
  fields) are always captured; human-readable names come from ingesting the
  related object (e.g. `User`) rather than from wide relationship traversal.
- SOQL length and governor limits are not a concern for all-field selects on
  these objects.

### CareStack And Future REST / Medical Systems

- Audit each endpoint to confirm we request the full object and the right
  expansions, and never apply field filters.
- Snapshot the observed key-set into the schema registry so REST drift is as
  visible as Salesforce drift.
- Preserve nested structures exactly; do not flatten or drop sub-objects on
  capture.

## Backfill Policy (resolved)

- **Salesforce**: after the dynamic projection lands, re-pull history so that
  past raw rows gain the now-captured fields. Initial scope: **all of 2026
  year-to-date**; earlier history revisited later if needed. The re-pull is by
  Id and rides the existing idempotent upsert path.
- **CareStack**: **forward-only** for now — new captures get full fidelity;
  historical re-pull is deferred and revisited later.
- Old raw rows are immutable evidence; backfill writes new raw rows / updated
  captures rather than mutating historical payloads in place.

## Salesforce Admin Prerequisites

Achieving true 100% requires source-side configuration, because Salesforce only
returns what the integration user is permitted to see. This is a configuration
prerequisite, **not a code blocker** — the code can be built first, and
principle 4's FLS-gap detector produces the exact list the admin needs.

A dedicated **Integration Permission Set** (or Permission Set Group) assigned to
the integration user should grant:

1. **Field-Level Security: Read on all fields** of every ingested object
   (Lead, Contact, Account, Opportunity, Event, Task, Case, OpportunityHistory,
   User, and any future object), including all custom `__c` fields.
2. **Object-level Read + "View All"** on each ingested object (or the system
   "View All Data" permission) so sharing rules do not hide records.
3. **"API Enabled"** (already in place).
4. A maintained process for **new fields**: by default a newly created custom
   field is FLS-visible only to System Administrator, so it will not appear for
   the integration user automatically. Either the admin sets the new field's FLS
   visible to the Integration Permission Set at creation time, or a periodic FLS
   sync keeps the permission set complete. Until then, the field exists in
   Salesforce but is invisible to our describe — caught and reported by the
   FLS-gap detector, not silently lost.

Timing: not required to start implementation; required to actually reach 100%.
The FLS-gap detector turns "is it needed yet" into a concrete, monitorable list.

## Proposed Task Block

A universal, provider-agnostic capture framework is the chosen scope (not a
Salesforce-only first cut). Suggested decomposition:

### Block A: Capture Contract And Schema Registry

- Define a provider-agnostic full-fidelity capture contract (what "complete"
  means per source class: describe-driven vs response-verbatim).
- Add the schema registry table and service (`provider, object, field, type,
  readable, first_seen, last_seen, active`).
- Define the drift event shape and where it surfaces.

### Block B: Salesforce Dynamic Projection

- Add `describe` + Tooling-API field listing to the Salesforce client.
- Build the dynamic all-queryable-fields projection; replace every static
  `_SF_*_PROJECTION` with it.
- Implement the FLS-gap detector (Tooling vs describe) and its report.
- Add completeness verification per object.

### Block C: Schema-Refresh And Drift Job

- Low-cadence job that re-derives schemas, updates the registry, emits drift
  events, and (Salesforce) absorbs new fields into the next pull automatically.

### Block D: CareStack / REST Full-Fidelity Audit

- Audit endpoints for field restriction and missing expansions.
- Add observed-key schema snapshotting to the registry.
- Confirm verbatim nested capture.

### Block E: Salesforce History Backfill (2026 YTD)

- Re-pull 2026-year-to-date Salesforce objects through the dynamic projection so
  history reaches full fidelity, via the idempotent upsert path.

### Block F: Governance And Docs

- ADR recording this doctrine as an architectural invariant.
- Update root `CLAUDE.md` invariants and `packages/ingest/CLAUDE.md`.
- Reaffirm raw-access gating and PHI boundaries under full fidelity.

## Decisions

Resolved:

1. Scope is a **universal, provider-agnostic framework** (SF + CareStack under
   one mechanism), not a single-source first cut.
2. Salesforce backfill scope is **2026 year-to-date**; CareStack is
   **forward-only** for now.
3. Full fidelity **includes PHI**, under the existing data-class and access
   boundaries.

Still needed:

1. Salesforce admin commitment to the Integration Permission Set (timing and
   ownership of the FLS process).
2. Storage-growth posture: all-field raw payloads grow `ingest.raw_event`;
   confirm monitoring / retention expectations for the larger JSONB volume.
3. Whether the schema registry lives in `ingest` or a small dedicated module.
4. Drift event surfacing target (logs only, incident file, Linear, or
   dashboard).

## Recommended Next Move

Promote a candidate mission — working name **Full-Fidelity Ingestion
Framework** — to the Orchestrator. The Orchestrator validates scope, creates or
links the Linear epic and per-block issues, defines ownership, and runs
execution to completion. This document is the strategy artifact; execution
starts only after the Orchestrator accepts the handoff and the Linear issues
exist.
