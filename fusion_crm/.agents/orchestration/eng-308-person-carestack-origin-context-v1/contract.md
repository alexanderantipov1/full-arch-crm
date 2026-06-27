# Contract — ENG-308

## API contract additions

- `PersonDetailOut.carestack_origin: list[CarestackOriginRowOut]` —
  one row per linked CareStack pid for this person.
- `CarestackOriginRowOut`:
  - `patient_id: str`
  - `earliest_activity_at: datetime | None`
  - `latest_activity_at: datetime | None`
  - `default_location_id: int | None`
  - `default_location_name: str | None` (resolved server-side)
  - `default_provider_id: int | None`
  - `default_provider_name: str | None` (resolved server-side)
  - `city: str | None`
  - `state: str | None`

## Repository contract additions

- `IngestRepository.person_carestack_origin_context(tenant_id,
  person_uid) -> list[CarestackOriginRowOut]` (or dict per pid the
  service converts to the DTO).
- `IngestRepository.upsert_providers(tenant_id, providers: list[dict])`
  idempotent.
- `IngestRepository.lookup_provider_names(tenant_id,
  provider_ids: Iterable[int]) -> dict[int, str]`.

## CareStack client addition

- `CareStackClientProtocol.list_providers(...)` returning
  `list[dict]` of providers as CareStack returns them. The shape is
  not invented — match what `docs/integrations/carestack/` documents
  (pre-flight confirms).

## Script contract

- `infra/scripts/backfill_providers.py` CLI flags: `--tenant-id`,
  `--max-providers` (default 2000), `--sleep-seconds` (default 0.5),
  `--commit-every` (default 50), `--dry-run`. Background-only.

## Persistence

- New table `ingest.carestack_provider` (or extension of an existing
  tenant-scoped table — worker decides + documents): keyed by
  `(tenant_id, provider_id)`. Columns at minimum: `provider_id`,
  `first_name`, `last_name`, `title` (nullable), `status` (nullable),
  `created_at`, `updated_at`. Tenant-scoped.

## Hard limits inherited from prior tickets

- CareStack mocked in all tests (no real network).
- No HTTP wiring for backfill script.
- No PHI in logs.
- No `apps/web/lib/msw/handlers.ts` modification.
- Throttle / backoff conventions unchanged (reuse 0.5s + injected sleep).
- `except Exception`, never `except BaseException`.
- English in repo; UI strings inherit existing tone (EN labels).
