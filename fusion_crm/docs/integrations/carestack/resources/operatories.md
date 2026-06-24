# Operatory

**Fusion domain:** `clinic` (new, TBD)
**PHI:** no — room/chair directory only.
**Spec section:** Resource 7 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| id | integer | operatory id |
| locationId | integer | FK to location |
| name | string | operatory name |

## Endpoints

### `GET /v1.0/operatories` — list all operatories
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of Operatory objects

## Fusion mapping

- Target table(s): `clinic.operatory` (new domain, TBD).
- Ingestion strategy: sync (low-frequency; rarely changes).
- Open questions: none.
