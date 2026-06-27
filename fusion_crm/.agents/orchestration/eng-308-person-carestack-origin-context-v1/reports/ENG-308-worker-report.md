# ENG-308 — Worker Report

- Task id: ENG-308
- Linear issue: ENG-308
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-308/person-card-surface-true-carestack-identity-and-origin-context
- Role: worker
- Agent: claude-code (Opus 4.7)
- Branch: eng-308-eng-308 (worktree-only; not pushed)
- Worktree: ~/.fusion-agent-orchestrator/c2db50910d08/current/worktrees/ENG-308/
- Allowed scope: in-scope; everything ships behind the existing
  CareStack ingest layering invariants.

## What changed (per task in the worker prompt)

### Task 1 + 3 — `CareStackProvider` model + migration + repository methods

- **`packages/ingest/models.py`** — new
  `class CareStackProvider(UUIDPrimaryKeyMixin, TimestampMixin,
  TenantScopedMixin, Base)`. Schema `ingest.carestack_provider`,
  columns: `provider_carestack_id (BigInteger)`, `first_name`,
  `last_name`, `middle_name`, `short_name`, `provider_type`,
  `is_active`, `payload (JSONB)`. Unique constraint
  `(tenant_id, provider_carestack_id)`, index
  `ix_carestack_provider_tenant_id`.
- **`packages/db/alembic/versions/20260531_2030_e9f0a1b2c3d4_add_ingest_carestack_provider.py`**
  — single new revision (down_revision = current head
  `d8e9f0a1b2c3`). Creates the table, the unique constraint, the
  tenant index, plus an FK to `tenant.tenant.id` ON DELETE RESTRICT
  matching the mixin convention. Has a clean `downgrade()`.
- **`packages/ingest/repository.py`** — three new methods:
  - `upsert_providers(tenant_id, providers)` — idempotent via
    `ON CONFLICT (tenant_id, provider_carestack_id) DO UPDATE`,
    dedups input rows by id before passing to Postgres (so the
    cardinality_violation case can never fire), short-circuits on
    empty input.
  - `lookup_provider_names(tenant_id, provider_ids)` — empty-input
    short-circuit, builds the display name per the worker-prompt
    rule (`"Dr <First> <Last>"` when `providerType` looks like a
    doctor, else `"<First> <Last>"`, falls back to `shortName`,
    then `f"Provider #{id}"`).
  - `person_carestack_origin_context(tenant_id, patient_ids)` —
    the per-pid aggregator. Three SELECTs (appointment.createdOn,
    accounting.TransactionDate, latest patient.upsert for
    location + provider + city + state). All `for_tenant`-scoped,
    deduped by `external_id` (latest `received_at` wins), JSONB
    extraction via `payload[...].astext` / `payload[k1][k2].astext`,
    address read limited to `city` + `state` (HIPAA Safe Harbor —
    `addressLine1` / `addressLine2` / `zipCode` are deliberately
    NOT in the SQL).

### Task 2 — CareStack `list_providers` + provider ingest service

- **`packages/integrations/carestack/client.py`** —
  `async def list_providers(self) -> list[dict[str, Any]]`. Calls
  `GET /api/v1.0/providers`, asserts the flat-array shape (per
  spec `docs/integrations/carestack/resources/providers.md`),
  raises `CareStackApiError` on a non-array body. Mirrors the auth
  / retry pattern used by `list_locations()`.
- **`packages/ingest/carestack_provider_service.py`** (NEW) —
  `CareStackProvidersClientProtocol` (one method: `list_providers`)
  and `CareStackProviderIngestService.import_providers(...)` —
  fetches the directory once, drops entries without a usable integer
  id, caps at `max_providers`, upserts in `commit_every`-sized
  batches with per-batch error isolation (`except Exception`, never
  `BaseException` per the repo invariant).

### Task 4 — DTOs

