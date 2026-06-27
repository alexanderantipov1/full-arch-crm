# ENG-511 — Worker Report

- **Task:** B1.3 — Treatment-accepted + surgery scheduled/completed stage capture
- **Linear:** ENG-511 — https://linear.app/fusion-dental-implants/issue/ENG-511/b13-treatment-accepted-surgery-scheduledcompleted-stage-capture
- **Task class:** `contract_change` (build only — UNCOMMITTED in worktree)
- **Role / agent:** worker / claude-code
- **Branch / worktree:** `eng-511-eng-511` /
  `…/revenue-intelligence-analytics-v1/worktrees/ENG-511`
- **Session:** f6ba9222e0ca
- **Status:** report-ready (do NOT merge — see do-not-merge conditions)

## Summary

Implemented Option A (plan-level acceptance) per the operator decision. The
fact builder now auto-resolves the three previously-`unresolved` stage columns
on `analytics.fact_patient_journey`:

| Fact column | Signal | Source |
| --- | --- | --- |
| `treatment_accepted_date` | CareStack `TreatmentPlan.StatusId=3` (Accepted) ONLY | NEW per-patient TreatmentPlan ingest → `interaction.event:treatment_accepted` |
| `surgery_scheduled_date` | treatment procedure `statusId=2`, implant-surgery CDT | existing procedure ingest → `interaction.event:surgery_scheduled` |
| `surgery_completed_date` | treatment procedure `statusId=8`, implant-surgery CDT | existing procedure ingest → `interaction.event:surgery_completed` |

Precedence `manual > auto > unresolved` is preserved: a rebuild never clobbers
an ENG-513 manual override (covered by a new test).

> Note: the spec referenced `docs/analytics/eng-511-treatment-surgery-stage-signals.md`
> and a decision-log entry that are NOT present in this worktree (it is off an
> earlier `main`). I implemented to the self-contained "Decided Implementation
> Plan" in the task prompt, which is internally complete. Flagging in case the
> reviewer expects those artifacts to be present at merge time.

## Changed files

### New
- `packages/db/alembic/versions/20260619_0000_b2c3d4e5f6a7_eng511_treatment_surgery_event_kinds.py`
  — new immutable revision (revises head `a1b2c3d4e5f6`). Widens the
  `interaction.event` `kind` CHECK (+`treatment_accepted`, `surgery_scheduled`,
  `surgery_completed`) and the `source_kind` CHECK (+`carestack_treatment_plan`).
  Pure CHECK widening, no data movement; downgrade restores the prior lists.
- `packages/ingest/carestack_treatment_plan_service.py` —
  `CareStackTreatmentPlanIngestService`: per-patient TreatmentPlan sweep,
  full-fidelity raw capture, `treatment_accepted` emission on `StatusId=3` only.
- `tests/ingest/test_carestack_treatment_plan_service.py` — unit tests (13).

### Modified — data/ingest layer
- `packages/integrations/carestack/client.py` — `get_treatment_plans(patient_id)`
  (`GET /api/v1.0/patients/{id}/treatment-plans`), normalises array/envelope/single.
- `packages/ingest/carestack_treatment_service.py` — procedure projection split:
  implant-surgery procedures (CDT-gated via `CatalogService`) map `statusId=2 →
  surgery_scheduled` / `statusId=8 → surgery_completed`; everything else keeps
  `treatment_proposed` / `treatment_completed`. Adds non-PII `is_implant_surgery`
  flag to the safe payload on surgery events only.
- `packages/ingest/schemas.py` — `CareStackTreatmentPlanImportOut`.
- `apps/worker/jobs/ingest_scheduled.py` — wires the TreatmentPlan sweep into
  `pull_carestack_for_tenant` + `backfill_carestack_for_tenant`, folds it into
  `_carestack_counters`, adds `treatment_plan` to the object scope and to the
  CareStack schema-snapshot set.

### Modified — interaction layer (contract)
- `packages/interaction/models.py` — `EVENT_KINDS` (+3), `SOURCE_KINDS` (+1).
- `packages/interaction/schemas.py` — `EventKind`/`SourceKind` Literals +
  `_SOURCE_KINDS_BY_PROVIDER`.
