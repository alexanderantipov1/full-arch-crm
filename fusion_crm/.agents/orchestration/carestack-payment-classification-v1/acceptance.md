# Acceptance — ENG-283

- [ ] `CareStackAccountingTransactionIngestService` classifies by transactionCode:
      PATIENTPAYMENTS/INSURANCEPAYMENTS → payment_recorded; PATPAYMENTAPPLIED/
      INSPAYMENTAPPLIED → payment_applied; PATIENTPAYMENTSDELETE/refund/isReversed
      → payment_reversed/payment_refunded; other folios → no event.
- [ ] New Alembic revision adds EVENT_KIND `payment_applied` to the CHECK
      constraint; models.py/schemas.py/_KIND_VERB/interaction CLAUDE.md updated to
      match (alembic check clean). Working downgrade.
- [ ] Backfill (migration UPDATE): existing payment_recorded events whose raw
      transactionCode is PATPAYMENTAPPLIED/INSPAYMENTAPPLIED → payment_applied;
      PATIENTPAYMENTSDELETE → payment_reversed; PATIENTPAYMENTS/INSURANCEPAYMENTS
      stay. Idempotent; re-run no-op. Append-only exception (decision-log).
- [ ] Aggregate: collected_total = sum(payment_recorded) − sum(payment_refunded +
      payment_reversed); payment_applied excluded; payment_event_count = recorded.
- [ ] PM Payments page: payment_applied rows hidden by default + "Show applied/all"
      toggle; rows labeled by type (Payment/Applied/Refund/Reversal).
- [ ] No PHI. Read-only. Verify green: lint, mypy, test, alembic check + round-trip;
      web lint/tsc/test.
- [ ] After local upgrade: Collected ≈ $11,698. Tests: code→kind, net aggregate,
      backfill reclassification, FE toggle.
- [ ] Report at `reports/ENG-283-worker-report.md`.
