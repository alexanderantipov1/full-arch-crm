# Contract — full-fidelity-ingestion-v1

## Shared contracts touched (require review before integration)

- **`ingest` schema** — new schema-registry table + Alembic migration. Shared
  with every ingest service. Block A owns it; B/C/D consume it.
- **Salesforce client** (`packages/integrations/salesforce/client.py`) — new
  `describe` + Tooling-API methods. Additive; no removal of existing methods.
- **SF ingest services** (`packages/ingest/sf_*_service.py`) — static
  `_SF_*_PROJECTION` constants replaced by the dynamic builder. Behavior change:
  raw payloads widen to all queryable fields. Domain mapping (`ops.lead.extra`
  etc.) stays unchanged — completeness is raw-only.
- **`sync_run.meta`** — gains a drift-event surface. Additive key.

## Invariants preserved

- Capture-then-route: raw written verbatim before any mapping (ingest/CLAUDE.md).
- No domain projection changes required by widening raw.
- PHI boundaries unchanged: raw stays gated; completeness raises the guard bar.
- Repositories data-only; services hold logic; migrations immutable once shipped.

## Integration mode

Single mission branch `eng-425-full-fidelity-ingestion-v1`; blocks bundled per
solo-dev PR-granularity rule, migrations chained on the same branch. Contract-
changing → cross-runtime review (prefer a Codex reviewer) before merge.