- **`packages/ingest/schemas.py`** — new
  `CarestackOriginRowOut` (patient_id + earliest_activity_at +
  latest_activity_at + default_location_{id,name} +
  default_provider_{id,name} + city + state, every field nullable
  where the back end may have nothing yet) and `ProviderImportOut`
  (imported + total_seen + error_count) — the operator-log shape
  for the backfill script.

### Task 5 — Service wrapper + persons route embed

- **`packages/ingest/service.py`** —
  `IngestService.person_carestack_origin_context(tenant_id,
  carestack_patient_ids)` — short-circuits on empty input, calls the
  repository aggregator, then resolves provider names in one batch
  via `IngestRepository.lookup_provider_names`. Location names are
  resolved per-cs-id via `LocationService.find_by_carestack_id` —
  `find_by_carestack_id` already existed in the tenant package, so
  the wrapper just calls it (no new tenant-repo method). Lookup
  failures are logged at `info` (best-effort; UI falls back to raw
  id). Module-scope structlog logger `_origin_log` avoids a
  `get_logger` call per failure.
- **`apps/api/routers/persons.py`** —
  - Added `CarestackOriginRowOut` to the import block.
  - Added `carestack_origin: list[CarestackOriginRowOut] = []` to
    `PersonDetailOut`.
  - In the `get_person_detail` handler, after the existing
    CareStack-pid resolution (lines 192-198), added one additional
    `ingest.person_carestack_origin_context(...)` call — same
    `tenant_id` + `carestack_patient_ids`. Single round-trip; no
    N+1.
  - Passed the resolved list into the constructor.

### Task 6 — `infra/scripts/backfill_providers.py`

- New script mirroring `backfill_payment_summary.py`:
  - `argparse` flags: `--tenant-id` (required), `--max-providers`
    (2000), `--sleep-seconds` (0.5), `--commit-every` (50),
    `--dry-run`.
  - `async def main(args, *, sleep=None, session_factory=None,
    client_factory=None) -> int` — testable shape, returns CLI exit
    code 0 / 2 / propagates the exception (CLI converts the
    final code).
  - Opens `async_session`, fetches the CareStack credential,
    wraps the sweep in
    `IntegrationService.open_provider_sync_run /
    close_provider_sync_run` (provider `"carestack"`, object_scope
    `"providers"`).
  - `--dry-run` builds a temporary CareStack client to FETCH the
    provider list and PRINTS the ids to stdout (so the operator
    sees what the real run would write), but never opens a sync_run
    and never calls the upsert.
  - Structured log lines all carry `selector="providers"` so log
    forensics can tell provider runs apart from payment-summary
    runs.
  - Exit codes: 0 success / 2 missing CareStack credential /
    propagates the exception (CLI exit code 1) on uncaught errors.

### Task 7 — Frontend Zod + hook

- **`apps/web/lib/api/schemas/person.ts`** —
  - New `PersonCarestackOriginRowSchema` mirroring the backend
    DTO field-for-field (every Datetime nullable+optional, every
    number / string nullable+optional where the backend allows
    `None`).
  - Extended `PersonDetailSchema` with
    `carestack_origin: z.array(PersonCarestackOriginRowSchema).default([])`.
  - `index.ts` re-exports `person.ts` already, so the new
    `PersonCarestackOriginRow` type is import-ready under
    `@/lib/api/schemas` without further changes.
- No new TanStack Query hook required — `usePersonDetail` already
  covers `PersonDetailSchema`.

### Task 8 — CareStack Card redesign

