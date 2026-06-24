# Goal — surface CareStack partial payments to timeline + dashboard

Ingest of accounting-transactions + payment-summary already lands in
`ingest.raw_event` (shipped, merged `fab2c28`). Now make partial payments
VISIBLE:

1. **Person timeline** — emit one `interaction.event` per payment ledger entry
   so a person's partial payments appear chronologically.
2. **PM dashboard** — show `collected` (from ledger payments) and `outstanding`
   (from payment-summary snapshots) on the existing treatment/payments widget.

Reuse the established enum-extend + emit pattern (migration `c1d2e3f4a5b6`).
NO new `billing` schema/domain — only widen existing `interaction.event` CHECK
constraints. Linear anchor: **ENG-257** (reopened).

## Locked decisions
- Timeline: per-payment events (folioType PATIENTCREDIT / COLLECTIONCREDIT +
  refunds/reversals). Charges and internal adjustments stay raw-only.
- Dashboard: collected from ledger payment events; outstanding/balances from
  the latest `carestack.payment_summary.snapshot` per patient.
