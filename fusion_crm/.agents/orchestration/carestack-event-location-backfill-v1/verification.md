# Verification — ENG-270

```bash
make lint
mypy .
make test
cd packages/db && alembic check   # no drift (data-only migration)
cd packages/db && alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

Focused:
- After upgrade: `count(*) FILTER (WHERE payload ? 'location_id')` > 0 for
  invoice_created / payment_recorded / treatment_* (was 0).
- Backfilled location_id matches the raw_event's CS locationId mapping.
- Unmapped CS locations / events without a raw locationId stay without location_id.
- Re-running `alembic upgrade head` (or the UPDATE) changes 0 additional rows.
- A dashboard query with a location filter (wide window) returns non-zero
  Collected/Invoices for a location that has billing events.
- No PHI introduced.
