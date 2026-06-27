# Location

**Fusion domain:** `clinic` (new, TBD)
**PHI:** no — location metadata only (name, address, phone, timezone).
**Spec section:** Resource 1 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| id | integer | unique identifier |
| name | string | location's full name |
| shortName | string | location's short name |
| email | string | location's email |
| timeZone | string | e.g. `Central Standard Time` |
| phone1 | string | primary phone |
| phone2 | string | secondary phone |
| fax | string | fax number |
| address | Address | embedded object (see below) |

### Address

| field | type | notes |
|---|---|---|
| addressLine1 | string | |
| addressLine2 | string | |
| city | string | |
| state | string | |
| zipCode | string | |

## Endpoints

### `GET /v1.0/locations` — list all locations
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of Location objects
- **Notes:** returns every location configured for the account.

### `GET /v1.0/locations/{locationId}` — get one location by id
- **Path params:** `locationId` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — one Location object
- **Notes:** spec documents no POST/PUT/DELETE for locations.

## Fusion mapping

- Target table(s): `clinic.location` (new domain, TBD).
- Ingestion strategy: sync (low-frequency; change rarely).
- Open questions:
  - Do we want to mirror `timeZone` as IANA or keep the Windows-style string? (Convert on ingest.)
