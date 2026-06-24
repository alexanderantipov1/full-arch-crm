# Incidents

## 2026-05-22T20:11:27Z — Verification environment retries

During the pre-PR verification gate, two command invocations initially used the
wrong local execution context:

- `make test` used system Python 3.11 and failed during collection because dev
  dependencies such as `structlog`, `respx`, and `chevron` were unavailable.
  The retry with `PATH=.venv/bin:$PATH make test` passed with 646 tests.
- `alembic check` first lacked required settings, then used the default local
  Postgres port where the `fusion` role does not exist. The retry used local
  dev values and the compose-reported ports (`127.0.0.1:5434` for Postgres,
  `127.0.0.1:6380` for Redis) and passed with no new upgrade operations.

No product code changes were made for these retries.

## 2026-05-22T20:21:47Z — Runtime artifact cleanup

Production Reviewer found local runtime references to 12 missing raw worker log
files and one stale prompt file. The sessions were launched in `print` mode,
which prepares commands and prompt files but does not start background worker
processes or write raw worker logs.

Resolution:

- Removed the dangling `log_path` fields from local `runtime.json` rather than
  fabricating empty log files.
- Removed stale prompt
  `ENG-227-VERIFY-SCAN-8d0cfcd6d591.md`; the active runtime session points to
  `ENG-227-VERIFY-SCAN-5ea9e584d846.md`.
- Kept reports and `runlog.md` as the execution evidence for these completed
  print-mode sessions.
