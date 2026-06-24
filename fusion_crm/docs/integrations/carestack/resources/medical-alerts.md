# Patient Medical Alerts

**Fusion domain:** `phi`
**PHI:** yes — allergies and medical conditions.
**Spec section:** Resource 13 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| patientMedicalAlertId | integer | unique identifier |
| medicalAlertId | integer | catalog alert id |
| alertName | string | |
| alertType | integer | 0 Condition, 1 Allergy |
| isRemoved | bool | true if cleared by a provider |
| removedUserType | integer | 1 Patient, 2 Provider |
| createdUserType | integer | 1 Patient, 2 Provider |
| createdBy | string | name of the user who created the alert |
| removedBy | string | name of the user who removed the alert |
| lastModifiedOn | string | last modified date |
| createdOn | string | created date |

## Endpoints

### `GET /v1.0/patients/{patientId}/medical-alerts` — list patient medical alerts
- **Path params:** `patientId` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of PatientMedicalAlert

## Fusion mapping

- Target table(s): `phi.medical_alert`.
- Ingestion strategy: on-demand (pre-visit fetch) + periodic sync if we surface them in the UI.
- Open questions:
  - `createdBy`/`removedBy` are free-text names — do we also resolve them to `identity.person`? Not required, but helpful.
