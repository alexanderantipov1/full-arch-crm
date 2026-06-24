# Lessons — carestack-payment-strict-classify-v1

- Classify money events by an explicit code ALLOWLIST, not by overrides on top of
  a broad set. An override (isReversed) must be scoped to the allowed set, or it
  drags unrelated rows in.
- Verify the headline number a change targets (Collected), not an intermediate
  (recorded sum). Green unit tests don't prove the aggregate is semantically right
  on real data.
