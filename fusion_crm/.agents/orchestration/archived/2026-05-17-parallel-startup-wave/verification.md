# Verification Plan

Use this file for commands and review checks that prove acceptance criteria.

## Wave S Local Verifier

Commands after S1 reports:

```bash
.venv/bin/python -m pytest tests/identity -q
set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check
git diff --check
make verify
```

Focused review checks:

- S1 changed only `packages/identity/**`, `tests/identity/**`,
  `packages/identity/CLAUDE.md`, and `reports/S1.md`.
- S2/S3 changed only their report files.
- No file under `packages/db/alembic/versions/**` was added or edited by S1.
- `identity` does not import `packages.ingest`.
- `MatchHintIn` contains only normalized person-hint fields, not raw provider
  payloads.
- `ResolveFromHintResult.was_existing_person_match` can map cleanly to the
  current Salesforce `is_reactivation` behavior in the next wave.
- Source-link recapture does not write a match candidate.
- Auto-accept writes source link before `MatchCandidate(status="auto_accepted")`.
- Open ambiguous matches do not block the caller from receiving a usable person.

## Semantic Verifier

Review:

- `goal.md`
- `acceptance.md`
- `contract.md`
- `ownership.md`
- `ownership.yaml`
- `reports/S1.md`
- `reports/S2.md`
- `reports/S3.md`

Decision:

- accepted
- not accepted

If not accepted, list only missing evidence or blockers.

## Full Verification

For Fusion CRM, use the required verify loop when appropriate:

- `make lint`
- `mypy .`
- `make test`
- `cd packages/db && alembic check`

Known mission context: prior focused gates were green, while some full
repository-wide gates have separate tracked debt. Do not hide those blockers;
separate current-diff acceptance from repository-wide health.

## Wave T Local Verifier

Commands after T1 reports:

```bash
.venv/bin/python -m pytest tests/ingest tests/identity tests/api/test_integrations_salesforce.py -q
set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check
git diff --check
make verify
```

Focused review checks:

- T1 changed only `packages/ingest/sf_lead_service.py`,
  `tests/ingest/test_sf_lead_service.py`, `packages/ingest/CLAUDE.md`, and
  `reports/T1.md`.
- T2 changed only `reports/T2.md`.
- No file under `packages/db/alembic/versions/**` was added or edited.
- No identity/ops/apps files were edited by T1.
- `SfLeadIngestService` still captures raw event before normalized hint.
- `SfLeadIngestService` no longer calls `self._identity._repo`,
  `resolve_by_email`, `resolve_by_phone`, `add_source_link`, or
  `resolve_or_create_person`.
- Raw SOQL records are not passed into identity.
