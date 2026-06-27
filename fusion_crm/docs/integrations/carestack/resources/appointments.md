# Appointment

**Fusion domain:** `scheduling` (new, TBD)
**PHI:** yes — appointments tie a patient to a date/time and may contain clinical notes.
**Spec section:** Resource 4 (CareStack Developer API v1.0.45)

## Object fields

### Appointment details

| field | type | notes |
|---|---|---|
| id | integer | unique appointment identifier |
| patientId | integer | FK to patient |
| locationId | integer | FK to location |
| operatoryId | integer | FK to operatory |
| dateTime | datetime | UTC ISO format |
| duration | integer | minutes |
| statusId | integer | FK to Appointment Status |
| notes | string | optional, max length 1000 (create path documents 2000 — TBD — verify in PDF p.16) |
| bookingMode | integer | 1 Direct, 2 Online |
| appointmentMode | integer | 0 None, 1 In-Office, 2 Tele-Appointment |
| providerIds | integer[] | FKs to providers |
| productionTypeId | integer | FK to production type |
| options | integer | 0 None, 1 Reschedule Enabled, 2 ShortCall Enabled |
| version | string | opaque concurrency token |

### Appointment status

| field | type | notes |
|---|---|---|
| id | integer | |
| name | string | |
| isSystem | bool | true = system status (read-only) |
| isActive | bool | |
| label | string | short form |
| color | string | hex color |
| confirmationStatus | integer | 1 NotSet, 2 Confirmed, 3 Unconfirmed |
| description | string | |
| threshold | integer | minutes |

### Production type

| field | type | notes |
|---|---|---|
| id | integer | |
| name | string | |
| color | string | |
| isActive | bool | |
| type | integer | 0 Normal, 1 Block |

## Endpoints

### `POST /v1.0/appointments` — create a new appointment
- **Path params:** none
- **Query params:** none
- **Body:** Required: `patientId`, `locationId`, `operatoryId`, `dateTime`, `duration`, `providerIds`. Optional: `notes` (max 2000).
- **Success:** 200 — created Appointment
- **Notes:** errors `PatientConflictingAppointment` and `ProviderConflictingAppointment` when the slot is taken.

### `GET /v1.0/appointments/{AppointmentId}` — get appointment by id
- **Path params:** `AppointmentId` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — Appointment object

### `DELETE /v1.0/appointments/{AppointmentId}` — delete appointment
- **Path params:** `AppointmentId` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — returns new `version` string

### `PUT /v1.0/appointments/{AppointmentId}/checkout` — checkout appointment
- **Path params:** `AppointmentId` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — returns new `version` string

### `PUT /v1.0/appointments/{AppointmentId}/cancel` — cancel appointment
- **Path params:** `AppointmentId` (integer)
- **Query params:** none
- **Body:** `{ reason (1 No Show, 2 Patient Notified), notes (max 2000), codeRetained (bool), resheduleEnabled (bool — note spec typo), inactivatedBy (1 N/A, 2 Patient, 3 Practice) }`
- **Success:** 200 — returns new `version` string

### `PUT /v1.0/appointments/{AppointmentId}/modify-status` — change status
- **Path params:** `AppointmentId` (integer)
- **Query params:** none
- **Body:** `{ statusId }`
- **Success:** 200 — returns new `version` string
- **Notes:** cannot target system statuses.

### `GET /v1.0/appointment-status` — list all appointment statuses
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of Appointment Status objects

### `GET /v1.0/production-types` — list all production types
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of Production Type objects

## Fusion mapping

- Target table(s): `scheduling.appointment`, `scheduling.appointment_status`, `scheduling.production_type` (new domain, TBD).
- Ingestion strategy: sync (Appointment Sync Resource) + webhook-style polling for near-real-time updates.
- Open questions:
  - Do we persist CareStack's optimistic-concurrency `version` token and use it on our own PUTs?
  - How to represent `providerIds` (array) — join table or denormalised?
  - The `notes` field spec says max 1000 in the model but max 2000 in create/cancel bodies — align on 2000 until CareStack clarifies.
