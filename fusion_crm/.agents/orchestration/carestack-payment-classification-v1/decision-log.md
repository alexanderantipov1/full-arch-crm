# Decision Log — carestack-payment-classification-v1

- 2026-05-30 | Handoff: orchestrator/claude-code -> worker/claude-code for ENG-283.
- 2026-05-30 | Root cause: payment classification by folioType (PATIENTCREDIT) caught both the PATIENTPAYMENTS credit (cash in) and the PATPAYMENTAPPLIED debit (allocation) of CareStack double-entry → Collected ~3.3x inflated.
- 2026-05-30 | Decision: classify by transactionCode. New kind `payment_applied` for allocation entries (shown on page, hidden by default, excluded from Collected). Collected = recorded − refunded − reversed.
- 2026-05-30 | Decision (append-only exception): migration reclassifies existing events' kind by joining raw transactionCode (UPDATE) — one-time data fix, same precedent as ENG-269/270. ENG-269 unique index includes kind; reclassify keeps rows unique (one source_external_id per kind).
