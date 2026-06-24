# ENG-241 Worker Report

## Summary

Implemented centralized call reference extraction without audio download,
transcription, or LLM calls.

Salesforce Task call-reference handling now uses the shared pure extractor.
Salesforce Event ingest now scans `Description` for allowlisted call/meeting
provider URLs and emits `call_reference_found` interaction events containing
only extracted metadata.

## Changed Files

- `packages/ingest/call_reference.py` — new pure extractor and `CallReference`
  dataclass.
- `packages/ingest/sf_task_service.py` — refactored `CallObject` extraction
  through the shared extractor while preserving legacy payload keys.
- `packages/ingest/sf_event_service.py` — added Event `Description`
  call-reference extraction and metadata-only `call_reference_found` emission.
- `packages/interaction/repository.py` — added tenant-scoped provider event
  list lookup for call-reference dedupe.
- `packages/interaction/service.py` — exposed the provider event list lookup.
- `tests/ingest/test_call_reference.py` — extractor coverage for providers and
  edge cases.
- `tests/ingest/test_sf_event_service.py` — Event integration and redaction
  coverage.
- `tests/integration/test_tenant_isolation.py` — resolver for the new
  tenant-scoped repository read method.

## Tests Run

- `python -m pytest tests/ingest/test_call_reference.py tests/ingest/test_sf_task_service.py tests/ingest/test_sf_event_service.py` — 41 passed.
- `make lint` — passed.
- `mypy .` — passed.
- `make test` — 741 passed.
- `cd packages/db && set -a && source ../../.env && set +a && alembic check` —
  passed, no new upgrade operations detected.

## Verification Result

Passed.

## Risks

- `call_reference_found` rows intentionally use `source_event_id=None` while
  storing `raw_event_id` in payload. This avoids the existing
  `(source_provider, source_event_id)` uniqueness constraint colliding with the
  primary `call_logged` or consultation event for the same raw capture.
- Event URL extraction is intentionally provider-domain allowlisted for free
  text. Non-provider URLs in `Description` are ignored unless a future task adds
  an approved provider.

## Blockers

None.

## Do-Not-Merge Conditions

None.
