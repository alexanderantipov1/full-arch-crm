# Mission Goal — revenue-intelligence-analytics-v1 (ENG-504)

Build a unified Revenue Intelligence Platform that traces every patient from
advertising spend to collected revenue, functioning as an executive operating
system for the clinic. Implements the `market.md` specification (14 analytics
pages + `fact_patient_journey` fact table + derived metrics + global filters incl.
per-location + CSV/Excel export) on top of Fusion CRM's existing analytics
surface.

Epic: ENG-504 (project "Revenue Intelligence Analytics Platform V1").
Strategy plan: `.agents/strategy/REVENUE_INTELLIGENCE_ANALYTICS_PLATFORM_PLAN.md`.
Source spec: `market.md`.

Child tickets:
- B0 Foundation: ENG-505 (analytics schema + fact_patient_journey + provenance),
  ENG-506 (fact builder/refresh job), ENG-507 (derived metrics + global filter/
  time-range contract incl. location), ENG-508 (CSV/Excel export + drill-down).
- B1 Missing-field enablement: ENG-509 (caller+coordinator → actor), ENG-510
  (doctor → actor), ENG-511 (treatment-accepted + surgery stages), ENG-512
  (marketing-cost allocation), ENG-513 (manual enrichment path).
- B2 Pages (14): ENG-514 Executive Overview, ENG-515 Funnel, ENG-516 Marketing
  Performance, ENG-517 Vendor, ENG-518 Caller, ENG-519 Coordinator, ENG-520
  Doctor, ENG-521 Revenue Intelligence, ENG-522 Cost Intelligence, ENG-523
  Patient Journey, ENG-524 Bottleneck Detection, ENG-525 Attribution, ENG-526
  Cohort, ENG-527 Revenue Influence Matrix.
- B3 Closeout: ENG-528 (future AI-analytics hooks), ENG-529 (verification +
  real-data validation + cross-runtime review).

Read-only staff surface. Dev-phase full-visibility (staff may see all data; logs
stay PHI-free; no raw payloads in responses/exports). Person spine =
`identity.person.id`. Analytics logic in `packages/analytics`, composed in
`apps/api` (no business logic in routes). New `analytics` DB schema is a
rebuildable projection, never a source of truth. Missing fields ship nullable
with provenance and never block the build.
