# Contract — carestack-payment-strict-classify-v1

- Payment events ONLY for payment transactionCodes (allowlist):
  PATIENTPAYMENTS/INSURANCEPAYMENTS→recorded, PATPAYMENTAPPLIED/INSPAYMENTAPPLIED→applied,
  PATIENTPAYMENTSDELETE/refunds→reversed/refunded. Else no event. isReversed flips
  only payment codes to reversed.
- Migration: payment-kind events with non-payment code → DELETE; payment code →
  reclassify to mapped kind. Idempotent.
- collected_total = sum(recorded) − sum(refunded + reversed) (now correct).
  Expected ≈ $11,538.
