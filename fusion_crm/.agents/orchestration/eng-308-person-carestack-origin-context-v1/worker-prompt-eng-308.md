You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: **ENG-308**
(https://linear.app/fusion-dental-implants/issue/ENG-308/person-card-surface-true-carestack-identity-and-origin-context).
Isolated git worktree. Implement → verify → write a report. Do NOT touch `main`,
do NOT push, do NOT open a PR. Commit to YOUR worktree branch only once green;
the Orchestrator integrates.

## Mission (frontend + backend + new ingest)

Make the CareStack identity context on the person card honest and complete:
- Rename "Patient since" → "First ingest" + tooltip (it's our ingest date,
  not CS creation).
- Add "Earliest activity" — true earliest CareStack anchor (from raw
  events that DO carry creation timestamps).
- Surface "City, State" from the CS patient payload (HIPAA Safe Harbor
  hint, no street/zip).
- Show a multi-link banner + collapsible per-pid panel when a person has
  ≥2 CareStack patient_ids (Torosyan-shape: 3 pids merged into one person).
- Resolve `defaultProviderId` to a readable "Dr First Last" via a NEW
  CareStack providers sync + lookup.

Backend lands: new origin-context aggregator, new providers ingest (+
table + backfill script), `PersonDetailOut` extension. Frontend lands:
CareStack Card redesign + multi-link expander.

## Pre-flight facts (AUDITED — do NOT re-investigate)

### Existing patterns to mirror (ENG-306 lineage)

- **Aggregator pattern** lives at `packages/ingest/repository.py:291-469`:
  - `latest_payment_summary_by_patient(tenant_id, patient_ids)` lines 291-383.
  - `sum_accounting_totals_by_patient(tenant_id, patient_ids, *, transaction_codes)` lines 385-469.
  - Both: `for_tenant` scoping, dedup by latest `received_at` per
    `external_id`, **empty-input short-circuit** (return early without SQL),
    JSONB extraction via `cast(payload[...].astext, ...)`.
- **SQL-shape test scaffold** at
  `tests/ingest/test_person_payment_repository_sql.py:23-42` — the
  `_stub_session_capturing()` helper. **Reuse verbatim.**
- **DTO + embed pattern** for `PersonDetailOut`:
  - DTO `PersonPaymentFinancialSummaryOut` at
    `packages/ingest/schemas.py:240-265`.
  - Import in `apps/api/routers/persons.py:35`; embed at line 108
    (definition); populate at line 282 (constructor).
  - Route resolver for CareStack pids at lines 190-201 (filters
    `source_links_map[person.id]` for `source_system='carestack' AND
    source_kind='patient'`). **Reuse the exact filter.**

### `createdOn` reality across raw events (critical — don't get this wrong)

| Event type | Has `createdOn`? | Field to use |
|---|---|---|
| `carestack.appointment.upsert` | **YES** — ISO datetime string (e.g. `'2026-03-12T23:47:38'`). Already read by `packages/ingest/carestack_appointment_service.py:393` (look there for the exact JSONB extract idiom). | `payload->>'createdOn'` |
| `carestack.accounting_transaction.upsert` | **NO `createdOn`** per `docs/integrations/carestack/_source/carestack-v1.0.45.txt:2650,2673`. The fields available are `TransactionDate` (when the transaction occurred) and `LastUpdatedOn`. **Use `TransactionDate` as the activity-time anchor** (it's the most accurate "when did this happen in CS"). |
| `carestack.patient.upsert` | **NO `createdOn`**. Confirmed in spec line 1065. |

So the **"earliest activity"** computation across a CareStack patient_id =

```
MIN(
   appointment.upsert payload->>'createdOn' across all rows with this external_id,
   accounting_transaction.upsert payload->>'TransactionDate' across all rows with this external_id
) per external_id
```

Latest activity = MAX of the same set.

### Address payload shape (verified)

- `carestack.patient.upsert` payload: `addressDetail` is a nested object with
  `addressLine1, addressLine2, city, state, zipCode` per spec
  `docs/integrations/carestack/_source/carestack-v1.0.45.txt:600-606`.
- Surface ONLY `city` and `state` — never street, never zip.

### CareStack client + new providers endpoint

- **Canonical client** at `packages/integrations/carestack/client.py` (NOT
  `packages/ingest/`). It already exposes `list_locations()`,
  `list_patients_modified_since()`, `list_appointments_modified_since()`,
  etc. Add `async def list_providers(self) -> list[dict[str, Any]]`
  alongside the existing list-style methods.
- Each per-service ingest defines its own service-local `Protocol` for the
  subset of client methods it consumes. Follow that — define
  `CareStackProvidersClientProtocol` with the `list_providers` method
  alone, inject it into the new provider ingest service.
- **`GET /api/v1.0/providers`** — flat JSON array, **no pagination**
  (verified in `docs/integrations/carestack/resources/providers.md`).
  Fields per provider:
  - `id` (integer) — the CareStack provider id.
  - `firstName` (string)
  - `lastName` (string)
  - `middleName` (string, may be null)
  - `shortName` (string, may be null)
  - `providerType` (string)
  - `isActive` (bool)

### Tenant-scoped table conventions

- `packages/ingest/models.py` uses
  `class X(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base)`.
  `TenantScopedMixin` from `packages.db.mixins` auto-adds the tenant_id
  column + the per-table `ix_<table>_tenant_id` index.
- New table goes in `packages/ingest/models.py` as
  `class CareStackProvider(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "carestack_provider"  # under the ingest schema
    # columns: provider_carestack_id (BigInteger), first_name, last_name,
    #          middle_name (nullable), short_name (nullable),
    #          provider_type (string), is_active (bool), payload (JSONB).
  ` plus a unique constraint `(tenant_id, provider_carestack_id)`.
- **A NEW Alembic revision is required** (one revision file). DO NOT edit
  any shipped revision. Generate with `alembic revision --autogenerate`
  if helpful, but verify it manually before committing.

### Backfill script + test scaffolds

- Mirror `infra/scripts/backfill_payment_summary.py` exactly. The shape
  is the canonical operator-grade pattern (`argparse`, `_principal`,
  `async_session`, `open_provider_sync_run` / `close_provider_sync_run`,
  `selector` field in structured logs, `--dry-run` short-circuits before
  CareStack calls, exit codes 0/2/1).
- Test scaffold: `tests/infra/test_backfill_payment_summary.py` loads
  the script dynamically via `importlib.util.spec_from_file_location`.
  Reuse `_fake_session_cm()` and `_args()` patterns — copy the helpers
  into the new `tests/infra/test_backfill_providers.py` (do NOT extract
  into a shared conftest unless you have a clean way to do so without
  breaking existing tests).

## Tasks (TDD — write tests first per piece)

### 1. Backend: new table + model + migration

`packages/ingest/models.py`:
- Add `CareStackProvider` class with the schema above.

`packages/db/alembic/versions/`:
- Generate one new revision. Verify upgrade + downgrade are clean.
- The migration creates `ingest.carestack_provider` with columns +
  `(tenant_id, provider_carestack_id)` unique constraint +
  `ix_carestack_provider_tenant_id` index.

### 2. Backend: providers ingest service + client method

`packages/integrations/carestack/client.py`:
- Add `async def list_providers(self) -> list[dict[str, Any]]` calling
  `GET /api/v1.0/providers`. Mirror the auth/retry pattern used by
  `list_locations()`.

`packages/ingest/carestack_provider_service.py` (NEW file):
- Define `CareStackProvidersClientProtocol`.
- `CareStackProviderIngestService` class:
  - `__init__(session, carestack_client)`.
  - `async def import_providers(tenant_id, *, sleep=None, commit_every=50,
    commit=None, max_providers=2000) -> ProviderImportOut` — calls
    `list_providers`, iterates, calls
    `IngestRepository.upsert_providers` in batches (commit per
    `commit_every`), returns counts.

### 3. Backend: repository methods

`packages/ingest/repository.py`:
- `IngestRepository.upsert_providers(tenant_id, providers: list[dict]) -> int`
  — idempotent upsert keyed by `(tenant_id, provider_carestack_id)`.
  Use SQLAlchemy `Insert(...).on_conflict_do_update(...)`. Returns the
  number of providers persisted (insert or update).
- `IngestRepository.lookup_provider_names(tenant_id, provider_ids:
  Iterable[int]) -> dict[int, str]` — empty-input short-circuit (returns
  `{}` without SQL); returns `{provider_id: "Dr First Last"}` (or
  `"First Last"` if no title — see § "Naming convention" below).
- `IngestRepository.person_carestack_origin_context(tenant_id,
  patient_ids: Sequence[str], *, provider_name_resolver:
  Callable[[Iterable[int]], Awaitable[dict[int, str]]] | None = None) ->
  dict[str, dict]` — per-pid dict with:
  - `earliest_activity_at: datetime | None` (MIN of appointment `createdOn`
    + accounting `TransactionDate` per external_id, deduped).
  - `latest_activity_at: datetime | None` (MAX of same).
  - `default_location_id: int | None` (from latest patient.upsert).
  - `default_provider_id: int | None` (from latest patient.upsert).
  - `city: str | None`, `state: str | None` (from
    `payload.addressDetail.{city, state}` of latest patient.upsert).
  - Empty input → `{}` short-circuit.
  - Tenant-scoped via `for_tenant`.

### Naming convention

Provider display name = `"Dr <First> <Last>"` when `providerType.lower()`
contains `"doctor"` or `"dr"` or `"dds"`/`"md"`. Otherwise `"<First> <Last>"`.
Edge cases:
- Empty firstName → use lastName only.
- Empty lastName → use firstName only.
- Both empty → return shortName if non-empty, else `f"Provider #{id}"`.

### 4. Backend: service wrapper + DTO

`packages/ingest/schemas.py`:
- Add `CarestackOriginRowOut(BaseModel)`:
  - `patient_id: str`
  - `earliest_activity_at: datetime | None`
  - `latest_activity_at: datetime | None`
  - `default_location_id: int | None`
  - `default_location_name: str | None`
  - `default_provider_id: int | None`
  - `default_provider_name: str | None`
  - `city: str | None`
  - `state: str | None`
- Add `ProviderImportOut(BaseModel)`:
  - `imported: int`
  - `total_seen: int`
  - `error_count: int`

`packages/ingest/service.py`:
- `person_carestack_origin_context(tenant_id, carestack_patient_ids:
  Sequence[str]) -> list[CarestackOriginRowOut]` — calls the repository
  method, resolves provider + location names via
  `IngestRepository.lookup_provider_names` and (existing or new) location
  name resolver. Empty input → `[]` short-circuit.
- If there's no existing location-name resolver, build a small
  `lookup_location_names(tenant_id, location_ids) -> dict[int, str]`
  reading from whichever table already stores CareStack locations (check
  `packages/ingest/models.py` and `packages/tenant/models.py`).
  If neither exists yet, return `None` for `default_location_name` and
  document it as a follow-up.

### 5. Backend: API route + Pydantic embed

`apps/api/routers/persons.py`:
- Line 35: add import for `CarestackOriginRowOut`.
- Line 108: add `carestack_origin: list[CarestackOriginRowOut] = []`
  field to `PersonDetailOut`.
- Around lines 190-201: after the existing `carestack_patient_ids`
  resolution, add one more `ingest.person_carestack_origin_context(...)`
  call (same `tenant_id` + `carestack_patient_ids`). Single round-trip;
  no N+1.
- Line 282: pass `carestack_origin=origin_rows` into the constructor.

### 6. Backend: backfill script

`infra/scripts/backfill_providers.py` — NEW file mirroring
`backfill_payment_summary.py`:
- `argparse` flags: `--tenant-id` (required), `--max-providers`
  (default 2000), `--sleep-seconds` (default 0.5), `--commit-every`
  (default 50), `--dry-run`.
- `async def main(args, *, sleep=None, session_factory=None,
  client_factory=None) -> int` — testable shape, returns exit code.
- Opens `async_session`, fetches CareStack credential, calls
  `CareStackProviderIngestService.import_providers(...)`. Wraps in
  `open_provider_sync_run` / `close_provider_sync_run` (provider/object
  scope `"providers"`).
- `--dry-run` lists the provider IDs that WOULD be persisted on stdout,
  skips the actual upsert, skips opening a sync_run.
- Logs include `selector="providers"` field in every structured line.
- Exit codes: 0 success / 2 missing CareStack credential / 1 uncaught
  exception.

### 7. Frontend: types + hook (Zod additions)

`apps/web/lib/api/schemas/person.ts`:
- New `PersonCarestackOriginRowSchema` mirroring the backend DTO
  (every field nullable / optional where the backend says so).
- Extend `PersonDetailSchema` with
  `carestack_origin: z.array(PersonCarestackOriginRowSchema).default([])`.

No new hook needed if `usePersonDetail` already covers `PersonDetailSchema`.

### 8. Frontend: CareStack Card redesign

`apps/web/app/(staff)/persons/[uid]/page.tsx`:
- Rename the existing "Patient since" FieldLine label → "First ingest".
  Wrap with the per-field `?` toggle from `0d44247` explaining: "Date we
  first pulled this patient from CareStack. Actual creation in CareStack
  may be earlier — see 'Earliest activity'."
- Add a new "Earliest activity" FieldLine showing the relative time of
  the earliest activity across all carestack/patient links. Tooltip:
  "Oldest appointment created or transaction recorded in CareStack for
  this patient."
- Add a "City, State" line (no separate FieldLine — just a small muted
  line under the patient name or near the CardHeader) when city OR state
  is present. Hide entirely when both are absent.
- Replace the existing raw "Patient ID" display with the resolved
  provider name when available, OR show "—" otherwise. Keep the patient
  ID visible (operators rely on it) — render it small under the provider
  name OR keep it as a separate FieldLine. The choice is yours;
  document it in the report.

### 9. Frontend: multi-link expander

When `data.carestack_origin.length >= 2`:
- Below the CareStack Card body, render a subtle button-style banner:
  "Linked to N CareStack patient records" (with N = the array length).
- The banner toggles open a `<details>`-style or stateful collapsible
  panel listing one row per pid:
  - patient_id (small monospace)
  - location name (or "—")
  - provider name (or "—")
  - earliest activity (relative time, or "—")
  - latest activity (relative time, or "—")
- Hide the banner entirely when array length ≤ 1.

### 10. Tests

**Backend** (extend or create as appropriate):
- `tests/ingest/test_carestack_provider_repository_sql.py` (NEW) —
  `_stub_session_capturing` style tests for `upsert_providers` (on-conflict
  upsert structure, dedup) and `lookup_provider_names` (empty short-circuit,
  basic SELECT shape, tenant scoping).
- `tests/ingest/test_person_carestack_origin_repository_sql.py` (NEW) —
  tests for `person_carestack_origin_context`: tenant scoping, JSONB
  paths, empty short-circuit, dedup pattern.
- `tests/ingest/test_carestack_provider_service.py` (NEW) — tests for
  `CareStackProviderIngestService.import_providers`: dry-run-like behavior
  with an empty `list_providers` mock, commit-every batching, failure
  isolation, mocked client end-to-end (no real network).
- `tests/api/test_person_detail.py` — extend with one test asserting
  `carestack_origin` is returned in the JSON for a person with 2+ CS
  links + correct provider name resolution; one test for a person with
  1 CS link (`carestack_origin` length 1).
- `tests/infra/test_backfill_providers.py` (NEW) — mirror
  `test_backfill_payment_summary.py`: dry-run skips client; max-providers
  cap; sleep injection; selector log assertion; no real network.

**Frontend** (extend existing
`apps/web/tests/unit/FinancialSummaryCard.test.tsx` or create
sibling `apps/web/tests/unit/PersonCardIdentity.test.tsx`):
- "First ingest" label + tooltip toggle.
- "Earliest activity" renders relative time when present, `"—"` when
  null.
- City + State line renders when present; absent when both null.
- Provider name renders when `default_provider_name` is set; `"—"`
  otherwise.
- Multi-link banner hidden with 1 link; visible + expandable with 3
  links. Expanded panel rows render pid + location + provider +
  earliest/latest activity.

**MSW fixtures**
- `apps/web/lib/msw/fixtures/persons.ts` — add `carestack_origin` array
  to Alice (1-link) and to a new fixture for the Torosyan-shape case
  (3 links with distinct earliest/latest dates, distinct locations,
  distinct providers — half resolved, half null to exercise empty-state
  paths).

## Hard constraints

- **CareStack mocked in all tests.** ZERO real API calls in dev/CI.
- **No HTTP wiring for `backfill_providers.py`** — background-only.
- **No PHI in logs.** patient_id, provider_id, counts, location_id only.
- **NO modification of `apps/web/lib/msw/handlers.ts`** — unrelated WIP.
- **Address surface = city + state ONLY.** Never street, never zip, never
  in logs.
- **`except Exception`, never `except BaseException`.**
- **Strict TS** on frontend; **strict mypy** on backend.
- **ONE new Alembic revision** if a table is added. Never edit shipped
  migrations.
- **English in repo files.** UI labels stay English (the EN/RU Help
  dialog from `0d44247` is the one bilingual surface; this ticket does
  not need a second one).
- **Reuse**: the per-field `?` tooltip from `0d44247`; the
  `_stub_session_capturing` helper from
  `test_person_payment_repository_sql.py`; the `for_tenant` + JSONB
  patterns from `sum_accounting_totals_by_patient`; the backfill shape
  from `backfill_payment_summary.py`; the embed pattern from
  `PersonPaymentFinancialSummaryOut`.

## Verify (sandbox-aware)

Worker MUST run what the sandbox allows:

```bash
ruff check infra/scripts/backfill_providers.py \
  packages/ingest/ packages/integrations/ \
  apps/api/routers/persons.py \
  tests/ingest/ tests/api/ tests/infra/
mypy infra/scripts/backfill_providers.py packages/ingest/ packages/integrations/
```

If `pytest` runs on the focused subset:

```bash
pytest tests/ingest/ tests/api/test_person_detail.py tests/infra/test_backfill_providers.py -v -o pythonpath=.
```

If web tools run:

```bash
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```

If `alembic check` runs:

```bash
cd packages/db && alembic check
```

Document EVERY command run (passed/failed/skipped). The integrator re-runs
the full loop with `.env` regardless.

## Definition of done

1. All sandbox-allowed verify commands green.
2. ONE commit on worktree branch (NOT main):
   `ENG-308: surface CareStack identity context — origin aggregator + providers ingest + UI`.
3. Worker report at
   `.agents/orchestration/current/reports/ENG-308-worker-report.md`
   covering: touched files, what changed per task, tests added + results,
   verify commands attempted + outcomes, design choices (table placement,
   provider-name format, location-name resolver), risks, blockers / questions,
   suggested next task, DO-NOT-MERGE conditions.
4. Do NOT run the real CareStack `/api/v1.0/providers` against prod — that
   is a SEPARATE operator decision after merge.

If the spec / facts conflict with reality you find during implementation,
STOP and write `Blocked:` in the report — don't guess.
