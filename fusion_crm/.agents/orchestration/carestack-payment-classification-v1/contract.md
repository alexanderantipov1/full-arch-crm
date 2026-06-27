# Contract — carestack-payment-classification-v1

- transactionCode → kind: {PATIENTPAYMENTS, INSURANCEPAYMENTS} → payment_recorded;
  {PATPAYMENTAPPLIED, INSPAYMENTAPPLIED} → payment_applied (NEW);
  {PATIENTPAYMENTSDELETE, refunds} / isReversed → payment_reversed|payment_refunded;
  else → no event.
- New EVENT_KIND `payment_applied` (CHECK-constraint migration). Existing events
  reclassified by raw transactionCode (migration UPDATE).
- Aggregate collected_total = sum(payment_recorded) − sum(payment_refunded +
  payment_reversed); payment_applied excluded.
- Payments page hides payment_applied by default (+ "show all" toggle), labels type.
