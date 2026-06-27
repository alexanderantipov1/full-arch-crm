# Incidents — Semantic Context And Analytics Foundation

- 2026-05-30T06:55:10Z | Linear initiative creation attempted through the
  connector, but the tool returned `save_initiative not found`. Impact: no
  Linear initiative URL is available. Mitigation: created Linear project
  `Semantic Context And Analytics Foundation` as the active umbrella and
  recorded the initiative gap in runtime `linear-sync.md` and
  `decision-log.md`.
- 2026-05-30T07:11:34Z | Linear initiative creation retried after user request.
  The connector again returned `save_initiative not found`. Impact unchanged:
  the Linear project remains the operational umbrella.
- 2026-05-30T07:57:11Z | ENG-273 and ENG-279 `claude-code` background
  workers stayed alive with zero-byte logs and no output files. Impact: worker
  execution path was not producing useful progress. Mitigation: terminated both
  sessions with `worker_ctl --kill`, then completed the docs locally as
  Orchestrator self-execute and wrote reports for both tasks.
- 2026-05-30T08:18:06Z | Full verification was partially blocked by the local
  shell environment. `make test` could not collect the suite because optional
  runtime/test dependencies were missing (`structlog`, `respx`, `chevron`,
  `arq`). `alembic check` could not load settings because `SECRET_KEY`,
  `DATABASE_URL`, and `REDIS_URL` were unset. Impact: full-suite and migration
  checks remain unverified in this shell. Mitigation: targeted checks, `make
  lint`, and `make typecheck` passed; rerun full verification in the prepared
  dev environment.
