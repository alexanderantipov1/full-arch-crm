# Incidents — carestack-payment-strict-classify-v1

- 2026-05-30 | Orchestrator verification miss: merged ENG-283 on the worker's "recorded=$11,703" + green tests without checking the actual collected_total (which was negative due to the over-broad isReversed + net formula). Lesson: always verify the HEADLINE metric the change targets, not just an intermediate value.
- 2026-05-30 | Stale local arq worker (old code) re-polluted payment_recorded after ENG-283 reclassification. Lesson: restart the worker on the new code before relying on local data post-emission-change.
