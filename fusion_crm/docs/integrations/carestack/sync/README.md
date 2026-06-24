# CareStack Sync APIs — overview

The CareStack Sync resources are polling endpoints that return every
record of a given type modified after a caller-supplied timestamp.
They are how Fusion keeps its local mirror warm without depending on
webhooks.

## Pattern

All sync endpoints share the same shape:

```
GET /api/{version}/sync/<resource>?modifiedSince=<iso-utc-datetime>
                                  &continueToken=<token>
                                  &pageSize=<n>
```

- `modifiedSince` is an ISO 8601 UTC datetime. Records with
  `lastUpdatedOn >= modifiedSince` are returned.
- `continueToken` is opaque. `null` starts a fresh scan; the response
  returns the next token, or `null` when the scan is complete.
- `pageSize` defaults to `100`, maximum `500`.
- Some resources (`treatment-procedures`, `existing-treatment-procedures`)
  accept `includeDeleted=true` to see tombstones.

## State kept in Fusion

For each resource we keep one row in `ingest.sync_cursor`, keyed by
`(source, resource)`:

| column | meaning |
|---|---|
| `source` | `"carestack"` |
| `resource` | e.g. `"patients"`, `"appointments"`, `"invoices"` |
| `watermark_at` | last successfully processed `lastUpdatedOn` |
| `continue_token` | in-flight pagination token, `null` between runs |
| `updated_at` | cursor row mtime |

One cursor per resource — do **not** share a watermark across resources.

## Commit discipline

Strict ordering per page:

1. Fetch a page from CareStack.
2. For every record in the page, insert into `ingest.raw_event` with
   `source="carestack"` and the per-resource `event_type`
   (e.g. `carestack.patient.upsert`, `carestack.appointment.upsert`).
3. Flush / commit the `raw_event` batch.
4. Only after the commit succeeds, update `ingest.sync_cursor`:
   - If the response carried a `continueToken`, store it and keep
     `watermark_at` unchanged — we are mid-scan.
   - If the response's `continueToken` is `null`, set
     `watermark_at = max(lastUpdatedOn)` across the scan and clear the
     token. The next run starts from this new watermark.

Never advance the cursor past a page you did not persist. A crash
between steps 1 and 3 must leave the cursor untouched so the next run
re-fetches the same page.

## Failure handling

- Transport / 5xx / rate-limit errors: retry with `tenacity`
  (exponential backoff, jittered, capped at a few minutes).
- Auth errors: bubble up — operator action required.
- Permanent / schema-breaking errors: log, alert, **leave the cursor
  alone**. Operator restarts the job after investigation. Do not
  swallow and advance.

## Cadence suggestions

| resource | suggested interval |
|---|---|
| `patients` | every 5 min |
| `appointments` | every 5 min |
| `treatment-procedures` | every 15 min |
| `existing-treatment-procedures` | every 15 min |
| `invoices` | every 15 min |
| `billing/procedures` (accounting procedure) | every 15 min |
| `accounting-transactions` | every 15 min |

Tune after the first week of production data: cadence should match
the clinic's actual update rhythm, not a default.

## Idempotency

Re-processing a page is expected (crash recovery, overlapping
windows). Dedup inside the CareStack ingest handler by the natural
key plus `lastUpdatedOn`:

- patients: `(patientId, lastUpdatedOn)`
- appointments: `(id, lastUpdatedOn)`
- treatment procedures: `(id, lastUpdatedOn)`
- existing treatment procedures: `(id, lastUpdatedOn)`
- invoices: `(invoiceId, lastUpdatedOn)`
- accounting procedures: `(treatmentProcedureId, lastUpdatedOn)`
- accounting transactions: `(id, lastUpdatedOn)`

## PHI

Treat **every** sync payload as potentially PHI, even if a resource
looks directory-like. Rules:

- Never log payload bodies. Allowed log fields: `source`, `resource`,
  `page_size`, `record_count`, `continue_token` presence bool,
  `watermark_at`.
- Raw payloads land in `ingest.raw_event` (segregated schema) and are
  then translated by `apps/worker/jobs/ingest_carestack.py` into
  domain services (`identity`, `phi`, `scheduling`, `billing`).
- AI agents never read `ingest.raw_event` directly.