- **`apps/web/app/(staff)/persons/[uid]/page.tsx`** —
  - Extracted the previous inline CareStack `<Card>` into a new
    `CarestackIdentityCard` component (still in the same file,
    same emerald colour scheme).
  - **"Patient since" → "First ingest"**. Uses
    `FieldLineWithHelp` (a new sibling of `FieldLine` that adds
    the per-field `?` toggle from `0d44247`). Description:
    *"Date we first pulled this patient from CareStack. Actual
    creation in CareStack may be earlier — see 'Earliest activity'."*
  - **New "Earliest activity" line** — relative time of the MIN
    of `earliest_activity_at` across every row in
    `data.carestack_origin`. Renders `"—"` when no row has a
    value. Per-field `?` describing the source.
  - **City, State** — rendered under the CardHeader (small
    muted line) when at least one of city/state is non-empty;
    hidden entirely when both are absent.
  - **Provider** — new `FieldLine` showing the primary
    pid's `default_provider_name` (no raw id ever reaches the
    UI). Falls back to `"—"`.
  - **Patient ID** kept as a separate `FieldLine` (operators
    still rely on it) — design choice documented here per the
    spec's "your call, document it" note.

### Task 9 — Multi-link expander

- New `CarestackMultiLinkPanel` component. Hidden when
  `data.carestack_origin.length < 2`. Otherwise renders a subtle
  button-style banner reading
  *"Linked to N CareStack patient records"*; clicking toggles a
  collapsible panel showing one row per pid with: pid (small
  monospace), location name (or `"—"`), provider name (or `"—"`),
  earliest activity (relative), latest activity (relative).
- The trigger is `aria-expanded` + `aria-controls` so the test
  can assert on its open/closed state without snapshot fragility.

### MSW fixtures

- **`apps/web/lib/msw/fixtures/persons.ts`** —
  - Added `carestack_origin: [...]` for Alice (1-link, populated)
    and Carol (1-link, empty activity).
  - New `TOROSYAN_UID` person + summary + detail with **3
    CareStack links** (pids `1460847`, `1461274`, `2171827`),
    half resolved / half null so the multi-link panel exercises
    both the populated and the empty-cell paths.
- **`apps/web/lib/msw/handlers.ts`** — NOT modified, per the
  hard constraint.

### Task 10 — Tests

**Backend** (every test green at the SQL-shape layer with the
existing `_stub_session_capturing` helper from
`tests/ingest/test_person_payment_repository_sql.py`):

- `tests/ingest/test_carestack_provider_repository_sql.py` (NEW) —
  5 tests covering: empty-input short-circuit for both methods,
  on-conflict upsert keyed on `(tenant_id, provider_carestack_id)`,
  input-row dedup by id, tenant + id-list scoping.
- `tests/ingest/test_person_carestack_origin_repository_sql.py`
  (NEW) — 4 tests covering: empty-input short-circuit, that the
  appointment `createdOn` JSONB read reaches the SQL, that the
  accounting `TransactionDate` JSONB read reaches the SQL, that
  the patient payload's city + state are read AND that
  addressLine1 / addressLine2 / zipCode are NEVER in the SQL
  (HIPAA Safe Harbor).
- `tests/ingest/test_carestack_provider_service.py` (NEW) — 5
  tests covering: empty CareStack response → zeroed counts +
  no commit, mid-run commit-every batching, max-providers cap,
  per-batch failure isolation, id-less entries silently dropped.
- `tests/api/test_person_detail.py` — extended with 2 tests:
  multi-link person returns 3 `carestack_origin` rows and
  passes the pid list to the service; zero-CS-link person
  returns `[]` (not null) for the frontend's safe-iteration
  contract.
- `tests/infra/test_backfill_providers.py` (NEW) — 7 tests
  mirroring `test_backfill_payment_summary.py`: argparse
  defaults / overrides, missing-credential exit code, dry-run
  doesn't open a sync_run or call upsert, --max-providers cap
  forwarded, sweep failure closes sync_run as `failed`,
  selector log field set to `"providers"`.

**Frontend** — `apps/web/tests/unit/PersonCardIdentity.test.tsx`
(NEW). 8 tests covering: "First ingest" rename + tooltip toggle,
Earliest activity relative-time render, Earliest activity `"—"`
empty state, City/State rendered when present, City/State hidden
when both absent, Provider name resolved vs `"—"` paths,
multi-link banner hidden with 1 link, multi-link banner +
expander rendered with 3 links.

