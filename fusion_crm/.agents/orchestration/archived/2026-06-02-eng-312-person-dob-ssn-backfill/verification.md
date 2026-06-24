# Verification — ENG-312

Worker (in worktree):
- `.venv/bin/python -m pytest tests/infra/test_backfill_person_dob_ssn.py -o pythonpath=. -v`
  (worktree needs `-o pythonpath=.` — shared .venv is editable-installed against source repo).
- `make lint && mypy . && cd packages/db && alembic check`.

Orchestrator (post-merge, before any --apply):
- Dry-run on local `:5434`:
  `.venv/bin/python infra/scripts/backfill_person_dob_ssn.py --tenant-id 11111111-1111-4111-8111-111111111111 --dry-run --max-persons 20`
  → sane plan, 0 errors, no PHI in logs.
- Spot a known split person (e.g. canary 1e80cb31 pid 1663653): dry-run shows it would
  set dob/ssn from that pid's latest payload.

Real `--apply` = SEPARATE operator go (not part of this mission's merge).
