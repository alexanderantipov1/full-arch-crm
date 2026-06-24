# Find Slot

**Fusion domain:** on-demand, no persistence
**PHI:** no — free-slot query returns provider/operatory/time only.
**Spec section:** Resource 16 (CareStack Developer API v1.0.45)

## Object fields

### Top-level result (per provider)

| field | type | notes |
|---|---|---|
| providerId | integer | |
| nextAvailableDate | date | populated only when no free slots match the query and the provider has availability within the next 3 months |
| slots | Slot[] | may be empty |

### Slot

| field | type | notes |
|---|---|---|
| startDateTime | datetime | UTC ISO |
| endDateTime | datetime | UTC ISO |
| operatoryId | integer | |
| productionTypeId | integer | spec example renders it as `productionTyeId` — TBD — verify in PDF p.31 |

## Endpoints

### `GET /scheduler/api/v1.0/appointments/find-slot` — list free slots
- **Path params:** none
- **Query params:**
  - `fromDate` (date, required)
  - `toDate` (date, optional; default = `fromDate + 1`; max `fromDate + 6`)
  - `locationId` (integer, required)
  - `providerId` (integer, required; may repeat — up to 5)
  - `productionTypeId` (integer, required; may repeat — up to 5)
- **Body:** none
- **Success:** 200 — array of per-provider result objects
- **Notes:**
  - Single-location context only.
  - Up to 7 slots returned per provider per day.
  - Base path is `/scheduler/api/v1.0` (not `/api/v1.0`).

## Fusion mapping

- Target table(s): none — results are ephemeral and used only for on-screen booking flows.
- Ingestion strategy: on-demand; do not cache across sessions.
- Open questions:
  - Confirm `productionTyeId` key spelling in real payloads vs. the likely-typo in the spec.