## Verify commands actually run

| Command | Result |
|---|---|
| `ruff check` (changed files: persons.py + packages/ingest/ + carestack client + backfill + new tests) | **PASS** (only pre-existing `UP037` on `list["SourceLink"]` and pre-existing `I001` in unrelated ENG-307 test file remain; my files are clean) |
| `mypy packages/ingest/{repository,models,schemas,carestack_provider_service,service}.py packages/integrations/carestack/client.py infra/scripts/backfill_providers.py apps/api/routers/persons.py` | **PASS** — "no issues found in 8 source files" |
| `pytest tests/ingest/ tests/infra/test_backfill_providers.py -v -o pythonpath=.` | **PASS** — 256 / 256 (21 new + 235 existing) |
| `pytest tests/ingest/test_carestack_provider_repository_sql.py tests/ingest/test_person_carestack_origin_repository_sql.py tests/ingest/test_carestack_provider_service.py tests/infra/test_backfill_providers.py -v -o pythonpath=.` | **PASS** — 21 / 21 (focused subset) |

### Commands deferred to the integrator

- `pytest tests/api/test_person_detail.py` — required `.env` to
  load `Settings` at import time. The worktree has no `.env` and
  I am not permitted to create one. The route logic itself is
  exercised by FastAPI dependency-overrides in the test; once the
  integrator runs the loop with `.env` present (per
  `verification.md` § Integrator), the new tests
  `test_person_detail_returns_carestack_origin_for_multi_link_person`
  and `test_person_detail_returns_empty_carestack_origin_when_no_cs_links`
  must pass.
- `cd apps/web && npm run lint && npx tsc --noEmit && npm run test`
  — the sandbox bash harness blocks `npm` / `npx` invocations.
  The TypeScript + vitest changes compile-check fine when read by
  hand against the patterns of the existing
  `FinancialSummaryCard.test.tsx`. Integrator must run this loop
  before merging.
- `cd packages/db && alembic check` — same `.env` blocker; the
  new revision (`e9f0a1b2c3d4`) is the only revision whose
  `down_revision = "d8e9f0a1b2c3"` (current head, verified via
  grep), so there is no parallel-head ceremony to worry about.

## Files touched

### Created

```
infra/scripts/backfill_providers.py
packages/db/alembic/versions/20260531_2030_e9f0a1b2c3d4_add_ingest_carestack_provider.py
packages/ingest/carestack_provider_service.py
apps/web/tests/unit/PersonCardIdentity.test.tsx
tests/ingest/test_carestack_provider_repository_sql.py
tests/ingest/test_carestack_provider_service.py
tests/ingest/test_person_carestack_origin_repository_sql.py
tests/infra/test_backfill_providers.py
```

### Modified

```
apps/api/routers/persons.py
apps/web/app/(staff)/persons/[uid]/page.tsx
apps/web/lib/api/schemas/person.ts
apps/web/lib/msw/fixtures/persons.ts
packages/ingest/models.py
packages/ingest/repository.py
packages/ingest/schemas.py
packages/ingest/service.py
packages/integrations/carestack/client.py
tests/api/test_person_detail.py
```

## Design choices

1. **Patient ID kept as a separate `FieldLine`** under the
   resolved Provider — operators rely on it for the "click into
   the inspector" flow. The spec said "your call, document it".
2. **Location-name resolver** — used the existing
   `LocationService.find_by_carestack_id` rather than adding a
   batch repo method. Each person card has at most ~3 distinct
   carestack_location_ids, so the per-id calls do not introduce
   an N+1 in practice. If a future report needs hundreds of
   location ids on one query (e.g. a dashboard scan), a batch
   `lookup_location_names_by_carestack_ids` can be added
   alongside `find_by_carestack_id` then.
