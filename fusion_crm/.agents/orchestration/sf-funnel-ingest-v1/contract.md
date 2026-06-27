# Contract — sf-funnel-ingest-v1

## Invariants that must not drift

- `ingest.raw_event` stays append-only in semantics: rows are inserted or
  skipped, never updated. The cleanup script is a one-off data repair, not
  a runtime path.
- No schema migrations in ENG-381. Watermark + change-guard are code-level;
  existing indexes are sufficient (external_id, source, received_at).
- Repositories stay data-only; change-detection decisions live in the
  ingest services.
- Provider API usage may only DECREASE (watermark narrows SOQL/API windows).
- Deep-backfill lanes (ENG-351 pattern) keep ignoring watermarks by design.
- `payment_summary.snapshot` semantics change is an approved owner decision:
  "Last snapshot" surfaces become "last change/write" timestamps.
- Do not touch files owned by the parallel Codex session:
  `packages/agent_runtime/*`, `packages/integrations/openai/*`,
  `apps/web/package.json`, `apps/web/package-lock.json`,
  `tests/agent_runtime/*`.

## Interfaces

- Reuse `IngestService.max_payload_watermark(event_type, watermark_key)`.
- New repo helper for batch latest-modified lookup must live in
  `packages/ingest/repository.py` and be covered by tests.
