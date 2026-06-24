# Payment Summary

**Fusion domain:** `billing` (new, TBD)
**PHI:** mixed — tied to a patient identifier; individual balances/credits are financial, not clinical, but read-access still implies patient linkage.
**Spec section:** Resource 6 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| patientId | integer | FK to patient |
| appliedPatientPayment | double | patient payments collected and applied against a service |
| appliedInsPayments | double | insurance payments collected and applied against a service |
| balanceDuePatient | double | outstanding balance owed by patient |
| balanceDueInsurance | double | outstanding balance owed by insurance |
| patientUnappliedCredits | double | patient payment received but not yet applied |

## Endpoints

### `GET /v1.0/billing/payment-summary/{patientid}` — patient payment summary
- **Path params:** `patientid` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — PaymentSummary object

## Fusion mapping

- Target table(s): none persisted long-term; fetch on-demand into `billing` views.
- Ingestion strategy: on-demand (live read from CareStack); optionally cache short-term for dashboards.
- Open questions:
  - Does CareStack expose a timestamp for when the summary was last recomputed? (Spec shows no such field.)
