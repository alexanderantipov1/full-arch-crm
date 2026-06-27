# Revenue Intelligence Analytics Platform — Strategy Plan

Status: handed off to Orchestrator (2026-06-17)
Linear epic: ENG-504 — project "Revenue Intelligence Analytics Platform V1"
Source spec: `market.md` (Revenue Intelligence Analytics Platform v1.0)
Mission folder: `.agents/orchestration/revenue-intelligence-analytics-v1/`

This plan maps the manager-provided `market.md` analytics specification onto
Fusion CRM's existing architecture. It records what already exists, what is
missing, the operator decisions taken, and the decomposition handed to the
Orchestrator. It is a strategy artifact — no product code, no worker launch.

## Business goal

Build a unified Revenue Intelligence Platform that traces the full lifecycle of
every patient from advertising spend to collected revenue, functioning as an
executive operating system for the clinic rather than a CRM reporting module.
Leadership must instantly answer: which campaigns/vendors drive revenue & ROI;
which caller books most consults; which coordinator converts most surgeries;
which doctor produces most revenue; where patients are lost; the true cost per
funnel stage; the revenue contribution of every employee; and where to invest
budget — sliced **aggregate and per-location**.

## What already exists (do not rebuild)

- **5 analytics pages live:** Calls, Sales Pipeline, Marketing, SEO, Full Funnel
  (`apps/web/app/(staff)/analytics/*`), backed by `apps/api/routers/dashboard.py`
  and `packages/analytics/`.
- **Multi-location data already present:** `tenant.location`,
  `ops.consultation.location_id`, CareStack location id. Analytics endpoints do
  **not** yet expose a location filter (only the PM dashboard does). So
  "aggregate + per-location" is a wiring task, not a data task.
- **Money metrics exist:** gross/collected revenue and first-payment date via
  CareStack accounting transactions, with the Net-Collected formula that excludes
  the `payment_applied` allocation leg (ENG-283).
- **Attribution schema exists:** `attribution.*` (vendor/channel/campaign/
  mapping_rule); resolver in progress (ENG-446/448).
- **Person-anchored funnel dating exists:** Full-Funnel v2 dates persons by real
  activity, not bulk-import date (ENG-481) — reused so the ~27k purchased
  CareStack base does not distort cohorts.

## What is missing relative to `market.md`

- **`fact_patient_journey`** — the one-row-per-patient fact table. Does not exist.
  It is the foundation for all 14 pages.
- **9 of 14 pages:** Executive Overview, Vendor, Caller, Coordinator, Doctor,
  Revenue Intelligence, Cost Intelligence, Patient Journey, Bottleneck Detection,
  Attribution, Cohort, Revenue Influence Matrix (Funnel + Marketing partially
  exist and get extended).
- **Fact fields not yet derivable from data today:**
  - `caller_id` (SF Lead Owner / `CreatedBy.Id`) — captured raw, not resolved to actor.
  - `coordinator_id` (SF Opportunity Owner) — in `opportunity.extra`, not resolved.
  - `doctor_id` (CareStack provider) — directory exists, no actor link.
  - `treatment_accepted_date` — no standardized CareStack "accepted" state.
  - `surgery_scheduled_date` / `surgery_completed_date` — no surgery classification.
  - `marketing_cost_allocated` — spend ingested (Google Ads), no per-lead allocation.
- **CSV/Excel export + drill-down** — flagged (`export_available`) but unimplemented.

## Operator decisions (2026-06-17)

1. **New `analytics` PostgreSQL schema** hosts `fact_patient_journey` and future
   aggregate read-models. This is an approved addition to architectural
   invariant #1 (the canonical-DB schema set). The schema is a **rebuildable
   projection** of canonical domains — never a source of truth, never written to
   except by the fact builder.
2. **Full epic** — all 14 pages + foundation + export delivered under one project.
3. **Missing fields are nullable + two fill paths.** Every dimension/date column
   ships nullable with per-field provenance (source system, method =
   `auto` | `manual` | `unresolved`, confidence, resolved_at). Fields not yet
   derivable ship NULL with method `unresolved` and never block the build. They
   are filled later by (a) automatic resolvers or (b) manual operator enrichment;
   manual overrides win over auto and survive a fact rebuild. The UI shows an
   honest "no data" state until a field resolves.

## Architecture constraints (must hold)

- Read-only staff surface; dev-phase full-visibility (PHI/PII may render; **logs
  stay PHI-free**; **no raw provider payloads** in responses or exports).
- Person spine: `identity.person.id` is `person_uid`; fact rows are person-anchored.
- Analytics business logic lives in `packages/analytics` and is composed in
  `apps/api` (no business logic in routes — invariant #5).
- Agents never touch the DB; any future AI analytics reads through services/tools
  (invariant #6).
- Raw payloads stay in `ingest.raw_event` (full-fidelity, invariant #11).
- Migrations are immutable once shipped; new schema = new Alembic revision,
  chained in one branch per solo-dev policy.

## Decomposition (handed to Orchestrator as ENG-504 children)

- **B0 Foundation** — ENG-505 (`analytics` schema + `fact_patient_journey` +
  provenance), ENG-506 (fact builder/refresh job, person-anchored), ENG-507
  (derived metrics + global filter/time-range contract incl. location), ENG-508
  (CSV/Excel export + drill-down).
- **B1 Missing-field enablement** — ENG-509 (caller+coordinator → actor),
  ENG-510 (doctor → actor), ENG-511 (treatment-accepted + surgery stages),
  ENG-512 (marketing-cost allocation), ENG-513 (manual enrichment path).
- **B2 Pages (14)** — ENG-514..ENG-527 (Executive, Funnel, Marketing, Vendor,
  Caller, Coordinator, Doctor, Revenue, Cost, Patient Journey, Bottleneck,
  Attribution, Cohort, Revenue Influence Matrix).
- **B3 Closeout** — ENG-528 (future AI-analytics hooks), ENG-529 (verification +
  real-data validation + cross-runtime review).

## Sequencing

B0 first (foundation gates everything). B1 may run in parallel with B0 where
ownership is disjoint. Each B2 page depends on B0 (fact + filters + metrics) and,
for its specific dimension, on the relevant B1 enablement (e.g. Caller page needs
B1.1). Pages whose data is not yet resolved still ship, rendering "no data".
B3 last.

## Risks

- **Treatment-accepted / surgery classification (ENG-511)** is the riskiest data
  gap — CareStack may have no reliable "accepted" signal. Discovery-gated; flag
  `Needs decision:` rather than guessing a mapping.
- **Operational cost basis (ENG-522)** — "cost per caller/coordinator conversion"
  needs a staff-cost input the system does not hold; decision-gated.
- **Attribution maturity** caps Vendor/Campaign/Ad-Set/Marketing-cost richness;
  unresolved dimensions must be shown as "Unattributed", never silently dropped.
- **New schema scope creep** — `analytics` must stay a rebuildable read-model, not
  a second source of truth.
- **Number drift** — new pages must reconcile with existing Funnel/PM dashboards
  on real data before merge (house rule: verify with real data before merge).

## Human decisions still open

1. Treatment-plan **acceptance** semantics + **surgery** classification source
   (ENG-511) — operator + CareStack docs.
2. **Operational cost basis** for cost-per-conversion metrics (ENG-522).
3. Provenance **precedence** confirmation (manual > auto > unresolved) — proposed,
   needs operator OK (ENG-513).
4. Whether Marketing Performance (ENG-516) **extends** the existing Marketing page
   or is a new route.
