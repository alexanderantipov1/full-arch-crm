# CLAUDE.md — `apps/api` (FastAPI)

The HTTP surface. Thin handlers, services do the work.

## Files

- **`main.py`** — `create_app()`, lifespan, middleware, routers.
- **`dependencies.py`** — DI: `get_db`, `get_principal`, one
  `get_*_service` per domain. Routers depend on services, not on
  `AsyncSession`.
- **`middleware.py`** — `RequestContextMiddleware` (request id +
  structured access log) and `platform_error_handler`
  (`PlatformError` → JSON envelope).
- **`routers/`** — one router per domain: `health`, `identity`,
  `ops`, `phi`, `ingest`, `tools`.

## Hard rules

- **No business logic in routes.** A handler's body is essentially:
  validate path/query → call service → return DTO. If you need an
  `if`, an `await session.execute(...)`, or a `for`, push it into
  the service.
- **No raw `HTTPException` for domain errors.** Raise
  `PlatformError` subclasses; the middleware handles translation.
  `HTTPException` is acceptable only for HTTP-level concerns
  (e.g. 400 on path/body mismatch).
- **One DB session per request.** Acquired via the `get_db`
  dependency, committed on success, rolled back on exception. Do
  not open extra sessions inside a handler.
- **Principal is read from `request.state.principal`** (set by
  future auth middleware). Today it defaults to `ANONYMOUS`.
  Replace the default before going to production.
- **Docs are off in production** (`/docs` and `/openapi.json` are
  `None` when `APP_ENV=production`). Don't re-enable them without
  a reverse-proxy gate.

## Adding a new endpoint

1. Decide which router it belongs to.
2. Add a `pydantic` `In` schema if the body is non-trivial.
3. Add the service method in `packages/<domain>/service.py`.
4. Wire the route: depend on the service via `Depends(...)`.
5. Return a DTO via `Out.model_validate(orm_obj)`.

## CORS / auth

- CORS origins come from `API_CORS_ORIGINS` (CSV). Don't hardcode.
- Auth is currently a stub. When you wire it (OIDC/JWT), implement
  it as a middleware that sets `request.state.principal` and let
  `get_principal` pick it up — no other call sites need to change.

## Run locally

```bash
make api      # uvicorn with --reload
```

Smoke checks: `GET /healthz`, `GET /readyz`.
