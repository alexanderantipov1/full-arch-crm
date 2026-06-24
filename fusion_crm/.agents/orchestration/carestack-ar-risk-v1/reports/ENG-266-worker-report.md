# ENG-266 — Worker Report

- **Task:** ENG-266 — PM dashboard AR-risk count from CareStack outstanding balances
- **Linear:** [ENG-266](https://linear.app/fusion-dental-implants/issue/ENG-266/pm-dashboard-ar-risk-count-from-carestack-outstanding-balances)
- **Role / agent:** worker / claude-code
- **Branch:** `eng-266-eng-266`
- **Worktree:** `/Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/carestack-ar-risk-v1/worktrees/ENG-266`
- **Scope:** small slice — extend an existing aggregate, surface one new
  count on the PM dashboard; no new ingestion, no schema, no migration.

## What changed

### AR-risk definition (single source of truth)

- **Constant:** `AR_RISK_BALANCE_THRESHOLD` in
  `packages/ingest/service.py` (module-level), default **`500.0`**
  dollars.
- **Boundary rule:** **strictly greater than** the threshold. A
  patient with `balanceDuePatient == 500.0` is **NOT** counted;
  `balanceDuePatient == 500.01` IS counted. ("Above the line, not on
  it.") Encoded as `CASE WHEN balance_patient > :threshold THEN 1
  ELSE 0 END` in the repository and asserted by
  `tests/ingest/test_payment_summary_repository_sql.py`
  (`> 500.0` present, `>= 500.0` absent).
- **Rationale (default):** $500 is the order-of-magnitude where
  partial-payment plans stall; it filters out small copay overruns
  while still surfacing real backlog. Tunable in one place — no
  schema or migration to touch.

### Ingest read

- `packages/ingest/repository.py` —
  `sum_latest_payment_summary_balances` gained a required
  `ar_risk_threshold: float` keyword arg. The latest-snapshot-per-
  patient subquery (`MAX(received_at)` per `external_id`,
  `source = 'carestack'`, `event_type =
  'carestack.payment_summary.snapshot'`, tenant-scoped via
  `for_tenant`) is reused **verbatim** — the new aggregate column is
  a `SUM(CASE WHEN balance_patient > threshold THEN 1 ELSE 0 END)`
  over the SAME `latest_rows` subquery, so no patient is double-
  counted across snapshots.
- `packages/ingest/service.py` —
  `IngestService.latest_payment_summary_balances` passes
  `AR_RISK_BALANCE_THRESHOLD` to the repo and surfaces
  `ar_risk_count` plus `ar_risk_threshold` on the existing DTO.
- `packages/ingest/schemas.py` — `LatestPaymentSummaryBalancesOut`
  gained `ar_risk_count: int = 0` and `ar_risk_threshold: float = 0.0`.

### Dashboard wiring

- `apps/api/routers/dashboard.py` — `DashboardTreatmentPaymentsOut.ar_risk_count`
  is no longer hard-coded `None`. It is populated from
  `outstanding_balances.ar_risk_count` when the existing
  `source_provider in (None, "carestack")` gate already pulled the
  aggregate; it stays `None` on a Salesforce-only view so the widget
  can render an explicit "n/a" (vs a misleading `0`). The dashboard
  response carries only the count — no patient identifiers, no
  per-patient balances.

### Frontend

- `apps/web/lib/api/schemas/dashboard.ts` — schema already declared
  `ar_risk_count: z.number().int().nonnegative().nullable()`. No
  change required; the backend now satisfies the nullable contract
  with a real number for CareStack views.
- `apps/web/lib/msw/handlers.ts` — fixture flipped from
  `ar_risk_count: null` to `ar_risk_count: 2` so dev-mode parsing
  and the new badge both render.
- `apps/web/app/(staff)/project-manager/page.tsx` — Treatment &
  payments card now shows a `destructive`-variant badge "N patients
  at AR risk" when `ar_risk_count` is a number. Renders nothing for
  the Salesforce-only `null` case.

## Files touched

```
apps/api/routers/dashboard.py                       (+5, -1)
apps/web/app/(staff)/project-manager/page.tsx       (+5, -0)
apps/web/lib/msw/handlers.ts                        (+1, -1)
packages/ingest/repository.py                       (+17, -2)
packages/ingest/schemas.py                          (+10, -1)
packages/ingest/service.py                          (+26, -5)
tests/api/test_dashboard_pm.py                      (+117, -0)
tests/ingest/test_latest_payment_summary_balances.py (+50, -9)
tests/ingest/test_payment_summary_repository_sql.py (NEW, +138)
```

## Tests

### New test files / cases

- `tests/ingest/test_payment_summary_repository_sql.py` (new) —
  compiles the aggregate query against the Postgres dialect with
  literal binds and asserts:
  - tenant scoping (`tenant_id` filter present);
  - source + event_type filters
    (`carestack`, `payment_summary.snapshot`);
  - latest-snapshot-per-patient (`MAX(`, `external_id`, `GROUP BY`);
  - strict `>` threshold rule (`> 500.0` present, `>= 500.0` absent);
  - all four aggregate labels surface
    (`balance_due_patient`, `balance_due_insurance`,
    `patient_count`, `ar_risk_count`);
  - non-default threshold flows into SQL (catches dead-config
    regressions).

- `tests/ingest/test_latest_payment_summary_balances.py` (extended) —
  added `test_ar_risk_count_surfaces_from_repo` and
  `test_ar_risk_threshold_is_positive_dollar_amount`; existing tests
  updated to include `ar_risk_count` in mocked repo rows and assert
  the threshold kwarg is passed through.

- `tests/api/test_dashboard_pm.py` (extended) — added
  `test_pm_dashboard_surfaces_ar_risk_count_for_carestack_view`
  (CareStack provider populates the count, response carries no
  `balanceDuePatient` / `patientId` / `person_uid`) and
  `test_pm_dashboard_omits_ar_risk_count_for_salesforce_only_view`
  (Salesforce-only filter does not call the ingest aggregate;
  `ar_risk_count` is `null`).

### Verification status

| Gate | Command | Result |
|---|---|---|
| Lint | `make lint` (`ruff check .`) | **PASS** — all checks passed |
| Types | `mypy .` | **PASS** — no issues in 269 source files |
| Tests | `make test` (`pytest -q`) | **PASS** — **900 passed** in 14.46s |
| Migrations | `cd packages/db && alembic check` | **PASS** — no new upgrade operations detected |

(Test/alembic runs use the test env vars from `.env.example` —
`SECRET_KEY`, `DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`,
`ENVIRONMENT=test` — supplied inline because `.env` is not allowed
to be edited.)

## Risks

- **Threshold default is unvalidated against finance data.** $500 is
  a reasoned guess; once finance gives a calibrated cut-off, tune
  `AR_RISK_BALANCE_THRESHOLD` in `packages/ingest/service.py` — one
  line, no migration. The dashboard DTO already carries
  `ar_risk_threshold` so the widget can be extended to display the
  cut-off if/when product wants.
- **No live-DB integration test for the aggregate.** The repo's SQL
  shape is locked in via dialect-compile assertions; the actual
  Postgres execution (CASE evaluation, NULL handling for missing
  `balanceDuePatient`, snapshot ordering) is not exercised by a
  Postgres fixture (the suite has no `ingest`-schema fixture yet).
  The service-level mocked tests cover wiring; a future
  Postgres-backed integration test should pin
  above/below/latest-per-patient semantics end-to-end.
- **Provider-filter gating mirrors the existing
  `outstanding_total` rule.** A future change to that rule must
  update `ar_risk_count` in lockstep — both populate from the same
  `outstanding_balances` object and would silently drift if one is
  wired separately.

## PHI / cross-domain compliance

- The dashboard response carries **counts and one threshold only** —
  no patient identifiers, no per-patient balances, no payload echo.
  Asserted in
  `test_pm_dashboard_surfaces_ar_risk_count_for_carestack_view` by
  scanning the rendered JSON for `balanceDuePatient`, `patientId`,
  and `person_uid`.
- No new logging was added; no PHI keys are emitted from the new
  code path.
- Cross-domain imports respected per `packages/CLAUDE.md`: only
  `packages.core` and `packages.ingest` internals are touched on the
  ingest side; the dashboard router already imports `IngestService`.
- `except Exception` rule honored — no broader exception handlers
  introduced.
- English only.

## Blockers / questions

None. No `Needs decision:` markers.

## Suggested next task

If the orchestrator wants a follow-up, the natural ones are:

1. **Surface the threshold on the widget.** The schema already
   carries it on the ingest DTO; one more field on
   `DashboardTreatmentPaymentsOut` + the matching Zod nullable +
   small page edit and the badge can read "N patients > $500 AR
   risk".
2. **Postgres-backed integration test** for
   `sum_latest_payment_summary_balances` covering above-line /
   at-line / below-line cases and a stale-snapshot-vs-fresh-snapshot
   scenario per-patient.

## Do-not-merge conditions

- Do **not** merge if the threshold constant is moved out of
  `packages.ingest.service` without updating the SQL-shape test
  (`tests/ingest/test_payment_summary_repository_sql.py`) that pins
  the `> 500.0` literal.
- Do **not** merge if the dashboard response starts emitting per-
  patient balances or identifiers — the no-PHI assertion in
  `test_pm_dashboard_surfaces_ar_risk_count_for_carestack_view`
  must stay green.
- Do **not** merge alongside a separate change that reshapes the
  `outstanding_balances` provider-filter gate without also updating
  the `ar_risk_count` wiring.
