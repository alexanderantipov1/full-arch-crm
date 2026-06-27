# Acceptance — sf-funnel-ingest-v1

## ENG-381 (idempotent ingest)

1. Each scheduled SF puller (lead, event, task, opportunity, case) queries
   with a `LastModifiedDate > watermark` cursor when a watermark exists,
   falling back to the current fixed window on first run.
2. Each CareStack puller in scope (appointment, patient, treatment_procedure)
   uses its provider modified-stamp the same way (pattern already used by
   invoice + accounting-transaction services).
3. Re-running a pull against unchanged provider data writes ZERO new
   ingest.raw_event rows (change-guard skips identical modified-stamps).
4. `carestack.payment_summary.snapshot` writes a new snapshot only when the
   snapshot content differs from the latest stored snapshot for that patient.
5. A one-off cleanup script exists, defaults to dry-run, reports per
   event_type counts, and on `--apply` deletes duplicate raw rows keeping
   (a) the newest row per (tenant, event_type, external_id, modified-stamp)
   and (b) every row referenced by interaction.event.source_event_id or
   ingest.normalized_person_hint.raw_event_id.
6. Watermark queries keep a small overlap window for clock skew; deep
   backfill lanes that intentionally ignore watermarks stay intact.
7. Unit tests cover: watermark used when present, fallback when absent,
   unchanged rows skipped, changed rows captured, payment-summary content
   dedupe, cleanup keep-rules.

## ENG-382 (SF funnel provenance) — after ENG-381

See Linear issue scope items 1-7 (conversion fields, attribution fields,
opportunity person link + timeline events, effective source, Contact pull,
Account pull, OpportunityHistory events).
