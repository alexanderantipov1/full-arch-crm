# Conventions

Common patterns across endpoints. Specifics per-endpoint are in
`resources/*.md` and `sync/*.md`.

## Identifiers

- `id` — integer PK inside CareStack for most resources.
- `patientId` — integer; the key reference across Patient-scoped
  resources (medications, alerts, insurance, documents, plans, ...).
- `locationId`, `providerId`, `operatoryId`, `facilityId` — integer.
- `appointmentId` — integer; often appears as a path parameter.
- External integration IDs (our `person_uid`, `person_identifier`)
  are NOT stored in CareStack — we keep the mapping on our side.

## Date / time

- Timestamps are ISO 8601. Time zone behaviour is per-location
  (`Location.timeZone`). Treat incoming values as local unless
  suffixed with `Z`.
- Sync endpoints take `modifiedAfter` as an ISO 8601 datetime.
- `dateOfBirth` is a date-only field (`YYYY-MM-DD`).

## Pagination (sync + search)

Sync and search APIs return a batch plus a continuation marker.
The exact parameter names vary by endpoint — check the per-endpoint
doc. General pattern:

```
GET /v1.0/sync/<resource>?modifiedAfter=2025-08-01T00:00:00Z&pageNumber=1&pageSize=100
```

On our side: always drive pagination to exhaustion in one worker run
before committing `modifiedAfter`, otherwise partial progress can be
lost on retry.

## Enums

CareStack returns enum values as strings (status codes, appointment
statuses, etc.). Treat them as opaque in ingest; map to our own
`StrEnum`s only in the per-source handler.

## JSON field naming

`camelCase` in CareStack payloads. Our domain is `snake_case`; the
adapter layer does the translation (don't let camelCase leak into
`packages/*/models.py`).

## Idempotency

- Writes do NOT appear to support an idempotency key. Guard duplicate
  writes by pre-checking existence via Search APIs, or by keeping a
  local "intent" ledger per patient/appointment.
- Reads and Sync APIs are naturally idempotent.

## Rate limits

Not explicitly documented in the spec. Assume conservative defaults:
- ≤ 5 req/s per account for polling.
- Exponential backoff on 429/5xx via `tenacity` in the client.
