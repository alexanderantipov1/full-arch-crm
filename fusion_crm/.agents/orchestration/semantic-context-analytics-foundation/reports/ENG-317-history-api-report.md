# ENG-317 History API Report

## Scope

Closed the read-path gap for semantic catalog review history and version history.

## Changes

- Added proposal review history contracts and endpoint:
  - `GET /semantic/catalog/proposals/{proposal_id}/history`
- Added semantic term version history contracts and endpoint:
  - `GET /semantic/catalog/versions?term=...`
- Added insight repository/service read methods for:
  - versions by semantic term
  - versions by source proposal
- Added analytics service mapping for durable insight-backed history and in-memory fallback history.
- Wired catalog approval to `AuditService.log_catalog_version_change` so approved version changes have the dedicated audit side channel.
- Extended tenant-isolation resolver coverage for the new insight read methods.

## Verification

- `make lint`
- `uv run mypy .`
- `uv run pytest tests/analytics/test_catalog_review_insight_integration.py tests/insight/test_catalog_service.py tests/api/test_semantic_catalog_routes.py tests/analytics/test_catalog_review_contracts.py tests/analytics/test_catalog_review_service.py tests/audit/test_audit_service.py -q`
- `PYTHONPATH=. uv run pytest tests/integration/test_tenant_isolation.py -q`
- `PYTHONPATH=. uv run pytest -q`

## Known Environment Notes

- Local live tenant-isolation DB still does not have `insight.semantic_catalog_*` tables applied, so insight live repository cases skip until the ENG-314 migration is applied to that database.
- `cd packages/db && alembic check` still requires `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL` in this shell.
