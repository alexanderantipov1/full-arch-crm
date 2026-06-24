# Decision Log — carestack-payment-location-v1

- 2026-05-30 | Handoff: orchestrator/claude-code -> worker/claude-code for ENG-267.
- 2026-05-30 | Storage decision: location_id on event PAYLOAD (no migration), consistent with amount. Column add is the escalation path (Needs decision:) if payload filtering proves unworkable.
- 2026-05-30 | Scope decision: Outstanding/AR-risk stay tenant-wide — payment_summary snapshots carry no location.
