# CLAUDE.md — `packages/ingest`

Capture-then-route. We store the raw payload from every external
system EXACTLY as received, then a worker translates it into domain
operations.

## Table (schema `ingest`)

- **`raw_event`** — `source`, `event_type`, `external_id`,
  `received_at`, `payload` (JSONB), `processed_at`, `error`.

## Why capture-then-route

- If our parser has a bug, we replay from `raw_event`.
- If a vendor reshapes their payload, we still have the original.
- Compliance gets a forensic trail of inbound data.

## Full-fidelity capture (ENG-425 / ADR-0005)

Every external object is captured with **100% of the fields it exposes at pull
time**, and newly-added fields are absorbed automatically. Completeness is a
RAW-layer property only — the domain projections (`ops.lead.extra`, etc.) stay
curated; a new field lands in `raw_event` but does not force a domain change.

- **Schema registry** — `ingest.source_object_field` records, per
  `(provider, object, field)`: type, `readable`, `active`, first/last seen.
  `IngestService.sync_object_schema` reconciles an observed schema → drift.
- **Salesforce** — the SOQL projection is built dynamically from `describe`
  per object via `SfSchemaSync` (`sf_schema_sync.py`); the static `_SF_*`
  projections are FALLBACK only. Do NOT re-introduce hand-maintained field
  lists as the primary projection. The Tooling API (non-FLS-filtered) vs
  `describe` diff is the FLS-gap report.
- **CareStack / REST** — never apply a field filter (`fields=` / sparse);
  capture the full object verbatim. `IngestService.snapshot_observed_schema`
  records the schema from the union of observed payload keys.
- **Drift / new fields** — the daily `refresh_*_schemas_*` cron keeps the
  registry current and surfaces drift + FLS gaps in `sync_run.meta`.
- **History** — `infra/scripts/backfill_sf_full_fidelity.py` force re-captures
  a window through the dynamic projection to widen old raw rows.
- The registry stores field NAMES + types only, never values — PHI field names
  (`ssn`, `dob`) are metadata, not PHI.

## Hard rules

- **Capture writes happen before any normalisation.** Do not
  transform, scrub, or reshape `payload` on the way in.
- **Carriers of PHI in `payload`** — many vendor webhooks include
  clinical context. The `ingest` schema's payload is potentially PHI.
  - **Development-phase visibility (current).** The verbatim
    `ingest.raw_event.payload` MAY be surfaced to the authenticated
    staff operator on every environment, including production — the
    Inspector pages under `/dev/inspector/<provider>`, the per-record
    drill-down behind a timeline / payments / person node, and the MCP
    `get_inspector_payload` tool. The only user today is the doctor,
    who already holds full provider access, so payload viewing grants
    no new data. This supersedes the former "Production: do not surface
    verbatim payloads" rule. See the root `CLAUDE.md` →
    "Data visibility posture (development phase)" for the governing
    policy; **role-scoped access and field-level redaction are a
    later layer added on top, not a present restriction.**
  - **Logs are NOT covered.** This is a UI/display posture only.
    Structured logs from workers, API, and MCP must redact PHI in
    happy AND error paths (name, DOB, address, phone, email, MRN-like,
    free-text) — disk and backups outlive the development phase. Log
    keys stay `patient_id` / `provider_id` / counts only.
- **`external_id`** should be the vendor's stable identifier when
  available — used for deduplication.
- **Payments doc-sync rule (ENG-300).** The CareStack payment
  classification in `carestack_accounting_transaction_service.py`
  (`_PAYMENT_CODE_TO_KIND`, `_CASH_REVERSAL_CODES`) and the Collected
  formula it feeds are documented for staff in
  `apps/web/lib/docs/paymentsDoc.ts`. If you change the classification
  (or the Collected aggregate in
  `packages/interaction/repository.py::get_treatment_payment_aggregate`),
  you MUST update that doc — BOTH the `en` and `ru` content — in the
  same change. Code and doc move together.
- Source handlers that resolve people must use the ENG-185 cutover
  pattern: capture the verbatim `raw_event`, capture one
  `normalized_person_hint` using the returned `raw_event.id`, build
  the identity-owned `MatchHintIn` from the returned hint row, call
  `IdentityService.resolve_or_create_from_hint(...)`, then fetch the
  resolved `Person` through `IdentityService.get_person(...)`. Do not
  reach into identity repositories or re-implement email/phone matching
  ladders inside ingest handlers.
- Per-source handlers go under
  `apps/worker/jobs/ingest_<source>.py`. They read from
  `IngestService.list_unprocessed()`, dispatch into
  `IdentityService` / `OpsService` (and `PhiService` if authorised),
  then call `mark_processed`.

