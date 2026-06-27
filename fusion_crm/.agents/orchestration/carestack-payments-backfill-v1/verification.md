# Verification — ENG-285

```bash
make lint
mypy .
make test           # all CareStack calls MOCKED — no real traffic
cd packages/db && alembic check
```

Focused (mocked client):
- Pagination loops over N mock pages and stops when continueToken is null.
- Throttle sleep is invoked between pages (assert via a patched sleep).
- A 429/5xx response triggers backoff + bounded retries; if exhausted, the loop
  stops and returns the last continueToken (resume).
- Re-running with the same data inserts no duplicate events (idempotent).
- A sync_run row is recorded for the backfill.
- NO test performs a real HTTP call to CareStack.
