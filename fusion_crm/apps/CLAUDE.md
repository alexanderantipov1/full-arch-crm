# CLAUDE.md — `apps/` (deployable processes)

Each subfolder is one deployable process. Today: `api` (FastAPI) and
`worker` (arq). Tomorrow: maybe `web` (frontend), maybe small
microservices. Each MUST have its own `CLAUDE.md`.

## Common rules for any app

- An app contains **wiring**, not domain logic. Logic lives in
  `packages/`.
- An app **owns the unit of work**: it opens the session, commits on
  success, rolls back on failure. Services and repositories never
  commit.
- An app reads config via `packages.core.config.get_settings()` —
  never via `os.environ`.
- Every app's `Dockerfile` runs as a non-root user (`uid 10001`).
  Keep it that way.
- Every long-running app exposes a healthcheck (HTTP `/healthz` for
  servers, `--check` or equivalent for workers).
- Logs are JSON in production (`APP_ENV=production` flips
  structlog into the JSON renderer automatically).

## Adding a new app

1. Create `apps/<name>/` with a `Dockerfile`, an entry module, and
   a `CLAUDE.md`.
2. Wire it into `infra/docker/docker-compose.yml`.
3. Add any new env vars to `packages.core.config.Settings` AND
   `.env.example`.
4. Document run/build/test commands in the new `CLAUDE.md`.
