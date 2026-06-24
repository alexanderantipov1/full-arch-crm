# ADR-0005: Full-fidelity ingestion

**Status:** Accepted
**Date:** 2026-06-14
**Authors:** Claude Code
**Workstreams affected:** backend
**Related Linear issues:** ENG-425 (epic), ENG-426, ENG-427, ENG-428, ENG-429, ENG-430

---

## Context

When we pull an object from an external system we historically captured only a
hand-maintained subset of its fields. Salesforce SOQL has no `SELECT *`, so each
ingest service carried a static `_SF_*` projection of ~7–45 fields. On the real
Lead object that was ~19% of the 240 readable fields — `CreatedById`,
`CampaignId`, and most standard/custom fields were never captured, and the only
way to answer "what fields exist and which are we missing?" was to interrogate
the source system again.

This violates the purpose of `ingest.raw_event` as the forensic copy of inbound
data: a later need for a field could not be served from our own store. The
clinic's data also includes PHI; the database is closed to end users and access
is governed separately, so storing everything in raw is consistent with the
access model rather than at odds with it.

Strategy artifact: `.agents/strategy/FULL_FIDELITY_INGESTION_DOCTRINE.md`.

## Decision

**Every external object is captured with 100% of the fields it exposes at pull
time, and newly-added fields are absorbed automatically. Completeness lives at
the RAW layer only; domain mapping stays curated and on-demand.**

In force (grep-verifiable):

- **Schema registry** — `ingest.source_object_field`
  (`packages/ingest/models.py`) records, per `(provider, object, field)`: type,
  `readable`, `active`, first/last seen. `IngestService.sync_object_schema`
  reconciles an observed schema and returns the drift shape (`SchemaDiffOut`).
- **Salesforce** — the SOQL projection is built dynamically from `describe`
  (`SfClient.describe`) for every object via `SfSchemaSync`
  (`packages/ingest/sf_schema_sync.py`); the static `_SF_*` projections remain
  only as a fallback. The Tooling API (`SfClient.describe_tooling_fields`,
  not FLS-filtered) vs `describe` diff yields the FLS-gap — the exact list of
  fields the integration user cannot read.
- **CareStack / REST** — the client applies no field filter (only
  `continueToken` / `modifiedSince`), so objects are captured verbatim in full;
  `IngestService.snapshot_observed_schema` records the schema from the union of
  observed payload keys.
- **Drift detection** — daily arq cron
  (`refresh_salesforce_schemas_for_*`, `refresh_carestack_schemas_for_*`)
  re-derives schemas, records drift + FLS gaps into `sync_run.meta`, and
  absorbs new fields into the next pull automatically (the projection is
  registry-derived).
- **History backfill** — `infra/scripts/backfill_sf_full_fidelity.py`
  force re-captures a window through the dynamic projection so old raw rows gain
  the wide field set.

The registry stores field NAMES and JSON types only, never values — so PHI
field names (`ssn`, `dob`) are schema metadata, not PHI.

## Consequences

### What this enables

- A field needed later is served from `ingest.raw_event` — never a fresh
  interrogation of the source system.
- "What fields exist / which are we missing?" is answerable from our own store;
  the FLS-gap report tells the Salesforce admin exactly what to open.
- New source fields are captured with no code change.

### What this costs

- Larger `raw_event` payloads (e.g. Lead 45 → 240 fields) → JSONB growth.
  Monitor table size, especially around a full backfill.
- A daily describe + Tooling query per Salesforce object (cheap, low cadence).

### Risks / open questions

- Achieving true 100% on Salesforce requires the integration user to have
  Field-Level-Security read on all fields (a source-side admin task); until
  then the FLS-gap detector reports the shortfall rather than silently losing
  fields.
- Observed-key snapshots record top-level keys only; nested-path flattening is
  a future enhancement.

## Alternatives considered

### Option A: Keep hand-maintained projections, add fields on demand

- **Approach:** widen the static `_SF_*` lists when a feature needs a field.
- **Why rejected:** perpetual catch-up; history can never be widened for a
  field we did not think to add at capture time; no answer to "what's missing".

### Option B: Mirror full source schema into domain tables

- **Approach:** model every field into typed domain columns.
- **Why rejected:** enormous modelling cost and churn for fields no feature
  uses. Completeness belongs at the raw layer; the domain stays curated.

## References

- Linear: ENG-425 (epic) + ENG-426..ENG-430
- Strategy: `.agents/strategy/FULL_FIDELITY_INGESTION_DOCTRINE.md`
- Related doctrine: `.agents/strategy/PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`
- Related ADRs: none
