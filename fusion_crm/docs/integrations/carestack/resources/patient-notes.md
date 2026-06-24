# Patient Notes / Memo

**Fusion domain:** `phi`
**PHI:** yes — free-text notes about a patient may contain clinical content.
**Spec section:** Resource 22 (CareStack Developer API v1.0.45)

## Object fields

### Note (response)

| field | type | notes |
|---|---|---|
| NoteId | int | unique identifier |
| NoteText | string | note text with HTML |
| RawText | string | note text without HTML |
| NoteType | string | see accepted types below |
| NoteAttachments | NoteAttachmentModel[] | attachments |
| DocumentIds | guid[] | document ids referenced by the note |

### Accepted NoteType values

- Patient Appointment
- Patient Clinical
- Patient Communication
- Patient Financial
- Patient General
- Recall Note

### NoteAttachmentModel

| field | type | notes |
|---|---|---|
| NoteId | int | |
| PatientId | int | |
| DocumentId | guid | |
| DocumentName | string | |
| Description | string | |
| Status | string | |

### Note payload (create/update)

| field | type | notes |
|---|---|---|
| NoteId | int | required on update; server-assigned on create |
| PatientId | int | required |
| NoteType | string | required |
| NoteText | string | HTML allowed |
| DocumentIds | guid[] | |

## Endpoints

### `GET /v1.0/patients/notes/{patientId}` — list notes for a patient
- **Path params:** `patientId` (integer)
- **Query params:**
  - `startIndex` (integer) — start index
  - `offSet` (integer) — page size / total entries
- **Body:** none
- **Success:** 200 — array of Note objects

### `PUT /v1.0/patients/notes` — update a note
- **Path params:** none
- **Query params:** none
- **Body:** `{ NoteId, PatientId, NoteType, NoteText, DocumentIds }`
- **Success:** 200 — updated Note (TBD — verify in PDF p.48)

### `DELETE /v1.0/patients/notes/{noteId}/{deleteAttachments}` — delete a note
- **Path params:**
  - `noteId` (integer)
  - `deleteAttachments` (bool) — also delete attached documents when true
- **Query params:** none
- **Body:** none
- **Success:** 200 / 204 — TBD — verify in PDF p.48

### `POST /v1.0/patients/notes` — add a note
- **Path params:** none
- **Query params:** none
- **Body:** `{ NoteId, PatientId, NoteType, NoteText, DocumentIds }`
- **Success:** 200 — id of the newly added note

## Fusion mapping

- Target table(s): `phi.patient_note`, `phi.patient_note_attachment`.
- Ingestion strategy: on-demand; sync if we surface notes in the UI.
- Open questions:
  - HTML content — sanitise before render.
  - Attachments reference `DocumentId` — join with the Documents resource.
  - The query parameter names (`startIndex`, `offSet`) are unusual — mirror verbatim.
