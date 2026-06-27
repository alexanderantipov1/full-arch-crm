# ENG-411 Worker Report

- Task id: ENG-411
- Linear issue: ENG-411
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-411/manager-analytics-read-model-quality-metrics
- Title: Manager Analytics Read-Model Quality Metrics
- Role: worker
- Agent: codex/read-model-quality
- Session id: 8ae800e9213a
- Branch: codex/eng-411-manager-analytics-read-model-quality-metrics
- Worktree: /private/tmp/fusion-crm-eng-411-read-model-quality-metrics
- Allowed scope: bugfix
- Report timestamp: 2026-06-12T18:49:55Z
- Orchestrator review update: 2026-06-12T23:47:00Z
- PR-ready verification update: 2026-06-13T21:11:00Z

## Summary

Implemented explicit aggregate read-model data-quality evidence for manager analytics and wired it into Agent Runtime answer eligibility and audit summaries.

The tool layer still calls services only. No raw SQL or direct database access was added to agents/tools, no row-level PHI was exposed, no `.env*` files or shipped Alembic revisions were edited, and no commit/push/destructive command was run.

## Changed Files

- `packages/ops/repository.py`
- `packages/ops/service.py`
- `packages/interaction/repository.py`
- `packages/interaction/service.py`
- `packages/tools/analytics_tools.py`
- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `apps/web/tests/unit/schemas.test.ts`
- `tests/tools/test_analytics_tools.py`
- `tests/ops/test_service.py`
- `tests/interaction/test_service.py`
- `tests/agent_runtime/test_service.py`
- `.agents/orchestration/manager-analytics-read-model-quality-metrics/reports/ENG-411-worker-report.md`

## What Changed

- Added service-owned aggregate quality counters for lead-backed read models:
  `identity_linkage_coverage`, `source_attribution_coverage`, `unmatched_lead_count`, and `location_assigned_center_mismatch_count` where location evidence is available.
- Added service-owned aggregate billing quality counters for treatment revenue:
  `identity_linkage_coverage`, `source_attribution_coverage`, `unmatched_payment_count`, and `payment_applied_excluded_count`.
- Attached `data_quality_evidence` to `run_analytics_query` execution envelopes for approved aggregate manager analytics queries.
- Added Agent Runtime `data_quality_metrics` schema support in manager answer eligibility and answer audit summaries.
- Added Agent Runtime gating:
  - caveat metrics produce `generated_with_caveat`;
  - evidence `blockers` or metric status `blocked` produce answer posture `blocked` and skip manager answer generation.
- Added `aggregate_read_model_data_quality` audit policy decision entries so caveat/block decisions have concrete evidence refs.
- Updated web Agent Runtime schema and dev UI to parse and show quality metrics.
- Orchestrator review tightened the location mismatch metric so it is omitted when Agent Runtime has only `location_id` and has not resolved assigned-center location needles. This avoids presenting a false `0` for a metric that was not computable from the supplied evidence.
- PR-ready pass fast-forwarded the branch onto latest `origin/main` at `f2d2d26` (ENG-412 raw_event indexes) and added tenant-isolation sweep resolvers for the new repository read methods.

## Tests Run

