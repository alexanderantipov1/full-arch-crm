# Goal — backfill location_id onto existing CareStack events (ENG-270)

Regression from ENG-269: dedup kept the earliest (pre-location) row per key, so
0 existing invoice/payment/treatment events carry `location_id` → every dashboard
location filter shows 0.

Fix: one-time migration backfill. For events lacking `payload.location_id`, read
the linked `ingest.raw_event.payload->>'locationId'`, resolve via
`tenant.location.external_ref->>'carestack_location_id'` (same tenant), and set
`payload.location_id`. No new schema. Runs in prod via the alembic Job.

Linear: ENG-270. No PHI (location id only).
