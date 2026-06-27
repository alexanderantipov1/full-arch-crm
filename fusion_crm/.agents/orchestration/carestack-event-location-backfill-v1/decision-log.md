# Decision Log — carestack-event-location-backfill-v1

- 2026-05-30 | Handoff: orchestrator/claude-code -> worker/claude-code for ENG-270.
- 2026-05-30 | Root cause: ENG-269 dedup kept earliest row per key; earliest rows predate ENG-267/268 location emit → 0 events carry location_id; idempotent emission skips re-pulls so they can't regain it.
- 2026-05-30 | Decision: one-time migration backfill from ingest.raw_event.locationId (raw is never deleted) via tenant.location mapping. UPDATE on interaction.event = append-only exception (migration-level), same precedent as ENG-269 DELETE. Prod backfilled via alembic Job on deploy.
