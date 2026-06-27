# ENG-315 Worker Report — SCR-02 Catalog Review API Contracts

- Linear issue: ENG-315
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-315/scr-02-catalog-review-api-contracts
- Mission: semantic-context-analytics-foundation
- Worker: Codex
- Status: completed with integration notes

## Summary

Implemented a typed semantic catalog proposal review API contract under
`/semantic/catalog`. The route layer is DTO-to-service wiring only; status
transition rules, PHI-source denial, agent-approval denial, impact preview, and
draft patch generation live in the service layer.

The service currently uses a process-local repository stub with a typed
repository protocol. ENG-314 storage appeared in this workspace as
`packages/insight` while this worker was active, so durable persistence should
be integrated by adapting this contract facade to the `insight` storage service
before ENG-316 relies on cross-process persistence.

## Changed Files

- `apps/api/dependencies.py`
- `apps/api/main.py`
- `apps/api/routers/semantic_catalog.py`
- `packages/CLAUDE.md`
- `packages/analytics/AGENTS.md`
- `packages/analytics/CLAUDE.md`
- `packages/analytics/__init__.py`
- `packages/analytics/repository.py`
- `packages/analytics/schemas.py`
- `packages/analytics/service.py`
- `tests/api/test_semantic_catalog_routes.py`
- `tests/analytics/test_catalog_review_contracts.py`

Related parallel-worker files observed but not owned by ENG-315:

- `packages/insight/*` from ENG-314 storage work.
- `packages/audit/*` and `tests/analytics/test_catalog_review_service.py` from
  ENG-317 audit work.

## API Contract

- `GET /semantic/catalog/proposals`
- `POST /semantic/catalog/proposals`
- `PATCH /semantic/catalog/proposals/{proposal_id}`
- `GET /semantic/catalog/proposals/{proposal_id}/impact-preview`
- `POST /semantic/catalog/proposals/{proposal_id}/review`
- `POST /semantic/catalog/draft-patch`

Typed DTO coverage includes proposal create/update/list/read, review
transition, impact preview, and draft catalog patch output. Review statuses are
limited to `proposed`, `approved`, `rejected`, and `unresolved`.

## Acceptance Notes

- API contracts are typed and tested.
- Routes delegate to `AnalyticsCatalogReviewService` and contain no metric
  business logic.
- Invalid/denied review transitions raise `ValidationError` and return the
  platform error envelope through middleware.
- PHI-looking source fields are denied until a separate PHI-capable review lane
  is explicitly approved.
- `Role.SYSTEM` principals can create agent-sourced proposals but cannot approve
  them.
- The frontend can target API calls instead of localStorage draft state, but
  durable persistence still needs the ENG-314 `insight` storage adapter.

## Verification

Passed:

- `uv run pytest tests/api/test_semantic_catalog_routes.py tests/analytics/test_catalog_review_contracts.py tests/analytics/test_catalog_review_service.py tests/audit/test_audit_service.py`
  — 26 passed.
- `uv run ruff check apps/api/routers/semantic_catalog.py apps/api/dependencies.py apps/api/main.py packages/analytics tests/api/test_semantic_catalog_routes.py tests/analytics/test_catalog_review_contracts.py tests/analytics/test_catalog_review_service.py tests/audit/test_audit_service.py`
  — passed.
- `uv run mypy packages/analytics apps/api/routers/semantic_catalog.py` —
  passed.
- `uv run mypy .` — passed across 322 source files.

Failed / not actionable in this worker:

- `make lint` failed on pre-existing or parallel-work ruff findings outside
  ENG-315 scope:
  - `packages/ingest/repository.py`
  - `packages/interaction/repository.py`
  - `tests/ingest/test_carestack_patients_with_payments_sql.py`
- `make test` failed during collection because `make` used system Python 3.11
  without project dependencies (`structlog`, `respx`, `chevron`, `arq`).
  Focused tests passed through `uv run` on Python 3.12.
- `cd packages/db && uv run alembic check` failed before migration checks
  because required settings were absent from the environment:
  `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL`. Per repo rules, this worker did
  not read or edit `.env*`.

## Risks

- There are now two semantic catalog package surfaces in the workspace:
  `packages/analytics` for ENG-315 API/service contracts and `packages/insight`
  for ENG-314 durable storage. Integrator should choose the final boundary and
  wire `AnalyticsCatalogReviewService` to `InsightCatalogService` or collapse
  the facade if preferred.
- The default in-memory repository is not production persistence. It is safe for
  contract tests and local API shape validation only.
- ENG-317 audit work overlapped with this service. Current behavior is
  compatible in focused tests, but the final integration should verify audit
  writes after storage-backed approval creates catalog versions.

## Blockers

- No blocker for API contract review.
- Durable persistence is blocked on integrating ENG-314 storage into the
  ENG-315 route dependency.
- Full repo verification is blocked by unrelated lint findings and local
  environment setup described above.

## Integration Notes

- Replace `_catalog_review_repository = InMemoryCatalogProposalRepository()` in
  `apps/api/dependencies.py` with a storage-backed adapter once ENG-314 is
  integrated.
- Approved review responses currently return `catalog_version_id=None`; the
  storage-backed adapter should populate it from `packages/insight` approval
  output.
- Keep API routes thin when wiring storage: route -> service -> repository ->
  DB. Do not move impact, status, PHI, or audit decisions into the router.
