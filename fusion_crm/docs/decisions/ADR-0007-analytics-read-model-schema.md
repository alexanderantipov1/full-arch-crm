# ADR-0007: `analytics` read-model schema + `fact_patient_journey`

**Status:** Accepted
**Date:** 2026-06-18
**Authors:** Claude Code (B0 Foundation worker), per operator decision (2026-06-17)
**Workstreams affected:** backend
**Related Linear issues:** ENG-504 (epic), ENG-505, ENG-506, ENG-507

---

## Context

The Revenue Intelligence Analytics Platform (epic ENG-504, `market.md` spec)
must trace every patient from ad spend → collected revenue across 14 analytics
pages, with global filters (date range, location, campaign, source, vendor,
caller, coordinator, doctor) and derived metrics (cost/revenue per stage, ROI,
conversion ratios).

Computing these read-time over the canonical schemas (`identity`, `ops`,
`interaction`, `attribution`, `marketing`) for every page would mean repeating
the same person-anchored funnel joins, Net-Collected revenue logic (ENG-283),
and person-anchored dating (ENG-481) in many places — drift-prone and slow.

The existing canonical-domain invariants forbid provider-specific tables and
keep `identity`/`ops`/`phi` as the only truth for people. A precomputed,
denormalised fact table does not fit any existing domain schema, and putting a
write-heavy analytics projection inside a canonical schema would blur the
source-of-truth boundary.

Some journey fields (caller/coordinator/doctor, treatment_accepted, surgery_*,
marketing_cost) have no canonical signal yet; the operator decided they must
ship now as nullable with provenance, filled later by an auto-resolver or manual
enrichment — without blocking the foundation.

## Decision

Add a **ninth-tier operator-approved schema `analytics`** that holds the
read-model layer. Its first table is `analytics.fact_patient_journey`
(`packages/analytics/models.py`), one row per `person_uid`:

- **Rebuildable projection, never a source of truth.** Every row is derived from
  the canonical schemas by the fact builder (ENG-506) and may be dropped and
  rebuilt. Nothing writes to `analytics.*` except the builder service.
- **Every column is nullable except the `person_uid` UUID primary key.** No
  cross-domain Python FK — `person_uid`, `location_id`, `campaign_id`,
  `vendor_id`, `caller_id`, `coordinator_id`, `doctor_id` are plain UUID columns
  (invariants #2/#3).
- **`location_id`** (plain UUID → `tenant.location.id`) is added beyond the
  `market.md` column list so analytics can aggregate (default) or filter
  per-location.
- **`field_provenance`** (JSONB, NOT NULL, default `'{}'`) records per field
  `{source, method: auto|manual|unresolved, confidence, resolved_at}`. The
  precedence is `manual > auto > unresolved`; a rebuild never clobbers a manual
  value (`packages/analytics/provenance.py`). Fields with no signal ship NULL
  with `method='unresolved'`.

Schema registration: `analytics` is added to `packages/db/alembic/env.py`
`DOMAIN_SCHEMAS`, the model import is added to `packages/db/registry.py`, and the
schema is created in-migration via `CREATE SCHEMA IF NOT EXISTS analytics`
(revision `b1c2d3e4f5a6`, chained on `f6a7b8c9d0e1`). Root `CLAUDE.md` invariant
#1 records the schema as an operator-approved read-model layer.

`packages/analytics` keeps its existing catalog-review contracts; the fact
read-model is additive within the same package.

## Consequences

### What this enables

- A single typed fact table the 14 pages, chat answers, and agent tools read,
  so metric definitions live once (ENG-507 derived metrics over fact +
  `marketing.*`).
- Missing fields ship now (nullable + provenance) and get filled later (B1.*)
  without a contract change or migration.
- Fast page reads: stage timestamps and money are precomputed, not re-joined per
  request.

### What this costs

- A refresh job (ENG-506, gated OFF by default in prod) must keep the projection
  current; staleness is possible between refreshes.
- One more schema to operate, back up, and reason about.

### Risks / open questions

- `infra/docker/init-schemas.sql` is owned by infra and was **not** edited by
  this worker (forbidden path). The migration's `CREATE SCHEMA IF NOT EXISTS`
  makes fresh/scratch upgrades self-contained, but the operator should add
  `CREATE SCHEMA IF NOT EXISTS analytics;` to `init-schemas.sql` for consistency
  with the other schemas.
- CareStack treatment-accepted / surgery signal (ENG-511) and the marketing cost
  basis (ENG-522) are still open; those fields stay `unresolved` until decided.

## Alternatives considered

### Option A: Compute everything read-time over canonical schemas

- **Approach:** No fact table; each page joins `ops`/`interaction`/`attribution`/
  `marketing` on demand.
- **Pros:** No projection to maintain; always fresh.
- **Cons:** Same complex joins + Net-Collected/person-anchored logic duplicated
  per page; slow; high drift risk.
- **Why rejected:** Violates "metric definitions live once"; would not scale to
  14 pages.

### Option B: Put the fact table inside an existing schema (e.g. `ops` or `marketing`)

- **Approach:** Add `fact_patient_journey` to a canonical schema.
- **Pros:** No new schema.
- **Cons:** Blurs source-of-truth vs derived-projection boundary; a write-heavy
  rebuildable table next to canonical truth invites accidental reads of the
  projection as truth.
- **Why rejected:** The read-model must be visibly separable and droppable; a
  dedicated schema makes "never a source of truth" enforceable.

## References

- Linear issue(s): ENG-504, ENG-505, ENG-506, ENG-507
- Related ADRs: ADR-0003 (multi-tenancy), ADR-0005 (full-fidelity ingestion)
- Source whitepapers / docs: `market.md`, `docs/analytics/full-funnel-v2-person-anchored.md`
- External references: none