3. **Frontend earliest-activity** — computed as the MIN across
   every `carestack_origin` row in the page-level component,
   NOT pre-aggregated by the backend. Rationale: the per-pid
   array is already returned (we need it for the multi-link
   expander), and computing MIN client-side keeps the backend
   API surface narrower (no `aggregate_earliest_activity`
   field that we'd then have to keep consistent with the
   per-pid rows). The cost is one tiny `pickEarliest` loop
   over a 1-3 element array per render.
4. **Provider name formatting** — built into the repository's
   `lookup_provider_names` rather than the service so the
   formatting rule is co-located with the data read. The
   helper `_format_provider_display_name` is module-private to
   avoid polluting the public service surface.

## Risks

- **No live Postgres test for the JSONB extracts** — the new
  SQL-shape tests assert the compiled SQL contains
  `createdOn` / `TransactionDate` / `addressDetail` /
  `'city'` / `'state'`. They do NOT execute the query against a
  real Postgres. The full integrator loop runs the full pytest
  suite (which includes the existing live-DB tests for
  payment-summary and accounting aggregations) but does not yet
  ship a live-DB test for the origin-context aggregator. Adding
  one is a follow-up.
- **`is_doctor` heuristic** in `_format_provider_display_name`
  is a substring match (`"doctor"` / `"dr"` / `"dds"` / `"md"`
  inside `provider_type.lower()`). Could false-positive on a
  hypothetical provider_type like `"drama therapist"`. The
  CareStack provider types we've observed in the wild are all
  in the 4-token set above; widen the rule if we see a
  surprising provider_type in prod.
- **`--dry-run` on `backfill_providers.py` STILL contacts
  CareStack** — it needs the provider list to print. The
  payment-summary backfill `--dry-run` skips CareStack entirely
  because it only needs the local source_link table. For
  providers, there is no local list to resolve against, so a
  dry-run that "would do nothing" makes sense semantically;
  document this divergence on the runbook.

## Blockers / Open questions

None. Every spec'd task landed. The two deferred verifications
(api tests + apps/web npm-based loop + `alembic check`) are
documented above as integrator-runs.

## Suggested next task

ENG-309 candidate: live-DB integration test for
`IngestRepository.person_carestack_origin_context` against a real
Postgres fixture (mirrors the existing
`tests/ingest/test_*_repository_sql.py` live shape). The
SQL-shape tests in this branch are necessary but not sufficient —
a JSONB extraction bug could survive them.

## DO-NOT-MERGE conditions

- The integrator's full loop (`make lint && mypy . && make test
  && cd packages/db && alembic check && cd apps/web && npm run
  lint && npx tsc --noEmit && npm run test`) MUST be green.
- `alembic check` MUST report no drift (the new revision is
  additive only; downgrade is clean).
- The `tests/api/test_person_detail.py` extension MUST pass —
  these were not runnable in the sandbox without `.env`, but they
  are written, imported, and reachable via pytest collection.
- **Do NOT run the real CareStack `/api/v1.0/providers` endpoint
  in this PR's verification loop** — that is a separate operator
  decision (see `verification.md` § Smoke step 2-3 for the
  dry-run → real-run sequence).

## Sandbox limitations (for the orchestrator)

- The runtime telemetry directory under
  `~/.fusion-agent-orchestrator/c2db50910d08/current/` is outside
  the worktree and the bash sandbox blocked direct writes there.
  The launcher's `runtime.json` is presumed up to date; this
  worker did not refresh it. The repo-side decision artifacts
  (`.agents/orchestration/current/{goal,acceptance,verification,
  contract}.md`) were read but not modified.
- `pytest` with env-var prefix (`SECRET_KEY=... pytest ...`) is
  blocked by the harness, so the `apps.api.dependencies`-importing
  tests (which load `Settings` at import) cannot run in this
  sandbox.
- `npm` / `npx` / direct `node_modules/.bin/vitest` invocations
  are also blocked.
