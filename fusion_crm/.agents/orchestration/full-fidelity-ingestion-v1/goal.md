# Goal — full-fidelity-ingestion-v1

Establish a universal, provider-agnostic data-capture invariant: when we pull any
object from any external system (Salesforce, future CRMs, CareStack, other
clinical systems), we capture 100% of the fields that exist on that object at
pull time, and absorb newly-added fields automatically. `ingest.raw_event`
becomes the complete forensic copy of the source object, so a later need for any
field is served from our own raw data — never by re-interrogating the source.

Strategy artifact: `.agents/strategy/FULL_FIDELITY_INGESTION_DOCTRINE.md`.
Linear epic: ENG-425 (blocks ENG-426..ENG-431).

## Core principle

Completeness lives at the RAW layer only; domain mapping stays curated and
on-demand. A new source field lands in raw automatically but does not force a
domain model change until a feature needs it.

## Resolved decisions

1. Universal provider-agnostic framework (SF + CareStack under one mechanism).
2. Salesforce backfill = 2026 year-to-date; CareStack = forward-only for now.
3. Full fidelity includes PHI, under existing data-class/access boundaries.
4. Schema registry lives in `ingest`; drift surfaces via structured log +
   `sync_run.meta`.

## Out of scope

- Auto-modelling new fields into domain projections.
- CareStack historical re-pull.
- Salesforce admin FLS configuration (external prerequisite; the FLS-gap
  detector produces the remediation list).
