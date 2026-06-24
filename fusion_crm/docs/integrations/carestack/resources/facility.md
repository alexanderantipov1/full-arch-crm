# Facility

**Fusion domain:** `clinic` (new, TBD)
**PHI:** no — facility directory (off-site care locations such as nursing homes, jails, etc.).
**Spec section:** Resource 19 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| accountId | integer | account the facility belongs to |
| id | integer | unique identifier |
| name | string | |
| type | integer | 1 AssistedLiving, 2 InHome, 3 ElementarySchool, 4 JuvenileDetention, 5 Jail, 6 SkilledNursingFacilities, 7 RetirementCommunities, 8 MemoryCare, 9 GroupHomes, 10 CorrectionFacilities, 11 Hospitals, 12 NursingHomes, 13 Corporate, 14 SpecialPrograms, 15 Other |
| address | Address | addressLine1/2, city, state, zipCode |
| timeZone | string | |
| phone1 | string | |
| phone2 | string | |
| fax | string | |
| email | string | |
| status | integer | 1 Active, 2 Inactive |
| locationIds | integer[] | locations assigned to the facility |

## Endpoints

### `GET /v1.0/facility` — list all facilities in the account
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of Facility objects (spec example shows a single-object response but narrative says "all the facilities within the account" — TBD — verify in PDF p.33)

## Fusion mapping

- Target table(s): `clinic.facility` (new domain, TBD) with a join table to `clinic.location` for `locationIds`.
- Ingestion strategy: sync (low-frequency).
- Open questions:
  - Shape of the response (array vs single object) — confirm by calling the live API.
