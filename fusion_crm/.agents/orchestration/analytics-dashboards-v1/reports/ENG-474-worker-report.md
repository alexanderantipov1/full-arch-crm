# Worker Report — ENG-474 (Calls dashboard shell)

- **Task:** ENG-474 — Analytics: Calls dashboard page (shell)
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-474
- **Role/agent:** worker / claude-code (`eng474-calls`)
- **Branch:** eng-468-analytics-dashboards · commit `85387dc`
- **Verified by orchestrator** (ruff + mypy + pytest + parity, independently).

## Changed/created files
- `packages/interaction/repository.py` + `service.py` + `schemas.py` — new call-event count read.
- `apps/api/routers/dashboard.py` — `GET /dashboard/analytics/calls` + CallsAnalytics* models (reuses MarketingKpiOut).
- `apps/web/lib/api/schemas/callsAnalytics.ts` (+ index export), `hooks/useCallsAnalytics.ts`, `app/(staff)/analytics/calls/page.tsx`, `AppShell.tsx` (Calls nav item).
- `tests/interaction/test_call_volume.py` (new, mirrors package layout).
- Orchestrator also fixed a pre-existing UP037 lint (forward-ref quotes) in `packages/interaction/schemas.py:359`, surfaced by touching the file; safe under `from __future__ import annotations` (141 interaction tests pass).

## Endpoint + DTO
`GET /dashboard/analytics/calls?start_date&end_date` → `CallsAnalyticsOut { window{start_date,end_date}, connected:bool, kpis[MarketingKpiOut], pending:list[str] }`. Zod parity confirmed.

## Not-connected (pending Phase 3 comms ingest)
agent scorecard, connected/voicemail/missed, recordings, transcripts, sentiment, QA scores. Empty state when no call events exist (no fake zeros).

## Verification (orchestrator-run)
- ruff PASS (after the UP037 autofix); mypy PASS (6 files); pytest: call-volume 3 PASS + interaction suite 141 PASS.
