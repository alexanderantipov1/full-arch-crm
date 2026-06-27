# Verification — ENG-310

## Worker (sandbox-aware)
```bash
ruff check packages/ingest/ apps/api/routers/persons.py tests/ingest/
mypy packages/ingest/ apps/api/routers/persons.py
pytest tests/ingest/ tests/api/test_person_detail.py -o pythonpath=. -q
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```

## Integrator (canonical .env)
```bash
make lint && mypy . && pytest tests --ignore=tests/integration -q -o pythonpath=.
cd packages/db && alembic check
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```
Baseline: main HEAD 636305c — mypy 305, pytest 941, vitest 71.

## Smoke (post-merge, dev server)
- `/persons/5758e85c-...` (Gaiane): expander shows "Gaiane Torosyan · 1461274"
  + "· 2171827"; Household section links to Eduard (bcd52d13, shares ···4258).
- `/persons/bcd52d13-...` (Eduard): Household links back to Gaiane; financials $0/separate.
- Patient details panel reveals DOB/phones/email/address on click.
