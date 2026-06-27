# Documents

**Fusion domain:** `ingest` + GCS
**PHI:** yes when attached to a patient (e.g. consent forms, clinical scans) — treat as PHI by default.
**Spec section:** Resource 17 (CareStack Developer API v1.0.45)

## Object fields

### Upload-session request

| field | type | notes |
|---|---|---|
| DocumentName | string | e.g. `consent form.pdf` |
| Type | enum | document type (TBD — verify enum values in PDF p.32) |
| TypeId | integer | identifier for the `Type` (e.g. `patientId` when `Type == Patient`) |
| ExtendedProperties | Map<string, string> | optional metadata |

### Upload-session response

| field | type | notes |
|---|---|---|
| DocumentId | guid | document identifier |
| Uri | string | blob upload URL |
| Token | string | SAS token for the blob |

### Commit payload

Same shape as the upload-session request (`DocumentName`, `Type`, `TypeId`, `ExtendedProperties`).

## Endpoints

### `POST /v1.0/documents` — create upload session
- **Path params:** none
- **Query params:** none
- **Body:** `{ DocumentName, Type, TypeId, ExtendedProperties? }`
- **Success:** 200 — `{ DocumentId, Uri, Token }` (client then PUTs bytes to the Azure blob URL using the SAS token)

### `POST /v1.0/documents/{documentId}/commit` — commit upload
- **Path params:** `documentId` (guid)
- **Query params:** none
- **Body:** `{ DocumentName, Type, TypeId, ExtendedProperties? }`
- **Success:** 200 — integer identifier of the stored document

## Fusion mapping

- Target table(s): `ingest.document_index` (document id + metadata only); blob bytes live in GCS, never in Postgres.
- Ingestion strategy: on-demand per workflow. For any document attached to a patient, route content through `phi` with a pointer row.
- Open questions:
  - The `Type` enum values are not listed in the plain-text dump — TBD — verify in PDF p.32.
  - Do we replicate Azure SAS → GCS on our side for egress, or read-through?
