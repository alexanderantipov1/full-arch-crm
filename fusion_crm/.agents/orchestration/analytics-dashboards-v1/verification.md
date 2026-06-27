# Verification — analytics-dashboards-v1 (ENG-468)

## Overnight (automated, every ticket)
- `ruff check .` clean on touched files.
- `mypy .` clean on touched packages.
- `make test` / targeted pytest: real-PostgreSQL integration test per service
  aggregation, seeding marketing + ops rows; mirror `tests/` layout.
- Zod⇄Pydantic parity: field names/optionality match; dates use `Datetime`.
- Pre-merge hygiene: `git status`, `git ls-files -u`,
  `rg "<<<<<<<|=======|>>>>>>>"`, `git diff --check`.

## Morning (human + orchestrator, before push/PR)
- Run the app (dev stack on 127.0.0.1; ports 5434/6380) and confirm each page
  renders with real ingested data (feedback_verify_with_real_data_before_merge).
- Eyeball spend / sessions / funnel numbers vs the Replit dashboards for one
  month.
- Cross-runtime Codex review of the bundled diff (contract_change gate).
- Then push epic branch + open PR(s).

## Notes
- DB access only through services/repos (no agent direct DB).
- No `.env*` edits; no edits to shipped Alembic revisions. New migration only if
  a read-model/materialization table is truly needed (prefer on-the-fly queries).
