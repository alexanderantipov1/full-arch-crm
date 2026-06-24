# Contract — interaction-event-idempotency-v1

- Partial UNIQUE INDEX on interaction.event
  `(tenant_id, source_provider, source_kind, source_external_id, kind)`
  `WHERE source_external_id IS NOT NULL`.
- `create_event` is idempotent: a second insert with the same key is a no-op
  (ON CONFLICT DO NOTHING), returns existing row or a skipped marker, never raises.
- Existing duplicates removed by the migration (keep earliest per key).
- No API/schema field changes; dashboard numbers drop to their true (deduped)
  values automatically once the migration runs.
