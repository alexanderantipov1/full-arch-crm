# CareStack Treatment / Payment Classification Draft

## Purpose

PMs and analysts need treatment and payment visibility in the first useful
dashboard. This data is required, but it must be classified before broad
implementation because it is patient-linked and can be clinical,
PHI-adjacent, or billing-sensitive.

## Sources Reviewed

- `docs/integrations/carestack/resources/payment-summary.md`
- `docs/integrations/carestack/resources/treatment-plans.md`
- `docs/integrations/carestack/sync/invoices.md`
- `docs/integrations/carestack/sync/treatment-procedures.md`
- `docs/integrations/carestack/sync/existing-treatment-procedures.md`

## Initial Classification

| Source | Proposed class | Reason |
|---|---|---|
| Payment summary | billing-sensitive / PHI-adjacent | Financial fields tied to `patientId`. |
| Invoices | billing-sensitive / PHI-adjacent | Financial rows tied to patient and location, with payment metadata. |
| Treatment plans | PHI | Clinical plan tied to patient. |
| Treatment procedures | PHI | Procedure, tooth/surface, provider, dates, and estimates tied to patient. |
| Existing treatment procedures | PHI | Historical procedures and notes tied to patient. |

## Dashboard-Safe Aggregates

First dashboard slice should expose aggregates, not raw rows:

- `treatment_total_amount`;
- `treatment_accepted_amount`;
- `treatment_status_summary`;
- `production_total`;
- `collection_total`;
- `balance_due_patient`;
- `balance_due_insurance`;
- `patient_unapplied_credits`;
- `first_payment_at`;
- `last_payment_at`;
- `ar_risk_flag`.

## Canonical Domain Implication

Existing docs point to:

- `billing` as a new domain for invoices/payment summary;
- `phi` for treatment plans and treatment procedures.

This mission should not force treatment/procedure detail into `ops`. If a
dashboard needs an ops-safe summary, create a service-built read model or
aggregate projection with explicit source references and no clinical free text.

## Minimum Safe Slice

Recommended first implementation after this classification:

1. Resolve CareStack patient id to `person_uid` through `identity.source_link`.
2. Capture raw CareStack payloads in `ingest.raw_event`.
3. Store or cache payment summary / invoice aggregates behind a billing-aware
   service boundary.
4. Store treatment/procedure detail only through a PHI-aware service boundary,
   or delay row-level treatment detail and expose only aggregate treatment
   status/amounts.
5. Expose dashboard DTOs with aggregate numbers and status flags only.
6. Keep notes, tooth/surface data, procedure descriptions, and raw treatment
   text out of the PM/Analyst dashboard response.

## Architecture Decision For ENG-257

Proceed with a minimum dashboard-safe billing aggregate slice, not a broad
domain expansion:

1. Do not place billing-sensitive or clinical treatment/procedure detail in
   `ops`.
2. Do not create a full `billing` schema/package in ENG-257 unless a separate
   structural change is approved.
3. Expose payment/invoice visibility through a narrowly named billing-aware
   aggregate service/read model that returns dashboard DTOs only.
4. Keep treatment/procedure detail behind a PHI-aware boundary, or omit it from
   v1 and expose only aggregate treatment totals/status.
5. Do not expose raw CareStack payloads, notes, tooth/surface data, procedure
   descriptions, or clinical free text in PM/Analyst dashboard responses.
6. Row-level invoice/payment drilldowns remain out of scope until an additional
   permission model is defined.

## Remaining Open Decisions

1. Which staff roles may see payment aggregates.
2. Whether CareStack payment summary should be fetched on-demand or cached by
   scheduled sync.
