# Incidents — carestack-event-location-backfill-v1

- 2026-05-30 | Regression: running ENG-269 dedup (keep-earliest) on local data that mixed pre-location and post-location duplicates dropped all location_id. Lesson: when a dedup keeps "earliest", later-enriched fields (location) are lost. Backfill from raw is the recovery.
