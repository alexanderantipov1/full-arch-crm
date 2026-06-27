# M1 Stabilization Review

Date: 2026-05-18
Owner: Codex orchestrator
Status: complete with known repository-wide blockers

## Scope

Stabilized and reviewed the current working-tree bundle before any commit/PR:

- deploy smoke diagnostics and Salesforce callback production env contract;
- tenant self-service integration credentials API/UI;
- local Salesforce OAuth reconnect recovery;
- orchestrator script lint cleanup.

No commit, push, merge, deploy, workflow rerun, or `.env*` edit was performed.

## Verification

Passed:

- `PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH make lint`
- `PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH make typecheck`
- `bash -lc 'set -a; source .env; set +a; PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH make verify'`
- `bash -lc 'set -a; source .env; set +a; PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH python -m pytest tests/api/test_integrations_salesforce.py tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py tests/core/test_env_reference_matches_settings.py tests/core/test_deploy_prod_smoke_logging.py tests/core/test_traffic_primary_filter.py -q'` => 71 passed
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run lint`
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run test` => 17 passed
- `git diff --check`

Blocked / not green:

- `PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH mypy .` fails with 51 existing test typing errors in 10 test files. The fresh errors in the current diff were fixed.
- `bash -lc 'set -a; source .env; set +a; PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH make test'` fails with 10 failed / 45 error / 425 passed. Main blocker is the existing `two_tenant_db` Phase B fixture raising at `tests/conftest.py:126`; additional existing outreach/worker test failures remain.
- `cd packages/db && alembic check` without env fails on missing required settings; rerun with `.env` loads successfully but reports existing drift: removed `tenant_id` indexes across domains and outreach default drift. No new migration was added in this bundle.

## Review Findings

No blocking finding in the current diff after focused verification.

Residual risks:

- `apps/api/routers/integrations.py` returns a JSON error response after expiring dead OAuth credentials instead of re-raising `SfNotConnectedError`; this is intentional so `get_db()` commits the credential expiry. Keep this behavior covered by route tests.
- `ProviderCard` currently exposes the bootstrap credentials form from provider cards. It is acceptable for the current two providers (`salesforce`, `carestack`), but future providers should get explicit bootstrap schema support before enabling the button.
- `.claude/scheduled_tasks.lock` is unrelated local harness state and must be excluded from any future staging.
- `.claude/scheduled_tasks.lock` is already tracked in git, so `.gitignore`
  alone cannot hide it. Codex added the ignore rule for new clones/future
  cleanup and marked the local path `skip-worktree` to keep it out of this
  staging package.

## Suggested PR Package

One coherent PR is possible:

1. Deploy smoke + prod Salesforce callback contract.
2. Tenant/company self-service provider credentials API/UI.
3. Salesforce reconnect recovery and local callback pass-through.
4. Focused tests and orchestration reports.

Exclude:

- `.claude/scheduled_tasks.lock`
