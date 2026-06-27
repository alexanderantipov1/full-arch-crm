# Decision Log — pm-payments-page-v1

- 2026-05-30 | Handoff: orchestrator/claude-code -> worker/claude-code for ENG-271.
- 2026-05-30 | Product: row = person + pipeline stage + amount/type/date/location; person name -> person page; per-row "view raw" -> verbatim raw payload modal.
- 2026-05-30 | Drilldown reuses the inspector raw-payload carve-out (already ungated on prod, b412f92) — no new PHI exposure beyond inspector.
- 2026-05-30 | List includes payment_recorded + payment_refunded + payment_reversed with a type badge.
