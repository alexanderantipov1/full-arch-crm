# ENG-256 Worker Report

## Task

- Linear: ENG-256
- Title: Classify CareStack treatment/payment data and define safe dashboard aggregates
- Role: Orchestrator self-execute
- Agent: Codex
- Branch: main
- Worktree: current checkout

## Changed Files

- `.agents/orchestration/pm-analyst-dashboard-v1/carestack-treatment-payment-classification.md`
- `.agents/orchestration/pm-analyst-dashboard-v1/decision-log.md`
- `.agents/orchestration/pm-analyst-dashboard-v1/ownership.yaml`

## Sources Reviewed

- `docs/integrations/carestack/resources/payment-summary.md`
- `docs/integrations/carestack/resources/treatment-plans.md`
- `docs/integrations/carestack/sync/invoices.md`
- `docs/integrations/carestack/sync/treatment-procedures.md`
- `docs/integrations/carestack/sync/existing-treatment-procedures.md`

## Result

Created initial classification:

- payment summary and invoices: billing-sensitive / PHI-adjacent;
- treatment plans and treatment procedures: PHI;
- dashboard first slice should expose aggregates, not raw rows;
- likely need a billing-aware service boundary for payment aggregates and a
  PHI-aware boundary for treatment/procedure details.

Defined safe aggregate candidates:

- treatment totals;
- accepted amounts;
- production/collection/payment totals;
- patient/insurance balance;
- unapplied credits;
- first/last payment;
- AR-like risk flag.

## Verification

- Not code-bearing.
- Reviewed against local CareStack integration docs.

## Status

In review. Implementation should not proceed to ENG-257 until the domain/service
boundary is accepted.
