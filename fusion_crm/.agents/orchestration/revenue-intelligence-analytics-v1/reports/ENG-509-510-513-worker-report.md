# Worker Report — B1 Enablement (ENG-509 / ENG-510 / ENG-513)

**Epic:** ENG-504 Revenue Intelligence Analytics Platform · **Block:** B1 (missing-field enablement)
**Branch (worktree):** `eng-509-eng-509` (base = `main`, has B0 foundation)
**Runtime:** claude-code · **Session:** aaa39d6a7b5b · **Date:** 2026-06-18
**Status:** ✅ Implemented + verified locally. **NOT committed, NOT pushed, NO PR opened, NO dev-DB backfill run** (see Do-Not-Merge / handoff).

---

## TL;DR

Fills the three people dimensions on `analytics.fact_patient_journey` and adds the
single manual-override write path:

| Ticket | Field(s) | Auto source | Manual |
|--------|----------|-------------|--------|
| ENG-509 | `caller_id` | SF Lead Owner `ops.lead.extra.owner_id` → `actor.actor` (kind `salesforce_user_id`) | ✅ |
| ENG-509 | `coordinator_id` | SF Opportunity Owner `ops.opportunity.extra.owner_id` → `actor.actor` | ✅ |
| ENG-510 | `doctor_id` | clinical actor on earliest clinical event (`interaction.event_responsibility` role=`clinical`; CareStack appointment provider, ENG-417) | ✅ |
| ENG-513 | ANY overridable fact field | — | ✅ `FactEnrichmentService` + `POST /dashboard/analytics/fact-override` |

Precedence **manual > auto > unresolved** is enforced for BOTH provenance AND value:
a builder rebuild never clobbers a manual value.

---

## What changed & why

### ENG-509 — caller + coordinator (SF owner → actor)
- `ops` (read-only additions): `OpsService.analytics_lead_owner_by_person` and
  `analytics_opportunity_owner_by_person` — one GROUP BY each, returning
  `person_uid → SF owner id` for the person's earliest lead / earliest opportunity.
- `actor`: `ActorService.resolve_actor_ids_from_source(...)` — batch idempotent
  create-or-lookup (`external_id → actor_id`). This IS the "backfill from existing
  extra": the builder collects the small set of distinct SF owner ids and resolves
  them once per run, creating `actor.actor` + `actor_identifier (salesforce_user_id)`
  rows as needed. Unmappable ids (bad SF prefix) are skipped → dimension stays NULL.
- `FactPatientJourneyBuilder._resolve_owner_actors` maps each person → caller /
  coordinator actor and sets the fact fields with provenance `method='auto'`; NULL +
  `unresolved` when no owner resolves.

### ENG-510 — doctor (CareStack provider → actor)
- `interaction` (read-only addition): `InteractionService.analytics_clinical_actor_by_person`
  — `person_uid → doctor actor_id` from the earliest `event_responsibility` row of
  role `clinical`. The clinical actor is the CareStack appointment-provider actor the
  ingest responsibility resolver (ENG-417) already links (kind `carestack_provider_id`).
  The builder surfaces it as `doctor_id` (`auto`), else NULL `unresolved`.
