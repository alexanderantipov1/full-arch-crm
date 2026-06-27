# Verification — ENG-309

## Worker (sandbox-aware)

```bash
ruff check packages/identity/ packages/ingest/ infra/scripts/ tests/identity/
mypy packages/identity/ infra/scripts/audit_identity_merges.py
```

If pytest runs on focused subset:

```bash
pytest tests/identity/ tests/infra/test_audit_identity_merges.py -v -o pythonpath=.
```

Document what ran vs what the integrator must re-run with `.env`.

## Integrator (canonical checkout, .env)

```bash
make lint
mypy .
pytest tests --ignore=tests/integration -q
cd packages/db && alembic check
```

All green. Baseline comparison (current main HEAD `9829967`): mypy 299
files, pytest 891 passed.

## Smoke (post-merge)

1. Run audit dry-run:
   ```bash
   set -a && source .env && set +a
   python3 infra/scripts/audit_identity_merges.py \
     --tenant-id 11111111-1111-4111-8111-111111111111 \
     --dry-run | tail -30
   ```
   Expect: at minimum the Torosyan-shape person
   `5758e85c-9085-4e09-8459-0db9de56da33` flagged (Eduard vs Gaiane DOB
   mismatch). Probably more.
2. Operator reviews the sample; decides whether to fire the un-merge
   script (separate go).
3. Re-load `/persons/5758e85c-...` — after un-merge, the person card
   should show one person (Gaiane with 2 pids) OR redirect / show
   updated split state. Eduard becomes his own person with his own pid
   1460847.
4. After ENG-310 lands, the per-pid expander shows names so the operator
   can visually confirm.
