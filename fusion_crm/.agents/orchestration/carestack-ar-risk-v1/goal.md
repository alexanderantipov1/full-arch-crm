# Goal — PM dashboard AR-risk count (ENG-266)

Populate `DashboardTreatmentPaymentsOut.ar_risk_count` (today hard-wired to
`None`) from already-ingested CareStack payment-summary balances. No new
ingestion, no new schema.

AR-risk = patients whose LATEST `carestack.payment_summary.snapshot`
`balanceDuePatient` exceeds a documented threshold (module-level constant,
tunable). Count per tenant, latest snapshot per patient only.

Surface the count on the PM dashboard treatment/payments widget. Linear: ENG-266.