- Provider-directory backfill (completeness for ENG-510 "link CareStack providers →
  actor"): `IngestService.list_carestack_provider_directory` +
  `apps/worker/jobs/fact_patient_journey_enablement.py::link_carestack_providers_to_actors`
  — links every `ingest.carestack_provider` row to an `actor.actor`
  (kind `carestack_provider_id`) with a proper "Dr First Last" name. Because
  `actor_identifier (kind,value)` is workspace-unique, this enriches the SAME actor
  rows the builder surfaces as `doctor_id` (gives the doctor dimension clean names and
  links providers not yet seen on a consult). `ingest` may not import `actor`, so the
  actor write is wired at the worker boundary. Gated OFF (on-demand only, no cron) —
  same posture as the B0 `refresh_fact_patient_journey`.

### ENG-513 — manual enrichment path
- `provenance.manual(...)` helper (method `manual`, highest precedence).
- `FactPatientJourneyRepository`:
  - `existing_for_merge(...)` (replaces `existing_provenance`) — returns prior
    provenance **and** value columns so the builder can preserve manual VALUES, not
    just provenance.
  - `apply_manual_override(person_uid, field, value, *, provenance_entry)` — sets one
    column + stamps `field_provenance[field]=manual`; creates the row if absent.
- `FactPatientJourneyBuilder._preserve_manual_values(...)` — on rebuild, any field the
  stored row marks `manual` keeps its stored value (auto recompute is discarded);
  `merge_provenance` keeps the manual provenance entry. Together = value+provenance
  both survive (manual > auto > unresolved).
- `FactEnrichmentService` (`packages/analytics/enrichment_service.py`) — the single
  write path. One edit, one unit of work:
  1. `EnrichmentService.add_annotation(... key="fact.<field>", source="ui")` — durable
     `enrichment.record_annotation` row **+ its `audit.access_log` row**
     (`action="enrichment.annotation.add"`). This is the auditable who/when per edit.
  2. `apply_manual_override(...)` into the fact row with `method='manual'`.
  Coerces the string/number input to the column type (UUID / ISO datetime / Decimal),
  `None` clears a field. Overridable: caller/coordinator/doctor, campaign_id/name,
  vendor_id, treatment_accepted_date, surgery_*_date, marketing_cost_allocated.
- Endpoint: `POST /dashboard/analytics/fact-override` (`FactOverrideIn` → `FactOverrideOut`),
  thin composer over `FactEnrichmentService`. Wired via `get_fact_enrichment_service`.
  (Web UI is the optional follow-up per the ticket.)

### Migration (one, chained on head `e5d4c3b2a190`)
`20260618_0600_a1b2c3d4e5f6_add_fact_people_dimension_indexes.py` — partial indexes
`ix_fact_patient_journey_{caller,coordinator,doctor}_id WHERE <col> IS NOT NULL` for the
Caller/Coordinator/Doctor filter pages (B2.5–B2.7). Mirrored in the model
`__table_args__` so `alembic check` stays clean.

---

## Changed files (18 modified, 4 new)

**Modified**
- `packages/ops/repository.py`, `packages/ops/service.py` — bulk owner reads (ENG-509)
- `packages/interaction/repository.py`, `packages/interaction/service.py` — clinical-actor read (ENG-510)
- `packages/actor/service.py` — `resolve_actor_ids_from_source` batch backfill
- `packages/analytics/provenance.py` — `manual()` helper
- `packages/analytics/fact_repository.py` — `existing_for_merge` + `apply_manual_override` + `ExistingFactRow`
- `packages/analytics/fact_builder.py` — caller/coordinator/doctor resolution + manual-value preservation
- `packages/analytics/models.py` — 3 partial indexes (model/migration parity)
- `packages/analytics/schemas.py` — `FactOverridableField`, `FactOverrideIn/Out`, `FactFieldProvenanceOut`
- `packages/ingest/repository.py`, `packages/ingest/service.py` — `list_provider_directory` read
- `apps/api/dependencies.py` — `get_fact_enrichment_service`
- `apps/api/routers/dashboard.py` — `POST /dashboard/analytics/fact-override`
- `apps/worker/jobs/fact_patient_journey_refresh.py` — wire `ActorService` into builder
- `apps/worker/main.py` — register the two enablement jobs (gated, no cron)
- `tests/analytics/test_fact_builder.py` — updated fakes + resolution/precedence tests
- `tests/integration/test_fact_patient_journey_builder.py` — builder ctor `actor=`

**New**
- `packages/analytics/enrichment_service.py` — `FactEnrichmentService`
- `apps/worker/jobs/fact_patient_journey_enablement.py` — provider→actor backfill
- `packages/db/alembic/versions/20260618_0600_a1b2c3d4e5f6_add_fact_people_dimension_indexes.py`
- `tests/analytics/test_fact_enrichment_service.py`

---

## Tests run & results

| Check | Result |
|-------|--------|
| `ruff check` (all touched packages + tests + migration) | ✅ clean (1 import-order auto-fix applied) |
| `mypy` analytics, actor, ops, interaction, ingest | ✅ no issues (59 files) |
| `mypy` apps/api deps + dashboard + worker jobs/main | ✅ no issues (5 files) |
| `pytest tests/analytics tests/actor` | ✅ 107 passed |
| `pytest tests/analytics/test_fact_builder.py test_fact_enrichment_service.py test_provenance.py` | ✅ 34 passed |
| `pytest tests/ops tests/interaction` | ⚠️ 216 passed, **2 pre-existing failures** (see Risks) |
| Migration on **scratch** Postgres: `alembic upgrade head` | ✅ applies |
| `alembic check` (model/migration parity) | ✅ "No new upgrade operations detected" |
| `alembic downgrade -1` → re-`upgrade head` | ✅ indexes drop + recreate cleanly |
| API + worker import smoke | ✅ imports OK |

New unit tests added:
- `test_fact_builder.py`: `test_caller_coordinator_doctor_resolved` (auto resolution +
  single batch resolve of distinct owners), `test_unresolved_people_dimensions_when_no_signal`,
  `test_rebuild_preserves_manual_value_over_auto` (manual VALUE beats auto across rebuild),
  updated `test_provenance_methods`.
- `test_fact_enrichment_service.py`: UUID/datetime/Decimal coercion, null-clear,
  unknown-field + uncoercible-value rejection, dual-write (annotation + fact override).

**Migration tested on a throwaway scratch DB** (`eng509_scratch_*`, created + dropped) —
**never against the shared dev DB**, per guardrail.

---

## Risks / notes

1. **`doctor_id` coverage depends on clinical responsibility rows.** Auto doctor
   resolution reads `interaction.event_responsibility` role=`clinical`, populated by the
   ingest responsibility resolver (ENG-417) on consult ingest. If a tenant's consults
   were ingested before that resolver was wired, `doctor_id` is NULL for them until a
   responsibility backfill runs — those persons are counted (unresolved), not dropped,
   and the manual path + provider-directory backfill cover the gap. Acceptance ("fact
   rows carry doctor_id") is design-correct; coverage is a data/backfill concern.
2. **caller/coordinator owners that are SF Groups/Queues (`00G…`)** resolve to a
   `system` actor (not a person). Rare for owners; the dimension still gets a stable
   actor id. Flag if the Caller/Coordinator pages must exclude non-human actors.
3. **2 pre-existing `tests/ops/test_covering_opportunity.py` failures** — `source_status`
   MagicMock not set; **confirmed pre-existing** by re-running with my `ops` changes
   stashed (identical failures). Unrelated to this work.
4. **Builder now resolves/creates actors during `build()`.** This is the explicit
   ENG-509 "idempotent backfill" and uses `ActorService` (the public idempotent surface,
   like audit). It is a deliberate, documented side-effect; the builder still writes
   business rows ONLY to its own `analytics` schema.
5. **Integration test `test_fact_patient_journey_builder.py` asserts `count()==2`** —
   only valid on an isolated/fresh DB (CI provides one). It must NOT be run against the
   populated dev DB. My run against the dev DB rolled back (fixture rollback; no writes
   leaked) and failed only on that global-count assertion; the per-row provenance
   assertions passed. CI on a clean DB is the real proof.

---

## Blockers / decisions

- None blocking. One design decision taken without escalation (documented above):
  `doctor_id` auto source = clinical `event_responsibility` actor (the resolved CareStack
  appointment-provider actor) rather than re-deriving the patient `defaultProviderId`,
  because the provider→actor linking already exists in ingest and this keeps the builder's
  dependency surface to already-imported services. The provider-directory backfill job
  satisfies ENG-510's "link CareStack providers → actor". If the operator prefers
  patient-`defaultProviderId` as the doctor source, that's an additive follow-up.

---

## Do-not-merge / handoff conditions

- **NOT committed, NOT pushed, NO draft PR** — per the orchestrator rule "Do not commit,
  push, or run destructive commands" and CLAUDE.md "Never commit unless the user
  explicitly asks." Changes are staged in the worktree, ready for the operator/orchestrator
  to commit per ticket (Claude Co-Authored-By trailer) and open the **draft PR** (no merge).
- **Do NOT run the dev-DB backfill here** — the orchestrator runs
  `refresh_fact_patient_journey` (+ optional `link_carestack_providers_to_actors`) against
  the shared dev DB AFTER review, per guardrail. The migration `a1b2c3d4e5f6` must be
  applied before the backfill so the people-dimension indexes exist.
- **Migration head check before merge**: confirm `main` has not gained another revision
  off `e5d4c3b2a190` (two alembic heads break prod deploy). Re-point `down_revision` if so.
- Integration tests must run on a fresh CI DB, not the dev DB (see Risk 5).
