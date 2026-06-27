# Acceptance — ENG-308

## Frontend (CareStack Card on persons/[uid]/page.tsx)

- [ ] "Patient since" label renamed to **"First ingest"**.
- [ ] First ingest field carries the existing `?` toggle tooltip
      (pattern from `0d44247`) explaining: "Date we first pulled this
      patient from CareStack. Actual creation in CareStack may be
      earlier — see 'Earliest activity'."
- [ ] New FieldLine **"Earliest activity"** with relative time from the
      true earliest CareStack anchor (MIN of appointment.createdOn +
      accounting.createdOn across all linked pids). Renders `"—"` when
      no activity. Carries its own `?` tooltip explaining the source.
- [ ] Address line **"City, State"** under the patient name (or near
      the CareStack Card header) — sourced from
      `payload.addressDetail.{city, state}` of the latest
      `carestack.patient.upsert` raw event. Renders nothing (no
      placeholder) when both are empty.
- [ ] **Provider** field showing the resolved provider name when
      `defaultProviderId` is set and the providers lookup has it;
      renders `"—"` otherwise. No raw `providerId` integer ever
      reaches the UI.
- [ ] Multi-link banner: when the person has ≥2 carestack/patient
      links, show a subtle banner under the CareStack Card body:
      "Linked to N CareStack patient records".
- [ ] Banner click toggles a collapsible panel with one row per pid:
      pid number, earliest activity, latest activity, location name
      (not raw ID), provider name (or `"—"`).
- [ ] No new PHI fields. The page never logs city/state/provider.
- [ ] No modification to `apps/web/lib/msw/handlers.ts`.

## Backend

- [ ] New aggregator method
      `IngestRepository.person_carestack_origin_context(tenant_id,
      person_uid) -> list[CarestackOriginRowOut]` returning one row per
      linked CareStack pid with: `patient_id`, `earliest_activity_at`,
      `latest_activity_at`, `default_location_id`, `default_provider_id`,
      `city`, `state`. Mirrors the `sum_accounting_totals_by_patient` /
      `latest_payment_summary_by_patient` shape: `for_tenant`, JSONB
      extraction, dedup-friendly, empty-input short-circuit.
- [ ] New DTO `CarestackOriginRowOut` in `packages/ingest/schemas.py`.
- [ ] `PersonDetailOut` (or its existing namespace) gains
      `carestack_origin: list[CarestackOriginRowOut]` field; person
      detail route handler populates it via one ingest call per
      request (no per-pid N+1).
- [ ] CareStack provider sync:
  - [ ] New CareStack client method `list_providers(...)` consuming
        the v1 providers endpoint (path confirmed by pre-flight). Mock
        in tests; no real network in CI.
  - [ ] Provider storage (decision recorded in the worker report): new
        `ingest.carestack_provider` table OR extension of an existing
        tenant-scoped table — orchestrator/worker picks based on
        what's already there. If a migration is required, it ships
        as a single new Alembic revision.
  - [ ] `IngestRepository.upsert_providers(tenant_id, providers)`
        idempotent per `(tenant_id, provider_id)`.
  - [ ] `IngestRepository.lookup_provider_names(tenant_id,
        provider_ids: Iterable[int]) -> dict[int, str]`.
- [ ] New `infra/scripts/backfill_providers.py` mirroring
      `backfill_payment_summary.py`:
      `--tenant-id`, `--max-providers` (default 2000), `--sleep-seconds`
      (default 0.5), `--commit-every` (default 50), `--dry-run`,
      structured log selector field. Background-only; NOT wired to any
      HTTP route.

## Tests

- [ ] Frontend vitest (extend
      `apps/web/tests/unit/FinancialSummaryCard.test.tsx` or add a
      sibling `PersonCardIdentity.test.tsx`):
  - First ingest renamed; tooltip toggles on click.
  - Earliest activity renders relative time when present, `"—"` when
    absent.
  - City + State render when present; nothing when absent.
  - Provider name renders when resolved; `"—"` when null.
  - Multi-link banner hidden for 1 link; visible + expandable for 3
    links (Torosyan-shape fixture: pids 1460847, 1461274, 2171827 with
    distinct locations).
- [ ] Backend pytest:
  - `person_carestack_origin_context` per-pid correctness, dedup,
    earliest/latest from BOTH appointment + accounting raw events,
    tenant scope, empty short-circuit.
  - `upsert_providers` dedups per `(tenant_id, provider_id)`, no
    cross-tenant leak.
  - `lookup_provider_names` returns `{}` on empty input; correct names
    for found, drops unknowns.
  - `list_providers` CareStack client mocked (no real network).
  - `backfill_providers.py`: `--dry-run` skips CareStack + skips
    commits; `--max-providers` cap; sleep injectable; selector log
    field.

## Verify

- [ ] `make lint && mypy . && make test && cd packages/db && alembic check`
      green (alembic check accounts for the new migration if added).
- [ ] `cd apps/web && npm run lint && npx tsc --noEmit && npm run test`
      green.
- [ ] Worker report at
      `.agents/orchestration/current/reports/ENG-308-worker-report.md`.
- [ ] Commit to worker's worktree branch only; NO push, NO PR;
      Orchestrator integrates.
