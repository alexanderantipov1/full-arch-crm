# Acceptance — ENG-284

- [ ] Emission: strict payment-code allowlist. PATIENTPAYMENTS/INSURANCEPAYMENTS →
      payment_recorded; PATPAYMENTAPPLIED/INSPAYMENTAPPLIED → payment_applied;
      PATIENTPAYMENTSDELETE/refunds → payment_reversed/refunded. Any other code →
      NO event (even isReversed=true). isReversed flips ONLY a payment code to reversed.
- [ ] Corrective migration (new revision): for interaction.event with payment kinds,
      join raw_event transactionCode → reclassify to the correct kind if code is a
      payment code; DELETE the event if code is non-payment. Idempotent; re-run no-op;
      downgrade no-op (documented). Append-only exception (decision-log).
- [ ] Aggregate keeps collected_total = sum(recorded) − sum(refunded + reversed),
      now correct because reversed/refunded hold only real payment reversals/refunds.
- [ ] No PHI. Read-only. Verify green: lint/mypy/test/alembic check + round-trip;
      web lint/tsc/test.
- [ ] After local upgrade: no payment event has a non-payment transactionCode;
      payment_reversed = real reversals only; collected_total ≈ $11,538 (POSITIVE).
- [ ] Tests: allowlist mapping (isReversed on non-payment → no event), corrective
      migration (delete spurious + reclassify), aggregate positive.
- [ ] Report at `reports/ENG-284-worker-report.md`.