- `packages/interaction/service.py` — `_KIND_VERB` labels + new
  `analytics_surgery_stage_milestones_by_person`.
- `packages/interaction/repository.py` — `analytics_surgery_stage_milestones_by_person`
  (one GROUP BY: earliest of each of the three new kinds per person).

### Modified — analytics layer
- `packages/analytics/fact_builder.py` — reads the new milestones, sets the three
  columns with `method='auto'`, drops them from `_UNRESOLVED_FIELDS`.

### Modified — docs
- `packages/interaction/CLAUDE.md`, `packages/ingest/CLAUDE.md`,
  `packages/integrations/carestack/CLAUDE.md`.

### Modified — tests
- `tests/analytics/test_fact_builder.py` — new fake method + auto-resolution +
  manual>auto no-clobber test for `surgery_completed_date`.
- `tests/ingest/test_carestack_treatment_service.py` — CDT-gated surgical mapping
  tests (implant 2/8 → surgery_*, non-implant → generic, implant non-2/8 →
  generic, unresolved code → fail-closed) + helper tests.
- `tests/interaction/test_repository.py` — real-PG test for the new milestone
  aggregate (skips when DB unavailable).
- `tests/interaction/test_models.py` — canonical `EVENT_KINDS` tuple updated.
- `tests/worker/test_ingest_scheduled.py` — patch new service in the 4 full-pull
  tests + add `treatment_plans` to the asserted result dict.

## What changed per layer (data → service → repo → DB)

1. **DB:** new Alembic revision widening two CHECK constraints (model parity:
   the tuples in `interaction/models.py` regenerate the same constraint SQL).
2. **Ingest (data):** TreatmentPlan client method + per-patient ingest service
   (capture-then-route, full-fidelity raw, ENG-185 identity resolution); procedure
   service gains CDT-gated surgery mapping via `CatalogService`.
3. **Interaction (service/repo):** three new event kinds + one new source_kind;
   builder-facing milestone aggregate.
4. **Analytics (service):** fact builder reads the milestones → three columns
   with auto provenance, manual override preserved.
5. **Worker (wiring):** TreatmentPlan sweep bounded like the payment-summary
   sweep; schema snapshot wired into the existing CareStack schema-refresh job.

## Identity resolution (ENG-185)

The TreatmentPlan ingest uses the ENG-185 cutover pattern: capture raw →
`normalized_person_hint` → `MatchHintIn` → `IdentityService.resolve_or_create_from_hint`
→ `IdentityService.get_person`. Patients to sweep are enumerated via
`IdentityService.source_links_for_dashboard` (the **service**, not the identity
repo — honouring "do not reach into identity repos"). Because the swept patients
are already linked, resolution is a Tier-0 source-link recapture (no
match-candidate row). The hint is written only on the **first** acceptance
observation (guarded by an event-existence pre-check), so re-pulls do not
accumulate redundant hint rows.

## Tests run + results

Run from the worktree with the canonical `.venv` (ruff/mypy/pytest on PATH).

- `ruff check` — **clean** on every touched package + test file.
- `mypy packages/ingest packages/interaction packages/analytics` — **Success, 51 files**.
- `mypy packages/integrations/carestack apps/worker/jobs/ingest_scheduled.py` — **Success, 4 files**.
- `pytest tests/ingest/test_carestack_treatment_plan_service.py` — **13 passed**.
- `pytest tests/ingest/test_carestack_treatment_service.py` — **26 passed**.
- `pytest tests/analytics/test_fact_builder.py` — **16 passed**.
- Combined runnable set (`test_fact_builder`, `test_provenance`,
  `test_models`, `test_repository`, both treatment tests, `integrations/carestack`)
  — **92 passed, 5 skipped** (the 5 skips are real-PG integration tests that skip
  cleanly without a DB, including the new `analytics_surgery_stage_milestones_by_person`
  repo test).

