# Goal — idempotent interaction.event emission (ENG-269)

Stop re-pull duplication of timeline events (currently ×5 → dashboard money
inflated: Collected shows $190,891, real $38,178). Two parts:

1. **Migration**: dedupe existing `interaction.event` rows (keep earliest per
   key) + add a partial UNIQUE INDEX so future inserts can't duplicate.
2. **Idempotent emission**: `create_event` becomes ON CONFLICT DO NOTHING; ingest
   callers treat "already exists" as a no-op.

Dedup key: `(tenant_id, source_provider, source_kind, source_external_id, kind)`
where `source_external_id IS NOT NULL`. Keeps proposed→completed transitions.

The migration runs in prod via the alembic Cloud Run Job → prod dedupes on the
next deploy. Linear: ENG-269.
