# Contract — ENG-306

## Person/patient detail page

Gains a `FinancialSummary` block:
- Renders four currency values: **Billed**, **Adjustments**, **Paid**,
  **Balance**, with a small label per value.
- Renders a snapshot timestamp line under the block (`Last balance snapshot:
  <relative>` or `No balance snapshot yet`).
- Source: `payment-summary` snapshot per CareStack patient_id (for Paid +
  Balance, authoritative); accounting journal deduped by `external_id` (for
  Billed + Adjustments, gross context).
- Empty state: numbers show `"—"`, timestamp line shows the "no snapshot
  yet" message; the block is rendered, not hidden.

## /project-manager/payments

Each row gains a compact balance pill next to the patient name (using the
established Badge pattern). Pill content = balance from latest snapshot;
`"—"` when absent.

## Backend (optional, only if needed)

A per-patient variant of `LatestPaymentSummaryBalancesOut` (or its
repository method) returning one row by CareStack `patient_id` from the
latest snapshot, or `None`. Reuses the existing select shape; no schema
change; no new ORM model.

## Hard limits

- NO PHI in logs (patient_id, counts, no names/DOB/notes/clinical text).
- Strict TS in apps/web.
- Frontend pattern parity: mirror existing Card / Badge / Tailwind patterns
  on the page.
- Currency formatting consistent with the rest of the app.
- No pagination regression on the Payments page.
- NO commit to `main`, NO push, NO PR — Orchestrator integrates.
