# Goal — classify CareStack payments by transactionCode (ENG-283)

Collected is ~3.3× too high because we map by folioType (PATIENTCREDIT), which
catches BOTH the payment-received credit AND the payment-applied debit of
CareStack's double-entry. Real collected ≈ $11,698; shown $38,178.

Fix: classify by `transactionCode`:
- PATIENTPAYMENTS, INSURANCEPAYMENTS → `payment_recorded` (real cash → Collected)
- PATPAYMENTAPPLIED, INSPAYMENTAPPLIED → new kind `payment_applied` (excluded from Collected, hidden on page by default)
- PATIENTPAYMENTSDELETE / refund / isReversed → `payment_reversed`/`payment_refunded`
- charges/adjustments → raw-only (no event)

Migration: add `payment_applied` kind + reclassify existing events by raw
transactionCode. Aggregate: Collected = recorded − refunded − reversed.
Linear: ENG-283.
