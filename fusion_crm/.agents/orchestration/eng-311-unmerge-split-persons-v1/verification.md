# Verification — ENG-311

## Worker (sandbox-aware)

```bash
ruff check infra/scripts/split_wrong_merged_persons.py tests/infra/
mypy infra/scripts/split_wrong_merged_persons.py
pytest tests/infra/test_split_wrong_merged_persons.py -v -o pythonpath=.
```

Document what ran vs deferred.

## Integrator (canonical .env)

```bash
make lint
mypy .
pytest tests --ignore=tests/integration -q
cd packages/db && alembic check
```

Baseline: main HEAD `c213772` — mypy 303, pytest 915.

## Smoke (post-merge)

1. **Dry-run single target** (Torosyan):
   ```bash
   set -a && source .env && set +a
   python3 infra/scripts/split_wrong_merged_persons.py \
     --tenant-id 11111111-1111-4111-8111-111111111111 \
     --person-uid 5758e85c-9085-4e09-8459-0db9de56da33 \
     --dry-run | tail -20
   ```
   Expect the plan: keep Gaiane's 2-pid bucket on original person,
   spin Eduard's 1 pid into a new person.

2. **Dry-run fleet** (count check):
   ```bash
   python3 infra/scripts/split_wrong_merged_persons.py \
     --tenant-id 11111111-1111-4111-8111-111111111111 \
     --dry-run --max-splits 5000 | tail -10
   ```
   Expect ~3,416 planned splits.

3. **Operator approves → real apply in batches** (SEPARATE go):
   ```bash
   python3 infra/scripts/split_wrong_merged_persons.py \
     --tenant-id 11111111-1111-4111-8111-111111111111 \
     --apply --max-splits 500
   ```
   Run in batches, re-run audit between batches.

4. **After fleet apply**: re-run
   `infra/scripts/audit_identity_merges.py --dry-run` → should report
   ~0 wrong-merged persons.

5. **Verify on the Torosyan card** `/persons/5758e85c-...` — now shows
   one person (Gaiane, 2 pids), Eduard moved to his own person.id with
   his own Paid/Balance.