## Sources currently shipped

| Provider object | Raw event source / type | Handler |
|---|---|---|
| Salesforce Lead | `salesforce` / `lead.pull` | `packages/ingest/sf_lead_service.py` (`SfLeadIngestService`) |
| Salesforce Event | `salesforce` / `salesforce.event.upsert` | `packages/ingest/sf_event_service.py` (`SfEventIngestService`) |
| Salesforce Task | `salesforce` / `salesforce.task.upsert` | `packages/ingest/sf_task_service.py` (`SfTaskIngestService`) |
| Salesforce Opportunity | `salesforce` / `salesforce.opportunity.upsert` | `packages/ingest/sf_opportunity_service.py` (`SfOpportunityIngestService`) |
| Salesforce Case | `salesforce` / `salesforce.case.upsert` | `packages/ingest/sf_case_service.py` (`SfCaseIngestService`) |
| Salesforce Contact | `salesforce` / `salesforce.contact.upsert` | `packages/ingest/sf_contact_service.py` (`SfContactIngestService`) |
| Salesforce Account | `salesforce` / `salesforce.account.upsert` | `packages/ingest/sf_account_service.py` (`SfAccountIngestService`) |
| Salesforce OpportunityHistory | `salesforce` / `salesforce.opportunity_history.upsert` | `packages/ingest/sf_opportunity_history_service.py` (`SfOpportunityHistoryIngestService`) |
| CareStack Patient | `carestack` / `carestack.patient.upsert` | `packages/ingest/carestack_patient_service.py` (`CareStackPatientIngestService`) |
| CareStack Appointment | `carestack` / `carestack.appointment.upsert` | `packages/ingest/carestack_appointment_service.py` (`CareStackAppointmentIngestService`) |
| CareStack Treatment Procedure | `carestack` / `carestack.treatment_procedure.upsert` | `packages/ingest/carestack_treatment_service.py` (`CareStackTreatmentIngestService`) |
| CareStack Treatment Plan | `carestack` / `carestack.treatment_plan.upsert` | `packages/ingest/carestack_treatment_plan_service.py` (`CareStackTreatmentPlanIngestService`) |
| CareStack Invoice | `carestack` / `carestack.invoice.upsert` | `packages/ingest/carestack_invoice_service.py` (`CareStackInvoiceIngestService`) |
| CareStack Accounting Transaction | `carestack` / `carestack.accounting_transaction.upsert` | `packages/ingest/carestack_accounting_transaction_service.py` (`CareStackAccountingTransactionIngestService`) |
| CareStack Payment Summary | `carestack` / `carestack.payment_summary.snapshot` | `packages/ingest/carestack_payment_summary_service.py` (`CareStackPaymentSummaryIngestService`) |
| Meta Ads campaign insight | `meta_ads` / `meta_ads.campaign_metric.upsert` | `packages/ingest/meta_ads_campaign_service.py` (`MetaAdsCampaignIngestService`) |
| Meta Ads ad insight | `meta_ads` / `meta_ads.ad_metric.upsert` | `packages/ingest/meta_ads_ad_service.py` (`MetaAdsAdIngestService`) — ENG-512 |

`apps/worker/jobs/ingest_scheduled.py` wires the scheduled provider pulls.
The placeholder `process_unprocessed_events` job remains only for generic
buffer processing examples; it is not the workflow-ready provider handler.

## Shared workflow-ready helpers

- **`consultation_timeline.py`** centralises appointment/consultation status
  mapping into workflow-ready `interaction.event` rows. Salesforce Event and
  CareStack Appointment handlers use it so scheduled, rescheduled, cancelled,
  completed, and no-show semantics stay consistent.
- **`call_reference.py`** is a pure extractor for safe call/meeting pointers.
  Free text is restricted to an allowlist of known call/meeting domains.
  Structured allowlisted keys such as Salesforce `Task.CallObject` may also
  produce `provider="other"` URLs or opaque external ids. The helper never
  fetches URLs, downloads recordings, transcribes audio, or calls external
  services.

Update these tables and helper notes when a new integration or shared ingest
semantic lands.

## CareStack scheduled pull — how it works & why (read before "debugging" partial syncs)

> Written 2026-06-04 after ENG-329. Goal: never re-investigate "why is
> CareStack always `partial` / worker yellow" from scratch again.

### The flow

`apps/worker/jobs/ingest_scheduled.py::pull_carestack_for_tenant` runs hourly
(arq cron, minute `:13`). Per tick it opens ONE `sync_run` and pulls, in order:
`locations → patients (days=1) → appointments (days=1) → treatments (days=7) →
invoices (days=7) → accounting_transactions (days=7) → payment_summaries
(rolling 50 + targeted)`. Each per-object service returns an envelope with
`imported_count` / `skipped_count`; `_carestack_counters()` aggregates them into
the `sync_run` row.

