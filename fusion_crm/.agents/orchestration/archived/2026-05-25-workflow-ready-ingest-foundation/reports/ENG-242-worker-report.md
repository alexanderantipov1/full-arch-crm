# ENG-242 Worker Report

## Summary

Added the safe person operational timeline read surface:

- `GET /persons/{uid}/operational-timeline`
- `InteractionService.list_operational_timeline(...)`
- frontend Zod contract and TanStack Query hook

The read model returns only allowlisted fields: event kind, occurred time,
source references, data class, review status, safe summary, and current ops
projection snapshots for lead, consultation, and follow-up task refs. It does
not expose `interaction.event.payload` or raw provider payloads.

## Changed Files

- `apps/api/dependencies.py`
- `apps/api/routers/persons.py`
- `apps/web/lib/api/hooks/usePersons.ts`
- `apps/web/lib/api/schemas/person.ts`
- `packages/interaction/repository.py`
- `packages/interaction/schemas.py`
- `packages/interaction/service.py`
- `packages/ops/repository.py`
- `packages/ops/service.py`
- `tests/api/test_persons_operational_timeline.py`
- `tests/integration/test_tenant_isolation.py`
- `tests/interaction/test_service.py`

## Implementation Notes

- Kept `packages.interaction` isolated from `packages.ops` by using a narrow
  `OperationalProjectionReader` protocol. API wiring injects `OpsService` as
  the reader.
- Added ops projection lookups by tenant-scoped ids and final allowlisting in
  `InteractionService` before constructing DTOs.
- Added API route response model:
  `PersonOperationalTimelineOut(items, total)`.
- Added frontend schemas:
  `OperationalTimelineEntrySchema` and
  `PersonOperationalTimelineSchema`.
- Added frontend hook:
  `usePersonOperationalTimeline(uid)`.
- Updated the tenant-isolation sweep argument resolver for the new ops
  repository read methods.

## Tests Run

- `ruff check packages/interaction/schemas.py packages/interaction/repository.py packages/interaction/service.py packages/ops/repository.py packages/ops/service.py apps/api/dependencies.py apps/api/routers/persons.py tests/interaction/test_service.py tests/api/test_persons_operational_timeline.py`
- `python -m pytest tests/interaction/test_service.py tests/api/test_persons_operational_timeline.py -q` — 63 passed
- `mypy packages/interaction packages/ops apps/api/routers/persons.py apps/api/dependencies.py`
- `make lint`
- `mypy .`
- `make test` — 737 passed
- `cd packages/db && set -a && source ../../.env && set +a && alembic check`

## Verification Result

Passed.

Required verification loop succeeded:

- `make lint`
- `mypy .`
- `make test`
- `cd packages/db && set -a && source ../../.env && set +a && alembic check`

## Risks

- `apps/web` package dependencies are not installed in this worktree; an
  optional `cd apps/web && npm run lint` attempt failed because `next` was not
  available. The required repo-level verification does not depend on npm.
- The endpoint exposes call reference URLs through `source_external_id` when
  present, with `review_status` preserved so the UI can gate pending-review
  items.

## Blockers

None.

## Do Not Merge Conditions

None observed after verification.

## Commit

Planned local commit message:

`add operational timeline read surface for persons`
