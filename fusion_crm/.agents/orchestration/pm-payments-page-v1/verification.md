# Verification — ENG-271

```bash
make lint
mypy .
make test
cd packages/db && alembic check   # no drift (no schema change)
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```

Focused:
- `/dashboard/pm/payments` returns payment rows with person + stage + amount +
  type + date + location; date/location/provider/search filters work; tenant-scoped.
- List response carries NO clinical free text / no patient identifiers beyond the
  person display name + uid (same safety level as the existing leads list).
- `/ingest/dev/inspector/raw-events/{id}` returns the verbatim payload for a
  raw_event belonging to the tenant; rejects/empties for another tenant's id.
- Page lists payments, filters recalc, a row "view raw" opens the full payload.
- No PHI in logs.
