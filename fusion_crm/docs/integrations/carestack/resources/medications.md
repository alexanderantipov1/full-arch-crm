# Patient Medications

**Fusion domain:** `phi`
**PHI:** yes — prescribed/active medication history.
**Spec section:** Resource 14 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| id | integer | unique identifier |
| name | string | medication name |
| startDate | datetime | |
| endDate | datetime | |

## Endpoints

### `GET /v1.0/patients/{patientId}/medications` — list patient medications
- **Path params:** `patientId` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of Medication objects

## Fusion mapping

- Target table(s): `phi.medication`.
- Ingestion strategy: on-demand (pre-visit) + periodic sync.
- Open questions:
  - CareStack model is very thin (no dose, no frequency, no provider). Confirm in PDF p.29 whether more fields are returned than documented.
  - TBD — verify in PDF p.29 whether `endDate` is nullable for active meds.
