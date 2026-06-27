# Goal — throttled 2026 payments backfill (ENG-285)

We only have a thin recent slice of CareStack payments (incremental + 500-cap
pull). Add an operator-triggered, RATE-LIMIT-SAFE historical backfill of
accounting-transactions (+ payment-summary) for 2026, so the dashboard shows real
per-location figures.

Hard rule: do NOT get blocked by CareStack — throttle between pages, backoff on
429/5xx, resumable via continueToken, bounded. TESTS MOCK the client (no real
calls). Reuse the existing ingest services + ENG-284 classification. Backend only,
no migration.

Run twice (decided): locally now, prod after deploy unblocks. Linear: ENG-285.
