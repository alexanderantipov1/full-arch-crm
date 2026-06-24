# Lessons — interaction-event-idempotency-v1

- raw_event idempotency does NOT imply timeline-event idempotency. Any
  capture-then-emit pipeline needs a dedup key on the emitted row too, or
  scheduled re-pulls multiply it.
