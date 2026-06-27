# Verification — ENG-284

```bash
make lint
mypy .
make test
cd packages/db && alembic check
cd packages/db && alembic upgrade head && alembic downgrade -1 && alembic upgrade head
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```

Focused:
- A non-payment code (PROCEDURECOMPLETED/PATIENTADJUSTMENT) with isReversed=true
  emits NO event.
- A payment code with isReversed=true → payment_reversed; without → its mapped kind.
- Corrective migration: every payment-kind event now has a payment transactionCode;
  spurious ones (non-payment code) are deleted; re-run changes 0 rows.
- collected_total ≈ $11,538 (POSITIVE) after upgrade; payment_reversed only real
  payment reversals.
- No PHI.
