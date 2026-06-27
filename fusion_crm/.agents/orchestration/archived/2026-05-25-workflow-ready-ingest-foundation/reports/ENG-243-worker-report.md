# ENG-243 Worker Report

## Summary

Added test-only workflow-ready ingest fixtures plus DB-backed integration
coverage for the cross-service ingest path, redaction sweep, operational
timeline response, and scheduled Salesforce sync-run lifecycle states.

## Changed Files

- `tests/_fixtures/__init__.py`
- `tests/_fixtures/workflow_ready.py`
- `tests/integration/test_workflow_ready_e2e.py`
- `tests/integration/test_workflow_ready_redaction.py`

## Verification Result

Passed.

## Tests Run

- `ruff check tests/_fixtures/workflow_ready.py tests/integration/test_workflow_ready_e2e.py tests/integration/test_workflow_ready_redaction.py`
- `python -m py_compile tests/_fixtures/workflow_ready.py tests/integration/test_workflow_ready_e2e.py tests/integration/test_workflow_ready_redaction.py`
- `python -m pytest tests/integration/test_workflow_ready_e2e.py tests/integration/test_workflow_ready_redaction.py -q` — 4 passed
- `python -m pytest tests/ingest/test_sf_lead_service.py tests/ingest/test_sf_event_service.py tests/ingest/test_carestack_appointment_service.py tests/ingest/test_sf_task_service.py tests/ingest/test_call_reference.py tests/api/test_persons_operational_timeline.py tests/integration/test_sf_lead_timeline_events.py tests/integration/test_workflow_ready_e2e.py tests/integration/test_workflow_ready_redaction.py tests/worker/test_ingest_scheduled.py -q` — 98 passed
- `make lint` — passed
- `mypy .` — passed
- `make test` — 759 passed
- `cd packages/db && set -a && source ../../.env && set +a && alembic check` — passed, no new upgrade operations detected

## Coverage Added

- End-to-end DB-backed ingest path across Salesforce Lead, Salesforce Event,
  CareStack Appointment, Salesforce Task action lane, Salesforce Task call lane,
  and `GET /persons/{uid}/operational-timeline`.
- Test fixture builders for Salesforce Lead/Event/Task and CareStack
  Appointment payloads, scoped under `tests/_fixtures`.
- Redaction sweep confirming raw provider payload markers stay out of
  `interaction.event.summary`, operational timeline responses, and lead /
  consultation projections.
- Provider-description redaction coverage for Salesforce Event Zoom references
  and Salesforce Task clinical-looking descriptions.
- Scheduled Salesforce worker entrypoint cross-check for `succeeded`,
  `partial`, `failed`, and `skipped_credential` `integrations.sync_run`
  closure states and record counters.

## Risks

- The new DB-backed integration tests skip only when database settings or
  connectivity are unavailable, matching the existing integration-test style.
- `call_logged` and `call_reference_found` share the same `occurred_at` for a
  single Salesforce Task by design; the E2E assertion treats those first two
  entries as an unordered tie while still checking descending timeline order
  for the rest.

## Blockers

None.

## Do Not Merge Conditions

None currently. Do not merge if any required verification command regresses,
or if review identifies that the redaction markers appear outside
`ingest.raw_event.payload`.

## Suggested Next Task

- Add a shared DB integration fixture if more workflow-ready tests land; the
  current helper keeps scope local to Task H and avoids changing global pytest
  behavior.
