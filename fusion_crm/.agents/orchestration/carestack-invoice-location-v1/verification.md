# Verification — ENG-268

```bash
make lint
mypy .
make test
cd packages/db && alembic check   # no drift — payload-based, no migration
```

Focused:
- Invoice event with mapped `locationId` stores the correct tenant.location UUID;
  unmapped/missing → omits `location_id`, still emits + captures raw.
- After a local re-pull, a dashboard query with a location filter shows non-zero
  Invoices + Payments for a location that has invoices (was 0 before).
- No PHI in payload/summary (amount, invoice_type, location_id only).
