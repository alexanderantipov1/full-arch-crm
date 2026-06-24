# Verification — ENG-283

```bash
make lint
mypy .
make test
cd packages/db && alembic check
cd packages/db && alembic upgrade head && alembic downgrade -1 && alembic upgrade head
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```

Focused:
- code→kind: PATIENTPAYMENTS→payment_recorded; PATPAYMENTAPPLIED→payment_applied;
  PATIENTPAYMENTSDELETE→payment_reversed; isReversed=true overrides to reversed.
- Aggregate: collected_total = recorded − (refunded + reversed); applied excluded.
- Backfill: after upgrade on local DB, events with raw code PATPAYMENTAPPLIED are
  now payment_applied; Collected ≈ $11,698 (was $38,178); re-run updates 0.
- Page: applied hidden by default, toggle shows them; type label per row.
- No PHI in logs/response.
