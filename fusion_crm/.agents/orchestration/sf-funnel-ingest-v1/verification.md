# Verification — sf-funnel-ingest-v1

Per task:

- `.venv/bin/python -m pytest tests/ingest tests/worker -q` (focused)
- `.venv/bin/python -m ruff check <touched files>`
- `.venv/bin/python -m mypy <touched packages>`
- `cd packages/db && alembic check` (no migrations expected in ENG-381)
- Local stack smoke: run one scheduled tick (or call the import services
  against local DB) twice; second run must produce 0 new raw rows.
- Cleanup script: dry-run output reviewed by human BEFORE `--apply`;
  `--apply` only with explicit user approval (destructive).

Full `make lint` + `make test` before integration if shared packages drift.
