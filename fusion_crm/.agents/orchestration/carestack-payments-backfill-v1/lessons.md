# Lessons — carestack-payments-backfill-v1

- A historical backfill against a rate-limited vendor must be throttled, backoff-
  aware, and resumable — and its tests must mock the client so development itself
  never trips the rate limit.
