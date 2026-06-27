# ENG-317 Worker Report — SCR-04 Review Audit And Version History

Linear issue: https://linear.app/fusion-dental-implants/issue/ENG-317/scr-04-review-audit-and-version-history

## Summary

Implemented the audit/version-history slice for semantic catalog proposal
review actions.

- Added stable audit taxonomy and helpers for catalog review decisions:
  approve, edit, reject, and unresolved.
- Added sensitive-key redaction before catalog review metadata is written to
  `audit.access_log.extra`.
- Added version-change audit helper and a small explanation helper so future
  catalog version history can explain why a metric changed.
- Integrated the new audit helper into the current ENG-315
  `AnalyticsCatalogReviewService` contract and API DI without adding route
  business logic.

## Changed Files

- `apps/api/dependencies.py`
- `apps/api/routers/semantic_catalog.py`
- `packages/analytics/service.py`
- `packages/audit/CLAUDE.md`
- `packages/audit/service.py`
- `tests/analytics/test_catalog_review_service.py`
- `tests/audit/test_audit_service.py`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-317-worker-report.md`

## Verification

Passed:

- `python -m pytest tests/audit/test_audit_service.py tests/analytics/test_catalog_review_service.py -q`
  - `17 passed`
- `python -m ruff check packages/audit/service.py tests/audit/test_audit_service.py packages/analytics/service.py tests/analytics/test_catalog_review_service.py apps/api/dependencies.py apps/api/routers/semantic_catalog.py`
- `python -m ruff format --check packages/audit/service.py tests/audit/test_audit_service.py packages/analytics/service.py tests/analytics/test_catalog_review_service.py apps/api/dependencies.py apps/api/routers/semantic_catalog.py`
- `python -m mypy packages/audit/service.py tests/audit/test_audit_service.py packages/analytics/service.py tests/analytics/test_catalog_review_service.py apps/api/dependencies.py apps/api/routers/semantic_catalog.py`
- `mypy packages apps`
  - `Success: no issues found in 203 source files`

Attempted but blocked:

- `make lint`
  - Failed on unrelated/pre-existing ruff issues outside ENG-317:
    `packages/ingest/repository.py`, `packages/interaction/repository.py`,
    and `tests/ingest/test_carestack_patients_with_payments_sql.py`.
- `make test`
  - Failed during collection because the current Python environment is missing
    dependencies including `structlog`, `respx`, `chevron`, and `arq`.
- `cd packages/db && alembic check`
  - Failed before migration comparison because required settings env vars are
    unset: `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL`.

## Risks And Notes

- ENG-314 durable storage is still represented in this workspace by in-memory
  repository contracts. No migrations or shipped Alembic revisions were edited.
- `log_catalog_version_change(...)` records version-change explanations when a
  real catalog version ID exists. Current review responses still return
  `catalog_version_id=None`, so durable storage should call this helper when it
  creates approved catalog versions.
- Audit payloads intentionally omit proposal `raw_value`, reviewer notes, raw
  provider payloads, secrets, and PII-like fields. The audit helper also redacts
  sensitive `extra` keys defensively.
- Parallel workers modified mission files, API wiring, web files, `packages`,
  `infra`, and new `packages/insight` files while this task was running. I did
  not revert those changes.

## Integration Notes

- `AnalyticsCatalogReviewService` now accepts an optional `AuditService`.
  API wiring passes a request-scoped audit service through
  `get_analytics_catalog_review_service`.
- `update_proposal(...)` writes `semantic_catalog.review.edit` when a principal
  is provided.
- `review_proposal(...)` writes:
  - `semantic_catalog.review.approve`
  - `semantic_catalog.review.reject`
  - `semantic_catalog.review.unresolved`
  - `semantic_catalog.review.edit` for transitions back to `proposed`.
- Future storage-backed approval should pair the review audit row with
  `semantic_catalog.version.change` when an approved proposal produces a new
  catalog version that changes metric meaning.
