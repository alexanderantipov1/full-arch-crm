# Referral Source

**Fusion domain:** `ops`
**PHI:** no — marketing channel metadata.
**Spec section:** Resource 2 (CareStack Developer API v1.0.45)

## Object fields

### Referral source

| field | type | notes |
|---|---|---|
| id | integer | unique identifier |
| name | string | referral source name |
| locationIds | integer[] | applicable locations; empty = all |
| status | integer | 1 = active, 0 = inactive |
| isSystemDefined | boolean | true for system-defined, read-only sources |

### Referral source subcategory

| field | type | notes |
|---|---|---|
| id | integer | unique identifier |
| referralSourceId | integer | parent referral source id |
| name | string | subcategory name |
| status | integer | 1 = active, 0 = inactive |

## Endpoints

### `POST /v1.0/referral-sources` — create a new referral source
- **Path params:** none
- **Query params:** none
- **Body:** `{ name (required), status, locationIds }`. Empty `locationIds` = applies to all locations.
- **Success:** 200 — created Referral source object
- **Notes:** system-defined sources cannot be created here.

### `GET /v1.0/referral-sources` — list all referral sources
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of Referral source objects

### `GET /v1.0/referral-sources/{id}/subcategory/` — list subcategories
- **Path params:** `id` (integer, referral source id)
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of subcategory objects

### `POST /v1.0/referral-sources/{referralSourceId}/subcategory/` — create subcategory
- **Path params:** `referralSourceId` (integer)
- **Query params:** none
- **Body:** `{ name (required), referralSourceId (required, mirrors path), status }`
- **Success:** 200 — created subcategory object

## Fusion mapping

- Target table(s): `ops.referral_source`, `ops.referral_source_subcategory`.
- Ingestion strategy: sync (low-frequency).
- Open questions:
  - Do we store `isSystemDefined` so UI can grey out read-only entries? (Yes, recommended.)
