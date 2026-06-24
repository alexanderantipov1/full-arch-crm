# Manager Analytics Read Models V1

This document defines the first service-computed manager analytics read models
for the Semantic Context And Analytics Foundation mission.

V1 does not create persisted tables, materialized views, or migrations. The
read models are computed through approved service handlers and surfaced through
the `run_analytics_query` tool envelope. Persisted models can be added after
metric definitions, row-level policy, export policy, and dashboard consumers
stabilize.

## Shared Contract

Every V1 read model response includes:

- `query_id`: canonical versioned registry query id.
- `read_model_id`: stable dashboard/chat-facing read model id.
- `output_type`: `aggregate`.
- `aggregation_level`: `aggregate`.
- `data_classes`: data classes touched by the result.
- `definition_versions`: semantic terms used by the result.
- `filters`: applied filter echo.
- `row_count`: aggregate bucket count, not patient/person row count.
- `warnings`: definition or coverage warnings.
- `drilldown_available`: `false` in V1.
- `export_available`: `true` for aggregate CSV exports after ENG-281.
- `result`: read-model-specific aggregate payload.

The contract is intentionally aggregate-only in V1. Row-level drilldowns remain
allowed by the human decision for authorized internal users, but they are not
implemented in this read-model slice.

## `lead_conversion`

- Query id: `lead_conversion_funnel.v1`
- Handler: `run_analytics_query` ->
  `OpsService.get_conversion_funnel_analytics`
- Storage posture: service-computed
- Data classes: `ops`, `integration_metadata`
- Output posture: aggregate
- Source references: lead status counts and consultation status counts from
  service-owned repositories.
- Result fields:
  - `lead_status`: aggregate buckets by lead status.
  - `consultation_status`: aggregate buckets by consultation status.
  - `pipeline_total`: active leads excluding lost.
  - `consultations_total`: total consultations in the filter window.
  - `completed_consultations`: completed consultation count.
- Notes:
  - V1 does not calculate conversion rate percentages in the backend. Consumers
    may display percentages derived from returned counts while preserving the
    source counts.

## `paid_leads`

- Query id: `paid_leads_by_source.v1`
- Handler: `run_analytics_query` -> `OpsService.get_paid_leads_analytics`
- Storage posture: service-computed
- Data classes: `ops`, `integration_metadata`
- Output posture: aggregate
- Source references: CRM-safe lead source and campaign labels.
- Result fields:
  - `total_paid_leads`: total count of leads classified as paid-source.
  - `sources`: aggregate buckets by source label.
  - `classification_terms`: V1 classifier terms.
- Notes:
  - V1 uses explicit source/campaign label heuristics such as Google, Meta,
    Facebook, Instagram, PPC, paid, AdWords, paid search, and paid social.
  - V1 does not inspect raw provider payloads.
  - Campaign normalization is a later hardening task.

## `consultation_followup`

- Query id: `consultation_followup_worklist.v1`
- Handler: `run_analytics_query` ->
  `OpsService.get_consultation_followup_analytics`
- Storage posture: service-computed
- Data classes: `ops`, `integration_metadata`
- Output posture: aggregate
- Source references: consultation status counts and follow-up task counts.
- Result fields:
  - `consultation_status`: aggregate buckets by consultation status.
  - `open_followups`: open tenant-wide follow-up task count.
  - `overdue_followups`: overdue tenant-wide follow-up task count.
- Notes:
  - V1 does not return a row-level worklist. The query registry keeps worklist
    semantics documented for the next row-level slice.

## `treatment_revenue`

- Query id: `treatment_revenue_evidence.v1`
- Handler: `run_analytics_query` ->
  `InteractionService.get_treatment_payment_aggregate`
- Storage posture: service-computed
- Data classes: `billing`, `integration_metadata`
- Output posture: aggregate
- Source references: workflow-ready interaction events emitted by CareStack
  treatment, invoice, and accounting-transaction ingest.
- Result fields:
  - `treatment_presented_count`
  - `treatment_completed_count`
  - `invoice_count`
  - `payment_total_amount`
  - `collected_total`
  - `payment_event_count`
  - `first_payment_at`
  - `last_payment_at`
- Notes:
  - This read model is billing-sensitive but aggregate-only in V1.
  - It does not expose raw CareStack payloads, clinical procedure text,
    tooth/surface data, notes, or patient identifiers.

## Deferred Read Models

The following remain deferred:

- `outstanding_balance`: needs export and billing row-level policy review.
- `source_quality_gaps`: belongs with Data Intelligence Agent gap brief
  tooling and source profiling.
- row-level `consultation_followup` worklist: requires row field allowlist,
  result caps, and manager UI workflow.

## Verification

V1 verification requires:

- the query registry maps each read model to a canonical query id;
- `run_analytics_query` returns `read_model_id` for implemented query ids;
- aggregate result envelopes include filter echo and semantic definition
  versions;
- drilldown flags stay false and export flags are true only for aggregate CSV
  exports;
- no raw SQL, direct repository access from tools, or raw provider payload
  output is introduced.
