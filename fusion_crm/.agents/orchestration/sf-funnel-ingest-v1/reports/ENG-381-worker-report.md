# ENG-381 Worker Report — Idempotent ingest

- **Task:** ENG-381 — Idempotent ingest: watermark + change-guard across
  SF/CareStack pullers, dedupe cleanup
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-381/idempotent-ingest-watermark-change-guard-across-sfcarestack-pullers
- **Role / agent:** worker / claude-code (self-execute)
- **Branch / worktree:** codex/eng-371-manager-answer-layer-v1 / canonical checkout
- **Allowed scope:** packages/ingest, apps/worker/jobs, tests/ingest,
  tests/worker, tests/infra, infra/scripts (per ownership.yaml)

## What changed

Core (capture change-guard support):
- `packages/ingest/repository.py` — `latest_payload_values` (batch max
  modified-stamp per external_id, GROUP BY + lexical max over fixed-format
  ISO stamps) and `latest_payload` (newest payload for one external_id,
  for content-level dedupe).
- `packages/ingest/service.py` — pass-through wrappers for both.

SF pullers (watermark + guard, `LastModifiedDate`):
- `sf_lead_service.py` — scheduled sync switched from "newest 50 by
  CreatedDate" to a modified-since watermark cursor (`_SF_SOQL_SYNC`,
  ASC). LastModifiedDate ADDED to the SOQL projection. Capture guard in
  the sync path and in `pull_all_since` backfill (its "re-runs write
  fresh raw rows" contract is replaced by skip-unchanged). Manual
  `pull_recent` (operator button) intentionally unchanged.
- `sf_event_service.py`, `sf_task_service.py`, `sf_opportunity_service.py`,
  `sf_case_service.py` — watermark resume via `resume_modified_since`
  (10-min overlap) + per-batch capture guard; recent SOQLs flipped
  DESC→ASC (load-bearing: with DESC + LIMIT a burst larger than the
  limit would advance the watermark past never-captured changes).
- `unchanged_count` added to the four `Sf*ImportOut` schemas and
  `SfLeadPullSummary`; `_salesforce_counters` in
  `apps/worker/jobs/ingest_scheduled.py` now emits the ENG-329-style
  `unchanged` bucket into sync_run meta (kept OUT of `failed`).

CareStack pullers (`lastUpdatedOn`):
- `carestack_appointment_service.py`, `carestack_patient_service.py` —
  watermark resume (previously fixed `days` window) + capture guard in
  recent and `pull_all_since` paths; `unchanged_count` added to
  `CareStackPatientImportOut`.
- `carestack_treatment_service.py` — watermark already existed (ENG-324);
  capture guard added to recent + deep-backfill paths (deep backfill
  still ignores the watermark by design; the guard only prevents
  re-writing identical rows).

Payment summary (owner decision):
- `carestack_payment_summary_service.py` —
  `_capture_snapshot_if_changed`: snapshot written only when content
  differs from the latest stored snapshot for the patient. All three
  paths (rolling sweep, targeted, backfill) use it; `unchanged_count`
  in `CareStackPaymentSummaryImportOut`. Accepted side effect: "Last
  snapshot" surfaces now mean "balance last changed/written".

Cleanup script:
- `infra/scripts/cleanup_raw_event_duplicates.py` — dry-run default;
  groups by (tenant, event_type, external_id, COALESCE(stamp,
  md5(payload))) keeping the newest; never deletes rows referenced by
  `interaction.event.source_event_id` or
  `normalized_person_hint.raw_event_id`; `--apply` deletes in committed
  batches; idempotent.

## Tests run

- New: `tests/ingest/test_ingest_idempotency_sql.py` (real-PG double
  import: second run writes ZERO raw rows; changed stamp writes exactly
  one more; watermark visible in the second SOQL) — the acceptance
  criterion in executable form.
- New: `tests/infra/test_cleanup_raw_event_duplicates.py` (keep-newest,
  FK keep-rules, content-hash grouping, apply path) — real PG.
- New guard/watermark unit tests in `test_sf_task_service.py` and
  `test_carestack_payment_summary_service.py`; mock fixtures updated in
  6 test files; 2 exact-dict API assertions extended with
  `unchanged_count`.
- Full verify: `make lint` ✓, `mypy .` (360 files) ✓, full `pytest`
  1426 passed ✓, `alembic check` — no new operations (no migrations,
  per contract).

## Verification status

PASSED. Dry-run against the local DB reports **2,171,968 deletable
duplicate rows** (appointment 827k, opportunity 420k, task 400k,
accounting-transaction 201k, treatment 146k, payment-summary 115k,
invoice 60k). `--apply` NOT executed — requires explicit human approval
per decision-log.

## Risks

- lead.pull and carestack.patient duplicates (343k + 235k rows) are
  pinned by `normalized_person_hint` FK references — the keep-rule
  protects them by design; cleaning them requires a hint-chain dedupe
  (follow-up candidate, not in ENG-381 scope).
- Local arq worker was NOT running during the work (last raw event
  19:55Z); the new watermark behavior activates on the next worker
  start. Prod jobs (fusion-job-sf-pull / cs-pull) pick it up on next
  deploy.
- First post-deploy lead tick resumes from `LastModifiedDate` watermark
  = none (old payloads lack the field) → falls back to a 7-day window
  and progressively captures up to 50 rows/tick with the new field; one
  extra capture per touched lead, then steady-state dedupe.

## Blockers / questions

- `--apply` of the cleanup script awaits owner approval.

## Suggested next task

ENG-382 (SF funnel provenance) — new pullers must reuse the watermark +
guard pattern from this change.

## Do-not-merge conditions

- Do not merge together with the parallel Codex working-tree changes
  (`packages/agent_runtime`, `packages/integrations/openai`,
  `apps/web/package.json`) — commit by path separation.
