# Worker Task — ENG-443 (Block D2): wire 3 deferred events to NotificationEventService.emit

**Linear:** ENG-443 — https://linear.app/fusion-dental-implants/issue/ENG-443
**Parent epic:** ENG-433 (Interactive Messenger Layer). Follow-up to ENG-437 (Block D), which is merged to `main`.
**Task class:** `normal` (additive call-site wiring + tests). **Branch base: `main`** (the full messenger layer + Block D `lead.created` wiring are already in `main`).

## Goal
Wire the 3 remaining first-wave notification events to `NotificationEventService.emit(...)`. The rule engine, de-identified renderer, emit service, seeds, and the flagship `lead.created` wiring already shipped in ENG-437. This is **purely call-site wiring + integration tests** — do NOT change the emit service, schema, seeds, or renderer.

Events to wire:
1. `opportunity.stage_changed`
2. `ownership.changed`
3. `ingest.sync_failed`

## Hard architectural constraint (do not violate)
`ops` MUST NOT import `integrations` (packages import matrix in root CLAUDE.md). So emit calls go at the **boundary/worker caller**, never inside `OpsService`.

## Precedent to mirror exactly
`apps/api/routers/ops.py` lines ~67-103 — the flagship `lead.created` emit (`create_lead`). Read it first. It shows: the boundary owns the request/session transaction, depends on BOTH `OpsService` and `NotificationEventService` (`get_notification_event_service`), builds a **NON-PII** context dict, and calls `await events.emit(tenant_id, EVENT_*, context, principal=..., person_uid=...)`. Note the `has_phone` unknown-vs-empty discipline — mirror that care: pass only non-PII, omit fields when presence is unknown.

## Exact call sites (verified on current `main`)
- **opportunity.stage_changed / ownership.changed** — `OpsService.upsert_opportunity` (`packages/ops/service.py:1356`). Result envelope `OpportunityUpsertResult` (`packages/ops/schemas.py:334`) already exposes `was_stage_change` and `was_owner_change` (create-path set at `service.py:1425-1426`, update-path at `:1469`/`:1473`/`:1485-1486`). The boundary caller is the SF ingest path: `packages/ingest/sf_opportunity_service.py:248`. Determine the cleanest emit point: the worker job that drives SF opportunity sync (it owns the session and may import `integrations`), OR `sf_opportunity_service` if that is the genuine boundary. Decide by reading how `lead.created` was wired and how the opportunity sync job is structured. There is no `/opportunities` POST API route today (only leads/followups in `ops.py`), so the live path is the ingest worker. For leads, ownership lives in `Lead.extra['owner_id']` (`service.py:1598`).
- **ingest.sync_failed** — emit at each `status="failed"` site. `apps/worker/jobs/ingest_scheduled.py:328,498,731` and `apps/worker/jobs/backfill_full.py:181,222,264,313,363,413`. These worker jobs own a session and may import `integrations` directly. Context: `{"provider":..., "object":..., "sync_status":"failed"}`, `person_uid=None`. Consider a thin worker-side helper so the 9 sites call emit without re-deriving context shape — keep it DRY.

## Context rules
- NON-PII only. The renderer allowlist is the backstop, but do not rely on it — never pass names, phone numbers, DOB, clinical text, notes.
- Match the field-condition shape the seeds expect (`packages/integrations/chat/seeds.py`) so seeded rules actually fire. Read the seeds for these 3 events to learn the exact context keys the conditions test against.

## Verification (required before report)
- Add integration tests mirroring the existing ENG-437 emit tests (real Postgres test DB, not mocks — per root CLAUDE.md). Cover: each event emits an outbox row when a matching seeded rule exists; no PII leaks into context; the `ops ⊄ integrations` boundary is respected (emit not called from inside OpsService).
- Run the project verify loop: lint + typecheck + the relevant test packages + `alembic upgrade head` drift check. This task adds NO migration — confirm none is created.
- If the integration test DB is not reachable in this environment, write unit tests you can run and clearly mark which integration tests are written-but-unrun in the report.

## Deliverables
- Code changes wiring the 3 events at the correct boundaries.
- Tests.
- Worker report at `.agents/orchestration/interactive-messenger-layer-v1/reports/eng-443-worker-report.md` with: touched files, what changed, the boundary-placement decision + rationale, tests run + results, verification status, risks, and do-not-merge conditions.

## Do NOT
- Do not modify the emit service, notification schema, seeds, or renderer.
- Do not import `integrations` from `ops`.
- Do not create an Alembic migration.
- Do not commit to `main` or open a PR — stop at the report; the Orchestrator verifies and integrates.
