# ENG-187 Worker Report

## Task

- Task id: ENG-187
- Title: Full verify cleanup: make repository-wide `make test` green
- Linear issue id: ENG-187
- Linear issue URL: https://linear.app/fusion-dental-implants/issue/ENG-187/full-verify-cleanup-make-repository-wide-make-test-green
- Role: worker
- Agent: codex
- Branch: main
- Worktree: `.`

## Allowed Scope

- Test command/tooling investigation.
- `Makefile` / test tooling changes if safe.
- This worker report.
- No test body edits; ENG-186 owns tests.
- No board, runtime, runlog, linear-sync, deployment, env, shipped migration,
  commit, or push changes.

## Touched Files

- `Makefile`
- `.agents/orchestration/current/reports/ENG-187-worker-report.md`

## What Changed

- Added a `PYTHON` Make variable that prefers the repository-local
  `.venv/bin/python` when it exists and falls back to `python` otherwise.
- Updated `make test` to run `$(PYTHON) -m pytest -q`.
- Updated `make verify-deploy` to use the same Python selector for its pytest
  invocation.

This keeps local pytest execution on the project-managed Python 3.12 virtual
environment while preserving the existing CI fallback path where GitHub Actions
sets up Python 3.12 and installs dependencies without creating `.venv`.

## Investigation Notes

- Root `CLAUDE.md` requires Python 3.12 for the project.
- `pyproject.toml` declares `requires-python = ">=3.12"` and test dependencies
  under the `dev` extra.
- The local shell resolves bare `python` to Python 3.11.5.
- `python3.12` is not on `PATH` in this shell.
- The repository `.venv` exists and uses Python 3.12.12.
- `uv run python` also resolves to the repository `.venv` Python 3.12.12.
- Before the Makefile change, `make test` ran `python -m pytest -q` under
  Python 3.11.5 and failed during collection with missing dependencies such as
  `structlog`, `respx`, and `chevron`.

## Verification

- FAIL before change: `make test`
  - Command used: `python -m pytest -q`
  - Python path: pyenv Python 3.11.5
  - Result: collection failed with 21 import errors from missing dependencies.

- FAIL after change: `make test`
  - Command used: `.venv/bin/python -m pytest -q`
  - Result: `10 failed, 512 passed, 55 errors in 5.08s`
  - Import/dependency collection errors from the Python 3.11 environment are
    resolved.

- FAIL comparison: `uv run pytest -q`
  - Result: `10 failed, 512 passed, 55 errors in 4.88s`
  - The failure profile matches `make test` after the Makefile change.

- PASS: `make verify-deploy`
  - Command used: `.venv/bin/python -m pytest tests/core/test_env_reference_matches_settings.py tests/core/test_traffic_primary_filter.py -q`
  - Result: `25 passed in 0.73s`

## Remaining Test Failures

- `tests/integration/test_tenant_isolation.py`
  - 55 errors come from `two_tenant_db` entering its Phase B branch and raising
    `RuntimeError: two_tenant_db Phase B body not yet implemented`.
  - 5 additional failures assert repository tenant-id signatures for
    `SendRepository` and `TenantRepository` methods.

- `tests/outreach/test_render.py::test_render_unknown_field_renders_empty_and_traces`
  - Still failing under the correct Python 3.12 environment.

- `tests/outreach/test_template_service.py::test_create_template_marketing_can_enable_tracking`
  - Fails because `TemplateOut.model_validate(template)` sees `id`,
    `created_at`, and `updated_at` as `None`.

- `tests/outreach/test_template_service.py::test_create_template_clinical_default_tracking_off`
  - Same `TemplateOut` validation failure for unset `id`, `created_at`, and
    `updated_at`.

- `tests/outreach/test_unsubscribe.py::test_one_click_post_adds_suppression`
  - Fails because the test expects suppression reason as positional arg index
    2, but the call no longer provides that positional argument.

- `tests/worker/test_bounce_poll.py::test_match_and_record_writes_bounce_audit_and_suppression`
  - Same suppression reason positional-argument expectation mismatch.

## Verification Status

Partially unblocked. The Makefile no longer runs the full test suite under the
wrong Python/dependency environment, and `make test` now matches
`uv run pytest -q`. Repository-wide `make test` is not green because of the
remaining test/product failures listed above. I did not edit test bodies or
product code because this worker was scoped to test command/tooling.

## Risks

- The Makefile fallback still uses bare `python` when `.venv` is absent. This is
  intentional for current CI compatibility, but local developers without `.venv`
  can still run with whatever `python` resolves to.
- Full `make verify` was not run because `make test` is already failing in the
  repository-wide suite.

## Blockers Or Questions

- ENG-186 or another test owner needs to decide whether the remaining
  tenant-isolation, outreach, and worker failures should be fixed in tests or
  product code.
- If the team wants all local Make targets to require `uv`, CI workflows should
  install `uv` first; this worker avoided that broader change.

## Suggested Next Task

- Fix or re-scope the remaining `make test` failures in the owning test/product
  areas, starting with the `two_tenant_db` Phase B fixture behavior because it
  accounts for most errors.

## Do Not Merge Conditions

- Do not merge as "full test green"; repository-wide `make test` still fails.
- Do not merge without ENG-186/test-owner review of the remaining test failures.