### Verification gaps (environment-limited, NOT logic concerns)
- **`cd packages/db && alembic check` could not run** — the isolated worktree has
  no `.env`, so `Settings` (DATABASE_URL/SECRET_KEY/REDIS_URL) fail to construct,
  and I must not create `.env`. The migration is a pure CHECK widening that
  mirrors the prior funnel-kinds migration pattern (which kept `alembic check`
  clean), revises the current head `a1b2c3d4e5f6`, and its kind/source_kind
  constants exactly mirror the model tuples. **Must be run green with a DB before merge.**
- **`tests/worker/test_ingest_scheduled.py` could not execute** — importing it
  builds the DB engine, which needs the same env; the sandbox blocks setting
  inline env vars for the run. The edits (patch the new service, add
  `treatment_plans` to the asserted dict) mirror the existing passing pattern and
  pass ruff. **Must be run green with a DB before merge.**
- Pre-existing **unrelated** failure in this worktree snapshot:
  `tests/ingest/test_carestack_appointment_service.py::test_map_status_known_values`
  (`_map_status("Checked In")` mapping) — in a file ENG-511 does not touch; fails
  independently of this work.

## CDT codes for operator confirmation

The implant-surgery split is gated on the operator confirming this CANDIDATE set
(constant `_IMPLANT_SURGERY_CDT_CODES` in `packages/ingest/carestack_treatment_service.py`,
annotated `# OPERATOR-CONFIRM`). A procedure whose `procedureCodeId` resolves
(via `CatalogService`) to one of these CDT codes is treated as implant surgery:

| CDT | Description |
| --- | --- |
| D6010 | Surgical placement of implant body: endosteal implant |
| D6011 | Surgical placement of interim / second-stage implant body |
| D6012 | Surgical placement of interim implant body for transitional prosthesis: endosteal |
| D6013 | Surgical placement of mini implant |
| D6040 | Surgical placement: eposteal implant |
| D6050 | Surgical placement: transosteal implant |

Open question for the operator: include abutment/restorative codes (D6056/D6057
abutments, D6058+ crowns) or keep strictly to surgical *placement*? Current set
is surgical placement only. Confirming this list is a **do-not-merge condition**.

## Risks

- **CDT set is provisional** — fail-closed (unknown/unresolved code → generic
  mapping), so a wrong/incomplete list under-counts surgeries rather than
  mislabelling non-surgery procedures. Still gated on operator sign-off.
- **Per-row catalog lookup** in the procedure split (`resolve_procedure_codes`
  one call per row) — N+1 across a page. Each call is a single indexed query;
  acceptable at current volumes, batchable per page later if needed.
- **TreatmentPlan endpoint shape** is documented as ambiguous (array vs object);
  the client normalises array / envelope / single-object. Verify against the live
  API response during the first real pull.
- **TreatmentPlan has no provider modified-stamp** — raw capture uses
  whole-payload content-dedup (mirrors payment-summary). "Acceptance date" =
  first observed `StatusId=3` (`lastUpdatedOn` if present else capture time),
  made stable by event idempotency.
- **Telemetry:** the mission runtime path (`~/.fusion-agent-orchestrator/…/runtime.json`,
  `runlog.md`) is outside the sandbox-allowed working directory, so live updates
  during this run were blocked; progress is captured here instead.

## Do-not-merge conditions

1. **Operator confirms the implant-surgery CDT set** above.
2. **Codex cross-runtime review** of the contract-changing diff (new event kinds /
   source_kind + migration + ingest contract).
3. **`cd packages/db && alembic check` run green** in an environment with the DB
   (no drift beyond the new revision).
4. **`tests/worker/test_ingest_scheduled.py` and the real-PG integration tests**
   (incl. `analytics_surgery_stage_milestones_by_person`) run green with a DB.
5. All changes remain **UNCOMMITTED** — no commit / push / PR / merge / deploy by
   this worker (contract_change: build only).

## Suggested next step

Operator confirms the CDT set → Codex cross-runtime review → orchestrator runs
`alembic check` + worker/integration tests against a DB → integrates
(commit/PR/merge) on operator go.
