# Verification Plan

## Backend

- Run focused `pytest` for Agent Runtime service, API routes, tool execution,
  answer contract validation, and safety metadata tests touched by the mission.
- Run `ruff` and `mypy` for changed backend modules.
- Run Alembic check if DB models or migrations change.

## Frontend

- Run focused schema/component tests for `/dev/agent-runtime` workbench changes.
- Run `npm run typecheck` and `npm run lint` in `apps/web` for changed UI work.
- Use browser smoke for local workbench rendering and important states:
  generated answer, clarification, denied, approval-required, no-match, blocked,
  and missing credential.

## Safety

- Assert API responses exclude secrets, raw provider payloads, PHI, raw prompts
  with sensitive values, row-level rows, raw SQL, unmasked samples, and export
  payloads.
- Assert answer generation is not called for unsafe or non-executed outcomes.
- Assert final answers include source refs and caveats.
- Assert generated answers do not introduce unapproved metric definitions or
  catalog meaning.

## Production Closure

- PR checks must pass.
- Production deploy must pass.
- Production route smoke must prove `/dev/agent-runtime` is present and
  protected.
- Live-key smoke should run where credentials are configured; otherwise record
  the safe missing-credential result.
- Linear and Orchestrator runtime must be synchronized before the mission is
  marked complete.

## ENG-377 Closure Evidence

- `make lint`: passed.
- `mypy .`: passed.
- `make test`: failed because default shell `python` lacks project
  dependencies.
- `PATH=.venv/bin:$PATH make test`: 1398 passed, 3 failed in unrelated Project
  Manager dashboard tests.
- Mission-focused backend tests: passed, 48 tests.
- Mission-focused backend ruff and mypy: passed.
- Frontend schema tests: passed, 19 tests.
- Frontend lint and typecheck: passed.
- Alembic check from `packages/db`: passed, no new upgrade operations detected.
- Local browser smoke: passed for allowed answer, clarification, denied,
  missing credential, and run-history answer audit.
- Production route smoke: `/dev/agent-runtime` returns IAP `302`, route exists
  and is protected.
