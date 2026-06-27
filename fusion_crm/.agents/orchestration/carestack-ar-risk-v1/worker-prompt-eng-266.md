You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-266
(https://linear.app/fusion-dental-implants/issue/ENG-266). You run in an
isolated git worktree on your own branch. Implement → verify → write a report.
Do NOT touch `main`, do NOT push, do NOT open a PR. Commit to YOUR worktree
branch only once verification is green; the Orchestrator integrates.

## Mission (small slice — no new ingestion, no new schema)
Populate `DashboardTreatmentPaymentsOut.ar_risk_count` (currently hard-wired to
`None`) so the PM dashboard shows an accounts-receivable risk signal, from
already-ingested CareStack payment-summary snapshots.

## Read first
- Root `CLAUDE.md`, `packages/CLAUDE.md`, `packages/ingest/CLAUDE.md`,
  `apps/api/CLAUDE.md`, and the mission spec at
  `.agents/orchestration/carestack-ar-risk-v1/`.
- The pattern to extend: `IngestRepository.sum_latest_payment_summary_balances`
  (latest `carestack.payment_summary.snapshot` per patient via MAX(received_at)
  per external_id) and `IngestService.latest_payment_summary_balances`, both
  added in the merged surface slice. Dashboard wiring lives in
  `apps/api/routers/dashboard.py` (`DashboardTreatmentPaymentsOut`,
  `ar_risk_count` is set to `None` around line 517).

## Task
1. **Define AR-risk** = a patient whose LATEST payment-summary snapshot
   `balanceDuePatient` is strictly greater than a module-level threshold
   constant (e.g. `AR_RISK_BALANCE_THRESHOLD`). Pick a sensible default (a
   positive dollar amount), document it, and keep it easy to tune. State the
   inclusive/exclusive boundary rule in the report.
2. **Ingest read:** extend the latest-balances aggregate (or add a sibling) to
   also return `ar_risk_count` = number of patients above the threshold,
   tenant-scoped, using ONLY the latest snapshot per patient. Reuse the existing
   MAX(received_at)-per-external_id subquery so you don't double-count snapshots.
3. **Dashboard:** populate `ar_risk_count` in the PM endpoint (only when the
   provider filter is `None`/`carestack`, matching the existing `outstanding_*`
   logic). Remove the hard-coded `None`.
4. **Frontend (apps/web):** show the AR-risk count on the treatment/payments
   widget (e.g. "N patients at AR risk"); update the Zod schema if needed and
   the MSW fixture so dev-mode parsing stays green.

## Hard constraints
- READ-ONLY. No new CareStack call. No new DB schema/migration.
- No PHI in the dashboard response or logs (count + threshold only; never patient
  identifiers or balances per patient).
- Cross-domain imports per `packages/CLAUDE.md`. `except Exception` only. English only.

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check` all green.
2. Commit to your worktree branch only (not main) once green.
3. Write `.agents/orchestration/carestack-ar-risk-v1/reports/ENG-266-worker-report.md`
   per the worker-report contract (changed files, chosen threshold + boundary
   rule, tests, verification status, risks, do-not-merge conditions).
4. If you hit a structural wall, STOP and write `Needs decision:` rather than guessing.