- `uv run --extra dev python -m pytest tests/tools/test_analytics_tools.py tests/ops/test_service.py::test_lead_read_model_quality_evidence_reports_coverage_metrics tests/interaction/test_service.py::test_treatment_payment_quality_evidence_reports_payment_metrics -q` — passed.
- `uv run --extra dev python -m pytest tests/agent_runtime/test_service.py::test_agent_runtime_generates_with_caveat_for_aggregate_quality_evidence tests/agent_runtime/test_service.py::test_agent_runtime_blocks_answer_for_quality_metric_blocker tests/agent_runtime/test_answer_schemas.py -q` — passed.
- `uv run --extra dev ruff check packages/ops/repository.py packages/ops/service.py packages/interaction/repository.py packages/interaction/service.py packages/tools/analytics_tools.py packages/agent_runtime/schemas.py packages/agent_runtime/service.py tests/tools/test_analytics_tools.py tests/ops/test_service.py tests/interaction/test_service.py tests/agent_runtime/test_service.py` — passed.
- `uv run --extra dev mypy packages/ops/repository.py packages/ops/service.py packages/interaction/repository.py packages/interaction/service.py packages/tools/analytics_tools.py packages/agent_runtime/schemas.py packages/agent_runtime/service.py tests/tools/test_analytics_tools.py tests/ops/test_service.py tests/interaction/test_service.py tests/agent_runtime/test_service.py` — passed.
- `npm ci` in `apps/web` — completed; npm reported existing dependency deprecation/vulnerability warnings.
- `npm run typecheck` in `apps/web` — passed.
- `npm run test -- --run tests/unit/schemas.test.ts` in `apps/web` — passed.
- `uv run --extra dev python -m pytest tests/tools/test_analytics_tools.py tests/tools/test_manager_chat_tools.py tests/ops/test_service.py::test_lead_read_model_quality_evidence_reports_coverage_metrics tests/interaction/test_service.py::test_treatment_payment_quality_evidence_reports_payment_metrics tests/agent_runtime/test_service.py::test_agent_runtime_generates_with_caveat_for_aggregate_quality_evidence tests/agent_runtime/test_service.py::test_agent_runtime_blocks_answer_for_quality_metric_blocker tests/agent_runtime/test_answer_schemas.py -q` — passed.
- `git diff --check` — passed.
- Orchestrator review rerun after location-metric correction:
  - `uv run --extra dev python -m pytest tests/ops/test_service.py::test_lead_read_model_quality_evidence_reports_coverage_metrics tests/ops/test_service.py::test_lead_read_model_quality_evidence_omits_unresolved_location_metric tests/tools/test_analytics_tools.py tests/agent_runtime/test_service.py::test_agent_runtime_generates_with_caveat_for_aggregate_quality_evidence tests/agent_runtime/test_service.py::test_agent_runtime_blocks_answer_for_quality_metric_blocker tests/agent_runtime/test_answer_schemas.py -q` — 9 passed.
  - `uv run --extra dev ruff check packages/ops/repository.py packages/ops/service.py packages/interaction/repository.py packages/interaction/service.py packages/tools/analytics_tools.py packages/agent_runtime/schemas.py packages/agent_runtime/service.py tests/tools/test_analytics_tools.py tests/ops/test_service.py tests/interaction/test_service.py tests/agent_runtime/test_service.py` — passed.
  - `uv run --extra dev mypy packages/ops/repository.py packages/ops/service.py packages/interaction/repository.py packages/interaction/service.py packages/tools/analytics_tools.py packages/agent_runtime/schemas.py packages/agent_runtime/service.py tests/tools/test_analytics_tools.py tests/ops/test_service.py tests/interaction/test_service.py tests/agent_runtime/test_service.py` — passed.
  - `npm run typecheck` in `apps/web` — passed.
  - `npm run test -- --run tests/unit/schemas.test.ts` in `apps/web` — 19 passed.
  - `git diff --check` — passed.
- PR-ready verification after fast-forward to latest `origin/main`:
  - `make lint` — passed.
  - `mypy .` — passed, 374 source files.
  - `SECRET_KEY=dev-secret DATABASE_URL=postgresql+asyncpg://fusion:fusion@127.0.0.1:5434/fusion REDIS_URL=redis://127.0.0.1:6380/0 PATH=/Users/eduardkarionov/Desktop/Fusion_crm/.venv/bin:$PATH make test` — 1505 passed.
  - `SECRET_KEY=dev-secret DATABASE_URL=postgresql+asyncpg://fusion:fusion@127.0.0.1:5434/fusion REDIS_URL=redis://127.0.0.1:6380/0 PATH=/Users/eduardkarionov/Desktop/Fusion_crm/.venv/bin:$PATH cd packages/db && alembic check` — passed, no new upgrade operations detected. Alembic emitted compare warnings for ENG-412 trigram operator-class indexes and skipped them as equal.
  - `npm run typecheck` in `apps/web` — passed.
  - `npm run test -- --run tests/unit/schemas.test.ts` in `apps/web` — 19 passed.
  - `git diff --check` — passed.

## Verification Result

Focused verification and the full requested gate passed after the PR-ready sync to latest `origin/main`.

## Risks

- `location_assigned_center_mismatch_count` only has concrete support when location-match evidence is supplied to the service. Agent Runtime does not currently resolve `location_id` into assigned-center needles, so ordinary manager analytics calls will not infer this metric speculatively.
- `unmatched_payment_count` is scoped to billing event provider attribution evidence inside `interaction.event`, not cross-domain payment-to-lead attribution, because `interaction` and `ops` cannot import each other under current architectural rules.
- `npm ci` surfaced existing npm audit warnings; dependency upgrades are outside ENG-411 scope.

## Blockers

None.

## Remaining Questions

- Should a follow-up add a service-owned cross-domain attribution projection for payment-to-lead/source quality, instead of approximating that inside either `ops` or `interaction`?
- Should Agent Runtime resolve manager-provided `location_id` to location-match needles before calling read-model services so location mismatch evidence can be populated for location-scoped manager questions?

## Do-Not-Merge Conditions

- Do not merge if product expects `unmatched_payment_count` to mean payment-to-lead attribution rather than provider transaction attribution; that needs a separate approved read-model/projection owner.
