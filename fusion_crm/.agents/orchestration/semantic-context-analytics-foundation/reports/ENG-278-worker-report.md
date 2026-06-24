# Worker Report — ENG-278 Manager Analytics Read Models V1

- Task id: ENG-278
- Linear issue: ENG-278
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-278/manager-analytics-read-models-v1
- Role: orchestrator self-execute
- Agent: codex
- Branch: main
- Worktree: .
- Allowed scope: read-model contracts, tool envelope metadata, workbench docs

## Summary

Defined the first manager analytics read-model contracts and connected them to
the implemented service-computed query layer from ENG-277. V1 stays
aggregate-only and service-computed; no persisted tables, materialized views,
migrations, row-level worklists, or exports were introduced.

## Touched Files

- `.agents/orchestration/semantic-context-analytics-foundation/manager-analytics-read-models-v1.md`
- `.agents/orchestration/semantic-context-analytics-foundation/analytics-query-registry-v1.md`
- `packages/tools/analytics_tools.py`
- `apps/web/app/(staff)/dev/semantic-analytics/page.tsx`

## Implemented Read Model IDs

- `lead_conversion`
- `paid_leads`
- `consultation_followup`
- `treatment_revenue`

`lead_source_profile` is also exposed as a supporting read model for manager
source questions, but it is not one of the four ENG-278 required models.

## What Changed

- Added `read_model_id` to the `run_analytics_query` result envelope.
- Documented shared read-model response contract:
  `query_id`, `read_model_id`, data classes, definition versions, filters,
  aggregate bucket count, warnings, drilldown/export flags, and result payload.
- Mapped registry query ids to read model ids.
- Added the read-model documentation to the frontend semantic analytics
  workbench.

## Guardrails

- No direct DB access from agents.
- No raw SQL.
- No raw provider payload output.
- No PHI service access added.
- No frontend metric definitions added; frontend only renders documentation.
- Exports and row-level drilldowns remain disabled in V1.

## Tests / Checks

- `python3 -m ruff check packages/ops packages/tools tests/ops/test_service.py` — passed.
- `python3 -m mypy packages/ops packages/tools` — passed.
- `python3 -m pytest tests/ops/test_service.py -q` — passed, 16 tests.
- `cd apps/web && npm run lint && npm run typecheck` — passed.
- `curl -I -L 'http://localhost:3000/dev/semantic-analytics?doc=read-models'` — passed with `HTTP/1.1 200 OK`.

## Verification Status

- Required read model ids are defined.
- Each required read model maps to a canonical versioned query id.
- Read model contracts include data-class and semantic definition provenance.
- Workbench can display the read-model documentation.

## Risks

- Read models are not persisted. This is intentional for V1 while semantics
  stabilize.
- `paid_leads` is still based on CRM-safe source/campaign label heuristics.
- Row-level read models and exports require ENG-281 and row field allowlists.

## Suggested Next Task

ENG-280 Manager AI Chat V1, using the aggregate-only read-model/query envelope
as the planner execution target.
