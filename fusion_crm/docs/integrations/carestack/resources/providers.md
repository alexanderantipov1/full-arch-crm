# Provider

**Fusion domain:** `staff` (new, TBD)
**PHI:** no — clinician directory only.
**Spec section:** Resource 5 (CareStack Developer API v1.0.45)

## Object fields

### Provider (list shape)

| field | type | notes |
|---|---|---|
| id | integer | unique identifier |
| firstName | string | |
| lastName | string | |
| middleName | string | |
| shortName | string | |
| providerType | string | e.g. "Dentist" (list endpoint uses the string label) |
| isActive | bool | |

### Provider (detail shape)

| field | type | notes |
|---|---|---|
| id | integer | |
| userDetailId | integer | link to user record |
| shortName | string | |
| providerType | integer | integer code on the detail endpoint (TBD — verify enum in PDF p.21) |
| specialityId | integer | |
| ein | string | employer id (format `11-1111111`) |
| npi | string | national provider id (10 digits) |

## Endpoints

### `GET /v1.0/providers` — list all providers
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of Provider (list shape)

### `GET /v1.0/providers/{providerId}` — get one provider by id
- **Path params:** `providerId` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — Provider (detail shape with `userDetailId`, `specialityId`, `ein`, `npi`)

## Fusion mapping

- Target table(s): `staff.provider` (new domain, TBD); `staff.specialty` lookup.
- Ingestion strategy: sync (low-frequency).
- Open questions:
  - List and detail shapes differ (string vs integer for `providerType`). Reconcile on ingest.
  - `userDetailId` — do we always join to the User resource or keep denormalised?
