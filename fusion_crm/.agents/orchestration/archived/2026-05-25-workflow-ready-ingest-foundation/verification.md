# Verification

Full verification is expected before the parent mission can be treated as
complete:

```bash
make lint
mypy .
make test
cd packages/db && alembic check
```

If a check is skipped, blocked, or fails for a known unrelated reason, the
worker or verifier report must document the exact command, status, and blocker.

Required focused coverage:

- event taxonomy and summary builder tests;
- Salesforce Lead/Event/Task ingest tests;
- CareStack Patient/Appointment ingest tests;
- idempotency tests for repeated pulls;
- redaction tests for raw payloads, SF Event `Description`, CareStack notes,
  Task free text, and sensitive call URLs;
- sync-run success, partial, skipped credential, and provider error tests.

