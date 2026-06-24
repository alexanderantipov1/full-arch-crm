# Verification

## Focused Checks

Run focused checks as each slice lands:

- Backend service/API tests for Agent Runtime contracts.
- Frontend Zod schema tests for every API response used by the workbench.
- Frontend typecheck and lint for `/dev/agent-runtime`.
- Browser smoke for docs, OpenAI test connection, and new controls.

## Full Verify Loop

Before closing the mission, run the repo-level checks required by policy where
practical:

- `make lint`
- `mypy .`
- `make test`
- `cd packages/db && alembic check`

If a full check is blocked by existing unrelated failures, record the failure,
scope, and evidence in the worker report and incidents file.

## Production Checks

- Verify `/dev/agent-runtime` renders in local and production-like runtime.
- Verify production-bundled docs do not disappear.
- Verify secrets are not returned to the browser.
- Verify run/audit/approval DTOs do not include PHI or raw provider payloads.
