# ENG-257 Worker Report

## Task

- Linear: ENG-257 — Implement minimum CareStack treatment/payment dashboard slice
- URL: https://linear.app/fusion-dental-implants/issue/ENG-257/task-g-implement-minimum-carestack-treatmentpayment-dashboard-slice
- Role: Worker
- Agent: codex
- Branch: main
- Worktree: current checkout
- Scope: product feature

## Changed Files

- `packages/interaction/repository.py`
- `packages/interaction/service.py`
- `packages/interaction/schemas.py`
- `apps/api/routers/dashboard.py`
- `apps/web/lib/api/schemas/dashboard.ts`
- `apps/web/app/(staff)/project-manager/page.tsx`
- `apps/web/lib/msw/handlers.ts`
- `tests/api/test_dashboard_pm.py`
- `tests/interaction/test_service.py`
- `tests/integration/test_tenant_isolation.py`

## What Changed

- Added a minimum dashboard-safe CareStack treatment/payment aggregate slice
  over existing workflow-ready `interaction.event` rows:
  - `treatment_proposed`;
  - `treatment_completed`;
  - `invoice_created`.
- Aggregates include treatment presented/completed counts, invoice count,
  summed safe invoice amount, and first/last invoice event timestamps.
- Replaced the PM dashboard treatment/payment readiness placeholder with an
  `available` DTO carrying the aggregate fields.
- Updated the Project Manager UI card to render the aggregate counts and
  payment total.
- Updated MSW fixtures and Zod schema for the expanded dashboard contract.

## Boundary

- No raw CareStack payloads are exposed.
- No procedure descriptions, tooth/surface data, notes, or clinical free text
  are exposed.
- No billing-sensitive or clinical treatment/procedure detail was stored in
  `ops`.
- No full `billing` schema/package was created.
- This slice reads only safe event fields and the allowlisted invoice `amount`
  already copied into `interaction.event.payload` by the invoice ingest path.

## Verification

- `ruff check .` — passed
- `mypy .` — passed, 262 source files
- `PATH=.venv/bin:$PATH make test` — passed, 831 tests
- `SECRET_KEY=dev-secret DATABASE_URL=postgresql+asyncpg://fusion:fusion@127.0.0.1:5434/fusion REDIS_URL=redis://127.0.0.1:6380/0 ../../.venv/bin/alembic check` from `packages/db` — passed, no new upgrade operations detected
- `npm run typecheck` in `apps/web` — passed
- `npm run lint` in `apps/web` — passed

## Status

Merged on `main` in commit `5ba9c01`. Linear ENG-257 is Done.

## Risks

- This is intentionally an aggregate-only v1. AR-like risk flags remain `null`
  until a separate permissioned billing/read model defines risk thresholds.
- Location and lead-source filters do not apply to this event-only aggregate
  slice yet because treatment/invoice events do not carry location or lead
  projection refs.

## Suggested Next Task

- Decide whether AR risk should be a follow-up issue or folded into a
  permissioned billing-domain design.

## Do-not-merge Conditions

- Do not merge if any dashboard response includes raw CareStack payloads,
  clinical free text, procedure descriptions, tooth/surface data, or patient
  identifiers inside the treatment/payment aggregate.
