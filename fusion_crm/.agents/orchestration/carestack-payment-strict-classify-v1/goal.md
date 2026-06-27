# Goal — strict payment-code classification (ENG-284)

ENG-283 follow-up. The isReversed override was applied to ALL codes, so reversed
charges/adjustments became payment_reversed → `collected = recorded − refunded −
reversed` went NEGATIVE (−$71,934).

Fix: a STRICT payment-code allowlist. Only PATIENTPAYMENTS/INSURANCEPAYMENTS
(→recorded), PATPAYMENTAPPLIED/INSPAYMENTAPPLIED (→applied), PATIENTPAYMENTSDELETE
/refunds (→reversed/refunded) produce payment events. Everything else
(PROCEDURECOMPLETED, PATIENTADJUSTMENT, FEEUPDATION, unknown) → NO event, even if
isReversed. isReversed only flips a PAYMENT code to reversed.

Corrective migration: reclassify payment events by code; DELETE payment events
whose code is non-payment. Then `collected ≈ $11,538` (positive). Linear: ENG-284.
