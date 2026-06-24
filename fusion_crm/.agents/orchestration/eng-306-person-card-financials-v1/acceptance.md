# Acceptance — ENG-306

## Person card

- [ ] Person/patient detail route renders a financial summary block with four
      numbers + a `last snapshot at <ts>` line (relative time): **Billed**,
      **Adjustments**, **Paid**, **Balance**.
- [ ] **Paid** = `appliedPatientPayment + appliedInsPayments` from latest
      `payment-summary` snapshot for this CareStack patient_id.
- [ ] **Balance** = `balanceDuePatient + balanceDueInsurance` from latest
      snapshot.
- [ ] **Billed** = Σ `PROCEDURECOMPLETED` debit on the patient's accounting
      rows, deduped by `external_id` (latest `received_at`).
- [ ] **Adjustments** = Σ `PATIENTADJUSTMENT` + `FEEUPDATION` (debit − credit
      or net), deduped by `external_id`.
- [ ] Empty state when no snapshot: each number shows `"—"`, the timestamp
      line shows `"no balance snapshot yet"` (or equivalent), and the block
      is still rendered (not hidden) so the user knows the feature exists.
- [ ] Currency formatting consistent with other monetary displays in the app
      (USD, 2 decimals, $-prefix).

## Payments page badge

- [ ] Each row on `/project-manager/payments` has a compact balance pill
      next to the patient name (or in the patient column if that's the
      established pattern), sourced from the same per-patient authoritative
      snapshot.
- [ ] Pill empty state: `"—"` when no snapshot.
- [ ] No pagination regression; no new N+1.

## Backend (only if needed)

- [ ] If the existing aggregate is tenant-wide only, add a per-patient
      variant (single CareStack `patient_id` input → one row from latest
      snapshot, or `None`). Reuse the existing query shape; do NOT
      re-derive from accounting.

## Verify

- [ ] `cd apps/web && npm run lint && npx tsc --noEmit && npm run test` green.
- [ ] If backend touched: `make lint && mypy . && make test &&
      cd packages/db && alembic check` green.
- [ ] Worker report at `.agents/orchestration/current/reports/ENG-306-worker-report.md`.
- [ ] Commit to worker's worktree branch only; NO push, NO PR; Orchestrator
      integrates.
