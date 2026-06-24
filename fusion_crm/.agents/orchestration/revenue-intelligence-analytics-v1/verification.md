# Verification — revenue-intelligence-analytics-v1 (ENG-504)

## Per ticket (automated)
- `ruff check .` clean on touched files.
- `mypy .` clean on touched packages.
- Targeted pytest: real-PostgreSQL integration per service aggregation (seed
  ops/interaction/marketing/attribution rows; mirror `tests/` layout). Unit tests
  for derived metrics (incl. zero denominators), filter/time-range resolver
  (aggregate + per-location), provenance precedence, marketing-cost reconciliation.
- `cd packages/db && alembic check` clean on a fresh DB (new revisions only).
- Zod ⇄ Pydantic parity: field names/optionality match; dates use datetime.
- Pre-merge hygiene: `git status`, `git ls-files -u`,
  `rg "<<<<<<<|=======|>>>>>>>"`, `git diff --check`.

## Per block / before PR (human + orchestrator)
- Run the dev stack (127.0.0.1; ports 5434/6380) and confirm each new page renders
  with real ingested data.
- **Real-data reconciliation** (house rule): eyeball revenue/funnel/cost numbers
  vs the existing Full Funnel + PM dashboards for at least one month AND one
  location. The fact builder's funnel counts must match the existing funnel for
  overlapping stages.
- Confirm honest "no data" rendering for unresolved fields (treatment_accepted,
  surgery_*, caller/coordinator/doctor, marketing_cost until B1 lands).
- Cross-runtime Codex review of the bundled block diff (contract_change gate).

## Mission close (ENG-529)
- Full verify loop green or documented blockers.
- Invariants confirmed: agents never touch DB; logs PHI-free; no raw payloads in
  responses/exports; manual override survives a fact rebuild; prod fact-builder
  job stays gated off by default.

## Notes
- DB access only through services/repositories (no agent direct DB).
- No `.env*` edits; no edits to shipped Alembic revisions; no infra/deploy changes
  in this mission (prod enablement is a separate operator-gated step per
  `docs/DEPLOYMENT_RULES.md`).
