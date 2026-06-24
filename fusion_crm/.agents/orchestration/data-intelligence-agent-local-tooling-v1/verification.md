# Verification Plan

## Required Repo Checks

- `make lint`
- `mypy .` or the current repo-standard typecheck command if different on the
  execution branch
- `make test`
- `cd packages/db && alembic check`
- `git diff --check`

## Focused Checks

- Tests cover accepted and denied tool calls.
- Tests prove no tool accepts raw SQL input or free-form DB query text.
- Tests prove `packages.tools` does not call repositories or
  `session.execute(...)` directly.
- Tests prove raw provider payload fields remain denied.
- Tests prove PHI output is denied in V1.
- Tests prove row limits cannot be bypassed.
- Tests prove masks/redaction are applied to row-level samples.
- Tests prove audit/logging is called for success and denial cases.
- Frontend tests or smoke checks cover local workbench visibility if ENG-298
  changes web code.
- Production review confirms agents still access platform data only through
  `packages.tools`.

## Review Output

ENG-299 must produce a production review report that lists:

- changed files;
- tests and checks run;
- verification status;
- architecture invariant risks;
- unresolved decisions;
- follow-up Linear issues generated from gap briefs.
