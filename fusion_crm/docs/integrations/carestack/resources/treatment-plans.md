# Treatment Plan

**Fusion domain:** `phi`
**PHI:** yes — clinical plan attached to a patient.
**Spec section:** Resource 21 (CareStack Developer API v1.0.45)

## Object fields

### TreatmentPlan

| field | type | notes |
|---|---|---|
| TreatmentPlanId | int | unique identifier |
| TreatmentPlanName | string | name / title |
| StatusId | TreatmentPlanStatus | enum below |
| Duration | int | months (or defined unit) |
| ConditionIds | string | comma-separated condition ids |
| CoordinatorId | int? | optional |
| TreatmentPlanPhase | TreatmentPhase[] | list of phases |

### TreatmentPlanStatus enum

| value | name |
|---|---|
| 0 | NotSet |
| 1 | Proposed |
| 2 | Recommended |
| 3 | Accepted |
| 4 | Rejected |
| 5 | Alternative |
| 6 | Hold |
| 7 | ReferredOut |
| 8 | Completed |
| 9 | Presented |
| 10 | ServiceCompleted |

### TreatmentPhase

| field | type | notes |
|---|---|---|
| TreatmentPlanPhaseId | int | unique identifier |
| TreatmentPlanId | int | FK to treatment plan |
| PlanPhaseName | string | |
| Duration | int | |
| IsDeleted | bool | |

## Endpoints

### `GET /v1.0/patients/{patientid}/treatment-plans` — list treatment plans for a patient
- **Path params:** `patientid` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — array (spec wording says "object of treatment plan details" — likely a list; TBD — verify in PDF p.38)

## Fusion mapping

- Target table(s): `phi.treatment_plan`, `phi.treatment_plan_phase`.
- Ingestion strategy: on-demand (pre-visit) + sync if we maintain plan history.
- Open questions:
  - `ConditionIds` is a comma-separated string — split on ingest.
  - Response shape (single vs array) — confirm against live API.
