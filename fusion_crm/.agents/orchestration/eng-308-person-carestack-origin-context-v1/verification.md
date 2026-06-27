# Verification — ENG-308

## Worker (sandbox-aware)

```bash
ruff check infra/scripts/backfill_providers.py \
  apps/api/routers/persons.py \
  packages/ingest/ \
  tests/infra/ \
  tests/ingest/
mypy infra/scripts/backfill_providers.py packages/ingest/
```

If sandbox allows backend pytest on the focused subset, run:

```bash
pytest tests/ingest/ tests/infra/ tests/api/test_person_detail.py -v -o pythonpath=.
```

If sandbox allows web tests:

```bash
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```

Worker MUST document what ran vs what the integrator must re-run with `.env`.

## Integrator (orchestrator session, canonical checkout with .env)

```bash
make lint
mypy .
pytest tests --ignore=tests/integration -q
cd packages/db && alembic check
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```

All green. Confirm:
- No regression vs current pre-merge baseline (mypy 292 files clean,
  pytest 868 passed, vitest 63 passed).
- If a migration was added, `alembic check` reports no drift.

## Smoke (post-merge)

1. **Dev server**: refresh `/persons/5758e85c-9085-4e09-8459-0db9de56da33`
   (Torosyan). Expect:
   - "First ingest" instead of "Patient since".
   - "Earliest activity" showing March 2026 (from pid 1461274's earliest
     appointment), not May 2026.
   - "City, State" line.
   - "Linked to 3 CareStack patient records" banner — click expands.
   - Provider field renders `"—"` initially (no providers in DB yet).
2. **Provider backfill dry-run** (separate operator go):
   ```bash
   python3 infra/scripts/backfill_providers.py \
     --tenant-id 11111111-1111-4111-8111-111111111111 \
     --dry-run --max-providers 500 | tail -10
   ```
   Verify the dry-run resolves a sensible provider count.
3. **Real provider backfill** (separate operator go after dry-run):
   ```bash
   python3 infra/scripts/backfill_providers.py \
     --tenant-id 11111111-1111-4111-8111-111111111111 \
     --max-providers 1000 \
     --sleep-seconds 0.5 \
     --commit-every 50 &
   ```
4. After backfill: refresh the page; provider names appear where
   `defaultProviderId` is set.
