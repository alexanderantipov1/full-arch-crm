# Periodontal Charting

**Fusion domain:** `phi`
**PHI:** yes — clinical exam data linked to a patient.
**Spec section:** Resource 8 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| id | string | unique identifier (GUID) |
| date | date | exam taken date |
| examname | string | exam name (appears as `examName` in responses) |
| providerID | number | FK to provider |
| locationID | number | FK to location |
| patientID | number | FK to patient |
| annotation | string | JSON blob with perio drawings (Maxilla/Mandible → Facial/Palatal) |
| dentition | string | JSON blob describing tooth dentition |
| status | string | `New`, `Open`, or `Completed` |
| deleteStatus | bit | 0 or 1 |
| chart | object | `{ maxilla: { tooth1, ... }, mandible: { tooth17, ... } }` |
| conditions | object | `{ missingTeeth, extractedTeeth, impactedTeeth, implantedTeeth, crownedTeeth, bridgeAbutmentTeeth, bridgePonticTeeth }` |

Response example also includes `createdBy`, `createdOn`, `accountID`, `lastUpdatedBy`, `lastUpdatedOn`, `documentPartitionKey`.

## Endpoints

### `GET /v1.0/patients/{patientId}/periodontal-charting` — list patient perio charts
- **Path params:** `patientId` (integer)
- **Query params:**
  - `offset` (integer, ≥0, optional)
  - `limit` (integer, ≥1, optional)
  - `id` (string, optional — specific perio chart id filter)
- **Body:** none
- **Success:** 200 — array of perio chart objects, latest first

## Fusion mapping

- Target table(s): `phi.perio_chart` with JSON columns for `chart`, `conditions`, `annotation`, `dentition`.
- Ingestion strategy: on-demand (fetch only when needed by clinical UI).
- Open questions:
  - Large JSON blobs — do we store raw JSON or flatten per tooth? Start with raw JSON.
  - `annotation` and `dentition` appear as stringified JSON — decode on ingest.
