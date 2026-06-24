# Verification — ENG-269

```bash
make lint
mypy .
make test
cd packages/db && alembic check   # no drift after the new revision
# migration round-trip:
cd packages/db && alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

Focused:
- Idempotency: calling create_event twice with the same
  (tenant, source_provider, source_kind, source_external_id, kind) inserts once;
  second call is a no-op (no exception, no second row).
- Transition allowed: same source_external_id with a different kind
  (treatment_proposed vs treatment_completed) → two rows, not blocked.
- Null external_id: events without source_external_id are not constrained.
- Migration data-fix: after upgrade on a DB with duplicates, count(*) per kind ==
  count(distinct source_external_id); a re-pull keeps it flat.
- No PHI in any new log line.
