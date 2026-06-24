# Verification — Full Funnel v2

## Backend (ENG-481)
- `ruff` + `mypy` (or project lint/typecheck) clean on changed packages.
- Endpoint smoke: `GET /dashboard/analytics/full-funnel?audience=all` and
  `?audience=marketing` return 200 with the new shape on local data.
- Reconciliation spot-checks (run via psql on local DB):
  - leads(all) == distinct persons in `ops.lead` ∪
    `identity.source_link(carestack/patient)`.
  - consults showed(all)/no_show(all) == raw `ops.consultation` status counts
    by `person_uid` in window.
  - revenue(all) == Net Collected from `interaction.event`.
  - marketing(stage) <= all(stage) for each stage.

## Frontend (ENG-482)
- Typecheck + build pass.
- Toggle Marketing/All changes the rendered numbers.
- No-show column present; closed-won non-zero (money).

## Tests (ENG-483)
- `pytest` integration tests green against the real PostgreSQL test DB.

## Project loop (when touching product code / shared packages)
- Run the standard verify loop: lint + typecheck + tests + alembic drift check.
- No migration expected (read-model only). If a migration appears, STOP and
  escalate — design says no new tables.
