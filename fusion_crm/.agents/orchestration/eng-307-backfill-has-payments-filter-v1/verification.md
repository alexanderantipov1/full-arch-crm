# Verification — ENG-307

## Worker

Worker runs in isolated worktree; sandbox may block the full verify loop
(seen on ENG-306). Worker MUST run the focused subset that does not
require `.env`:

```bash
ruff check infra/scripts/backfill_payment_summary.py tests/infra/
mypy infra/scripts/backfill_payment_summary.py
```

For tests that need `.env`-dependent imports, document inability and
defer to integrator.

## Integrator (orchestrator session) — canonical checkout with .env

```bash
make lint
mypy .
pytest tests/infra/test_backfill_payment_summary.py -v
pytest tests --ignore=tests/integration -q
cd packages/db && alembic check
```

All must be green. Confirm no regression in pre-merge baseline
(855 passed currently on main HEAD `33ea1de`).

## Smoke (post-merge, separate operator go)

```bash
set -a && source .env && set +a
# Dry run with the filter — should print exactly the patients-with-payments
# patient_ids on stdout, NO CareStack API calls.
python3 infra/scripts/backfill_payment_summary.py \
  --tenant-id 11111111-1111-4111-8111-111111111111 \
  --only-with-payments \
  --dry-run \
  --max-patients 3000 | tail -10

# Operator review of the patient_ids count + sample (expect ~1803 ± noise).
# When satisfied, real backfill run (background):
python3 infra/scripts/backfill_payment_summary.py \
  --tenant-id 11111111-1111-4111-8111-111111111111 \
  --only-with-payments \
  --max-patients 3000 \
  --sleep-seconds 0.5 \
  --commit-every 50 &
```

Operator monitors for sustained 429 → abort if seen.
