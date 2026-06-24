# Lessons — carestack-event-location-backfill-v1

- Dedup "keep earliest" + later-added payload fields = silent data loss. Prefer
  keep-richest or backfill. raw_event being immutable is what makes recovery possible.
