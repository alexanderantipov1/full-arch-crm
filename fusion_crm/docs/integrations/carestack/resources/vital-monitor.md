# Vital Monitor

**Fusion domain:** `phi`
**PHI:** yes — ties a patient and clinical case to an external vital monitor device.
**Spec section:** Resource 18 (CareStack Developer API v1.0.45)

## Object fields

### VitalMonitor (top-level)

| field | type | notes |
|---|---|---|
| IsProvider | bool | is the calling user a provider? |
| ClinicalCaseId | string | clinical case id (guid) |
| Vendor | string | vendor name, e.g. `XChart` |
| VitalMonitorDetails | VitalMonitorDetails | embedded |

### VitalMonitorDetails

| field | type | notes |
|---|---|---|
| VitalMonitorId | long | 0 when invoked at patient level |
| PatientId | int | |
| LocationId | int | |
| ExaminerId | int | provider id of the examiner |
| AppointmentId | int | 0 when invoked at patient level |

## Endpoints

### `GET /v1.0/vital-monitor/{AuthCode}` — get vital monitor details by auth code
- **Path params:** `AuthCode` (string)
- **Query params:** none
- **Body:** none
- **Success:** 200 — `{ VitalMonitor: string }` — an AES-256-encrypted payload
- **Notes:**
  - The response string is AES-256 encrypted using the vendor key (hyphens stripped) as the key. IV is prepended to ciphertext.
  - Example vendor key `472B39B6-7D7B-466E-9960-94C512EFF9C2` is used as `472B39B67D7B466E996094C512EFF9C2`.
  - Decrypted payload is the VitalMonitor JSON object above.

## Fusion mapping

- Target table(s): `phi.vital_monitor_session` (ephemeral mapping of clinical case → device).
- Ingestion strategy: on-demand (per launch of the vital monitor integration UI).
- Open questions:
  - Vendor key storage — keep in secret manager, not in DB.
  - Do we cache decrypted payloads? Probably no — re-fetch each session.
