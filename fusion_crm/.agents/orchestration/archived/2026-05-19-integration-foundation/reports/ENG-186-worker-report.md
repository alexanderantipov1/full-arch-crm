# ENG-186 Worker Report

## Scope

Fixed repository-wide `mypy .` failures in tests only. No production code was changed.

## Failures Fixed

- `tests/interaction/test_models.py`
  - Fixed SQLAlchemy `Index.name` key typing (`quoted_name | None`) by filtering non-null names and converting to `str`.
- `tests/identity/test_models.py`
  - Fixed SQLAlchemy `Index.name` key typing for the source-link partial unique index map.
- `tests/identity/test_match_candidate_model.py`
  - Fixed SQLAlchemy `Index.name` key typing for match-candidate partial unique index lookup.
- `tests/auth/test_auth_models.py`
  - Added a typed `_indexes_by_name` helper for session index lookup.
  - Replaced untyped `dialect_options.get("postgresql", {})` access with direct `dialect_options["postgresql"]` access.
- `tests/interaction/test_service.py`
  - Replaced direct typed method assignment to `session.rollback` with a local `AsyncMock` assigned through an `Any`-cast test double, preserving the assertion target without `method-assign`.
- `tests/tenant/test_location_import.py`
  - Replaced `captured.append(loc) or loc` side effect with a typed async helper returning `Location`.
- `tests/integrations/test_sf_oauth.py`
  - Wrapped OAuth test tenant UUIDs with `TenantId(...)` to match the service boundary.
- `tests/outreach/test_template_service.py`
  - Replaced direct typed assignment to service collaborator methods with local `AsyncMock` instances assigned through `Any`-cast test doubles.
- `tests/worker/test_bounce_poll.py`
  - Replaced direct module class reassignment with `monkeypatch.setattr`.
  - Wrapped bounce-poller tenant UUIDs with `TenantId(...)` for `_system_principal` and `_try_match_and_record`.
- `tests/outreach/test_unsubscribe.py`
  - Cast Starlette `Response.body` to `bytes` before decoding.
- `tests/outreach/test_open_tracking.py`
  - Cast Starlette `Response.body` to `bytes` before byte-prefix assertions.

## Remaining Blockers

- None for ENG-186 typing. Full repository `mypy` is green.
- `make test` is not green due to pre-existing/out-of-scope test-suite blockers:
  - `tests/conftest.py::two_tenant_db` enters the Phase B shim and raises `RuntimeError`, causing 55 tenant-isolation setup errors.
  - Additional out-of-scope failures remain in tenant isolation metadata tests, outreach render/template tests, unsubscribe assertions, and bounce-poll assertions.
- `cd packages/db && alembic check` is blocked by local environment/database setup:
  - Without env: missing `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL`.
  - With temporary test env values: PostgreSQL rejects the connection because role `test` does not exist.

## Verification

- `uv run mypy tests/interaction/test_models.py tests/identity/test_models.py tests/identity/test_match_candidate_model.py tests/auth/test_auth_models.py tests/interaction/test_service.py tests/tenant/test_location_import.py tests/integrations/test_sf_oauth.py tests/outreach/test_template_service.py tests/worker/test_bounce_poll.py tests/outreach/test_unsubscribe.py tests/outreach/test_open_tracking.py`
  - Result: `Success: no issues found in 11 source files`
- `uv run mypy tests/interaction/test_service.py tests/outreach/test_template_service.py`
  - Result after lint-compatible cast rewrite: `Success: no issues found in 2 source files`
- `uv run mypy .`
  - Result: `Success: no issues found in 221 source files`
- `make lint`
  - Result: `All checks passed!`
- `make test`
  - Result: failed, `10 failed, 512 passed, 55 errors`
- `cd packages/db && uv run alembic check`
  - Result: failed on missing required settings (`SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`)
- `cd packages/db && SECRET_KEY=... DATABASE_URL=... DATABASE_URL_SYNC=... REDIS_URL=... uv run alembic check`
  - Result: failed on PostgreSQL connection (`role "test" does not exist`)
