# ENG-259 Worker Report

## Task

- Linear: ENG-259
- Title: Add Project Manager leads list with filters and search
- Role: Orchestrator self-execute
- Agent: Codex
- Branch: main
- Worktree: current checkout

## Changed Files

- `apps/api/routers/dashboard.py`
- `packages/identity/repository.py`
- `packages/identity/service.py`
- `packages/ops/repository.py`
- `packages/ops/service.py`
- `tests/api/test_dashboard_pm.py`
- `apps/web/app/(staff)/project-manager/page.tsx`
- `apps/web/app/(staff)/project-manager/leads/page.tsx`
- `apps/web/components/layout/AppShell.tsx`
- `apps/web/lib/api/hooks/useDashboard.ts`
- `apps/web/lib/api/schemas/dashboard.ts`
- `apps/web/lib/msw/handlers.ts`

## Result

Added a dedicated Project Manager leads surface at `/project-manager/leads`.
The API endpoint `GET /dashboard/pm/leads` returns individual safe lead rows
from existing canonical data: person identity summary, lead status/source,
Salesforce Lead id when available, timestamps, and source providers. Filters
cover date range, provider, lead source, status, search query, and limit.

## Verification

- `.venv/bin/python -m pytest tests/api/test_dashboard_pm.py -q`
- `ruff check apps/api/routers/dashboard.py packages/identity/repository.py packages/identity/service.py packages/ops/repository.py packages/ops/service.py tests/api/test_dashboard_pm.py`
- `.venv/bin/mypy apps/api/routers/dashboard.py packages/identity/repository.py packages/identity/service.py packages/ops/repository.py packages/ops/service.py`
- `cd apps/web && npm run lint`
- `cd apps/web && npm run typecheck`
- `cd apps/web && npm run test -- --run`

## Status

In review. Next lead-specific increment should add drilldown links/actions and
Salesforce enrichment fields from ENG-255.
