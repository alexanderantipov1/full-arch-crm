# Verification — Per-tenant marketing creds

- ruff + mypy on changed packages; tsc/lint on apps/web for UI work.
- ENG-489: apply the new migration on a TEMP/clean DB (not the multi-branch dev DB) and confirm new provider_kinds accepted, existing rows intact. Run the standard alembic drift check.
- ENG-490: seed a DB credential locally, confirm the pull builds the client via from_credential and ingests; no-cred → graceful skip.
- ENG-491: enter a key via the UI, confirm encrypted row in tenant.integration_credential, no secret in logs/audit.
- Integration tests on a real PostgreSQL test DB where applicable.
