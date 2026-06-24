# CLAUDE.md — `packages/core`

Cross-cutting primitives. Allowed to be imported by EVERY other
package; itself imports NOTHING from sibling packages.

## Modules

- **`config.py`** — `Settings` (pydantic-settings) + `get_settings()`.
  All env reads go through here. Never call `os.environ` elsewhere.
  Production env changes must also follow `docs/DEPLOYMENT_RULES.md`.
- **`exceptions.py`** — `PlatformError` hierarchy. Domain code raises
  these; the API middleware translates them to JSON. Do NOT raise
  raw `HTTPException` from services or tools.
- **`logging.py`** — `configure_logging()` + `get_logger(name)`.
  Use this everywhere; the stdlib `logging` module is forbidden in
  app code.
- **`security.py`** — `Principal`, `Role`, `PHI_READ_ROLES`. Today
  this is a placeholder for real auth (OIDC/JWT); the contracts here
  are what the rest of the platform depends on.
- **`types.py`** — shared `NewType`s, e.g. `PersonUID`. Use them at
  service boundaries to prevent UUID swap bugs.

## Rules

- Adding a new env variable → add a typed field on `Settings` AND
  document it in `.env.example`. Never read it ad hoc.
- For Cloud Run-provided values, avoid direct complex env field types
  such as `list[str]`; use raw string fields plus computed
  properties when operators will set CSV-like values. See
  `docs/DEPLOYMENT_RULES.md`.
- New production env vars must be reflected in
  `infra/env/production.env.reference`, deploy scripts, and env
  contract/preflight tests unless explicitly documented as
  operator-only.
- New `PlatformError` subclass → set `code` and `http_status`.
- Don't grow `core` into a junk drawer. If something fits in a
  domain, put it there.

## Logging — what is safe

Allowed in log fields: `request_id`, `principal_id`, `person_uid`,
action codes, durations, counts.
**Forbidden:** any clinical content, names, phone numbers, emails,
DOB, raw payload bodies. If unsure, don't log it.
