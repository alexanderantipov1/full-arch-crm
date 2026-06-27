# Q0 — ENG-188 Alembic Drift Fix

## Status

Complete.

## Summary

`alembic check` drift was caused by ORM metadata no longer describing
schema objects that already exist in the database:

- ENG-123 tenant indexes existed in the DB, but `TenantScopedMixin` model
  adopters did not declare the matching index metadata.
- `outreach.template.category` and `outreach.campaign.mailbox_strategy`
  had DB server defaults from the original migration, but model metadata
  omitted those `server_default` values.

No shipped Alembic revision was edited. No new migration was needed.

## Files Changed

- `packages/actor/models.py`
- `packages/audit/models.py`
- `packages/auth/models.py`
- `packages/identity/models.py`
- `packages/ingest/models.py`
- `packages/integrations/models.py`
- `packages/interaction/models.py`
- `packages/ops/models.py`
- `packages/outreach/models.py`
- `packages/phi/models.py`

## Verification

- PASS: `cd packages/db && ../../.venv/bin/alembic check`
  - `No new upgrade operations detected.`
- PASS: `source ./.venv/bin/activate; make verify`
  - `ruff check .`
  - `mypy packages apps`
  - deploy-critical pytest bundle: 24 passed
- PASS: `.venv/bin/python -m pytest tests/actor/test_models.py tests/identity/test_models.py tests/interaction/test_models.py tests/ops/test_models.py -q`
  - 35 passed
- PASS: `git diff --check`

## Known External Debt

- `mypy .` still fails on existing test typing debt.
- Full `make test` still fails on the existing tenant isolation Phase B
  fixture plus unrelated outreach/worker failures.

These are tracked by the separate full-verify cleanup issues and were not
introduced by this fix.

## Linear

- `ENG-188` moved to `Done`.
- `ENG-181` commented as unblocked for the next additive data-foundation
  wave.
