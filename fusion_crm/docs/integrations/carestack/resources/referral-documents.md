# Referral Document

**Fusion domain:** `phi`
**PHI:** yes — ties a patient to a referring provider, a referral letter, and attached documents.
**Spec section:** Resource 11 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| id | integer | referral document id |
| referredById | integer | referring provider id |
| referredToId | integer | referred-to provider id |
| referredProviderId | integer | usually same as `referredToId`; differs when `referredToId` is a portal-login proxy and `referredProviderId` is the actual provider |
| referralDate | datetime | UTC ISO |
| referralStatus | integer | 1 New, 2 Accepted, 3 Scheduled, 4 Completed, 5 Declined |
| patientId | integer | patient id |
| expectedReturnDate | datetime? | UTC ISO, nullable |
| referralLetterId | string | referral letter id |
| documentId | string | attached document id, if any |
| locationId | integer | location id |

## Endpoints

### `GET /v1.0/referral-document/{referral-document-id}` — get referral document
- **Path params:** `referral-document-id` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — Referral Document object
- **Notes:** spec only documents GET; no list endpoint on this resource.

## Fusion mapping

- Target table(s): `phi.referral_document`.
- Ingestion strategy: on-demand (follow from patient record when needed).
- Open questions:
  - Do we also pull the attached document via the Documents resource automatically on ingest?
