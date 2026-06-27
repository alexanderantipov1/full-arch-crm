# Lessons — carestack-payment-classification-v1

- folioType is too coarse for payment semantics — double-entry puts both the
  received credit and the applied debit on the same folio. Classify money events
  by transactionCode, not folio. "Collected" must be cash-received only, net of
  reversals; allocation/charges/adjustments are different concepts.