### The CareStack sync API is forward-only, ascending, cursor-paginated

Every `list_*_modified_since` hits a `/sync/...` endpoint that accepts ONLY
`modifiedSince` + `continueToken` and returns rows **ascending by
`lastUpdatedOn`** with an opaque `continueToken` (null = caught up). **There is
no sort / descending / "newest first" option** — confirmed in
`docs/integrations/carestack/sync/*.md`. The only way to "get new rows first /
stop re-reading old ones" is to **resume from where you left off** — not to
reorder. We do this with a high-watermark on `lastUpdatedOn` derived from
already-captured rows (ENG-324; see below), not by reordering the feed.

### Why CareStack shows `partial` with a big `records_failed` — and why that is (mostly) NOT a failure

`records_failed` is built from `*_skipped`, but "skipped" lumps THREE different
outcomes together (see `_capture_*` in each service):

1. **Idempotent dedup** — the row was imported on a previous run, so
   `InteractionService.create_event_idempotent` returns `was_created=False` and
   the row counts as `skipped`. **This is healthy and logs nothing.** It is the
   dominant contributor (~94% of the daily "failures").
2. **`no patientId in payload`** — practice-level invoices / advance payments /
   unattached transactions legitimately have no patient. By design; logs at
   WARNING. Small tail (~tens/run).
3. **`patient not yet linked`** — patientId present but no `identity.source_link`
   yet (patient pull is `days=1`, financial pulls are `days=7`). Rare in
   practice (observed 0), self-heals on the next patient pull.

So a "1260 failed / 470 succeeded `partial`" CareStack run is normal: the 7-day
pull window overlaps every hour, re-reads already-imported rows, dedup-skips
them, and the counter calls that `failed`. **Do not treat `partial` alone as an
incident** — check the `error` column and the WARNING-logged skip reasons first.

### Starvation of newest rows — already fixed by ENG-324 (watermark)

A scheduled pull that always restarts from `modifiedSince = now − 7d` with
`continue_token=None` could never reach the newest rows on a busy tenant: when
`treatments` / `accounting_transactions` exceed `max_pages=5` (500 rows) inside
the window, all 5 pages are spent on the OLDEST (already-imported) rows and
page 6+ (the new ones) is never reached. `imported_count≈0` with a non-null
`next_continue_token` was the tell.

**This is fixed by `packages/ingest/sync_window.py` (ENG-324):** each run resumes
`modifiedSince` from the highest `lastUpdatedOn` already captured in
`ingest.raw_event` (`IngestService.max_payload_watermark` + `resume_modified_since`,
minus a 10-min overlap that the `(id, lastUpdatedOn)` idempotency key dedupes).
So the feed advances run-to-run and the import date tracks "now", not "now − 7d".
No cursor table is needed — the watermark is derived from already-persisted rows.
(ENG-329 originally proposed a persistent `continueToken` cursor table; it was
dropped as redundant once ENG-324 landed.)

### The metric still lied — fixed by ENG-329 (counter split)

Even with the watermark, the 10-min overlap re-reads plus practice-level
`no patientId` rows are dedup/skip outcomes that `_carestack_counters` used to
fold into `records_failed`, keeping CareStack permanently `partial`. ENG-329
splits the per-row outcome into **`imported` / `unchanged` / `skipped`**:
`unchanged` = idempotent dedup (`create_event_idempotent`/consultation-upsert
returned no write) is HEALTHY and surfaced in `sync_run.meta.unchanged`, kept OUT
of `failed`; `failed` now counts ONLY genuine skips (missing source id, no
`patientId`, unlinked patient) + payment-summary errors. Result: a steady-state
re-read run reports `succeeded` with `records_failed == 0`, not `partial`.

### The dashboard "Worker" tile is ingest-freshness, not process liveness

`/health/services` (`apps/api/routers/health.py`) derives `worker` status purely
from the newest `sync_run.started_at`: `< 2h → ok`, else `stale` (yellow),
none → `unknown`. A yellow "Worker" usually means **no recent sync_run**, which
on a laptop almost always means the Mac was asleep at `:13` (arq cron is
wall-clock and does not fire while macOS is suspended) — NOT a dead worker.
Confirm liveness via the arq health key in Redis
(`redis-cli get arq:health-check` → `j_complete/j_failed/...`) before assuming a
crash. Forcing a fresh tick: enqueue `ingest_scheduled_fanout` onto the live
arq pool.
