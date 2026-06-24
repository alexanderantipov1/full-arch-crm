# Verification — ENG-306

## Frontend (always required)

```bash
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```

Focused (worker performs + includes in report):

- New tests on the person-card financial block: renders four numbers when
  snapshot present; renders `"—"` four times + empty timestamp line when
  snapshot absent; currency formatting consistent.
- New tests on the Payments row pill: pill renders with balance; pill renders
  `"—"` when snapshot absent; no pagination regression (existing tests still
  pass).
- Visual: orchestrator opens dev server (or worker uses Chrome via Claude
  Code's native integration) and confirms layout on the person card +
  payments page.

## Backend (only if touched)

```bash
make lint && mypy . && make test && cd packages/db && alembic check
```

- New per-patient aggregate method tests (if added): correct dedup, correct
  empty result on missing snapshot, no PHI in logs.

## Out of band (post-merge, operator's choice)

- After ENG-307 lands + operator approves backfill window: real CareStack
  `payment-summary` backfill of ~1803 patients. After that the UI will
  light up for those patients organically.
