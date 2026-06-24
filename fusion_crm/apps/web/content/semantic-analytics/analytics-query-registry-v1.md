# Analytics Query Registry V1

The query registry is the allowlist of executable analytics queries. It maps
validated `analytics_query_spec.v1` requests to backend service-owned query
handlers. It is not a SQL catalog and must never expose raw SQL to clients,
LLM planners, dashboards, chat, or agents.

## Registry Goals

- Make approved analytics queries discoverable by dashboard, chat, workbench,
  and internal Data Intelligence Agent surfaces.
- Bind query specs to service-owned execution paths.
- Declare params schema, result schema, data classes, output posture, audit,
  row limits, export posture, and AI-chat safety flags.
- Prevent metric drift by requiring catalog term versions.

## Registry Entry Shape

```yaml
query_id: paid_leads_by_source.v1
title: Paid leads by source
description: Count and drill into leads with payment evidence grouped by source.
status: draft|review-ready|approved-v1|blocked
owner: marketing analytics
service_owner: LeadAnalyticsService
handler: paid_leads_by_source
question_refs:
  - Q16
catalog_terms:
  paid_lead: v1
  lead_source: v1
params_schema_ref: analytics_query_spec.v1
result_schema_ref: analytics_result.table.v1
allowed_roles:
  - authorized_internal
allowed_environments:
  - local
  - staging
  - production
data_classes:
  - ops
  - identity
  - billing
phi_possible: false
billing_possible: true
max_row_count: 1000
default_limit: 100
sample_policy: masked_samples_allowed
export_policy: aggregate_csv_allowed
audit_required: true
safe_for_manager_ai_chat: true
safe_for_data_intelligence_agent: true
raw_payload_allowed: false
```

## Required Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `query_id` | yes | Stable id with version suffix. |
| `status` | yes | Review lifecycle state. |
| `service_owner` | yes | Backend service that owns business logic. |
| `handler` | yes | Service method or future callable query handler. |
| `catalog_terms` | yes | Terms and versions used by the query. |
| `data_classes` | yes | Data classes touched by params/results. |
| `allowed_roles` | yes | V1 uses `authorized_internal`. |
| `max_row_count` | yes | Hard cap for row-level results. |
| `audit_required` | yes | Whether execution audit is mandatory. |
| `raw_payload_allowed` | yes | Must be false for ordinary analytics queries. |

## Initial Query Entries

### `lead_source_profile.v1`

- Status: `implemented-v1`
- Owner: marketing analytics
- Service owner: `OpsService`
- Handler: `run_analytics_query` -> `OpsService.get_lead_source_profile`
- Tool query ids: `lead_source_profile.v1`, alias `lead_source_profile`
- Read model id: `lead_source_profile`
- Questions: Q14, Q16, Q17, Q18, Q21, Q25
- Terms: `lead_source`, `source_provider`
- Data classes: `ops`, `integration_metadata`
- Output: aggregate source buckets
- Max row count: aggregate only
- Audit required: true
- Manager AI chat: safe
- Data Intelligence Agent: safe
- Export: CSV aggregate allowed under ENG-281; XLSX, scheduled, and row-level
  exports denied.

### `lead_conversion_funnel.v1`

- Status: `implemented-v1`
- Owner: marketing analytics
- Service owner: `OpsService`
- Handler: `run_analytics_query` -> `OpsService.get_conversion_funnel_analytics`
- Tool query ids: `lead_conversion_funnel.v1`, alias `conversion_funnel`
- Read model id: `lead_conversion`
- Questions: Q17, Q19, Q29
- Terms: `lead_source`, `consultation_scheduled`,
  `consultation_completed`, `treatment_accepted`, `payment_received`
- Data classes: `ops`, `identity`, `billing`, `integration_metadata`
- Output: aggregate funnel
- Max row count: aggregate only
- Audit required: true
- Manager AI chat: safe
- Data Intelligence Agent: safe
- Export: CSV aggregate allowed under ENG-281; XLSX, scheduled, and row-level
  exports denied.

### `paid_leads_by_source.v1`

- Status: `implemented-v1`
- Owner: marketing analytics
- Service owner: `OpsService`
- Handler: `run_analytics_query` -> `OpsService.get_paid_leads_analytics`
- Tool query ids: `paid_leads_by_source.v1`, alias `paid_leads`
- Read model id: `paid_leads`
- Questions: Q16, Q17, Q18, Q21, Q25
- Terms: `paid_lead`, `lead_source`, `facebook_source`,
  `google_ads_source`, `payment_received`, `revenue_evidence`
- Data classes: `ops`, `integration_metadata`
- Output: aggregate paid-source buckets
- Max row count: aggregate only
- Audit required: true
- Manager AI chat: safe with source references and definition versions
- Data Intelligence Agent: safe
- Export: CSV aggregate allowed under ENG-281; XLSX, scheduled, and row-level
  exports denied.

### `consultation_followup_worklist.v1`

- Status: `implemented-v1`
- Owner: operations analytics
- Service owner: `OpsService`
- Handler: `run_analytics_query` -> `OpsService.get_consultation_followup_analytics`
- Tool query ids: `consultation_followup_worklist.v1`, alias `consultation_followup`
- Read model id: `consultation_followup`
- Questions: Q1, Q2, Q8, Q11, Q24, Q27, Q30
- Terms: `consultation_completed`, `no_next_action`,
  `stale_followup`, `reactivation_candidate`, `carestack_linked`
- Data classes: `ops`, `identity`, `integration_metadata`
- Output: aggregate consultation and follow-up workload
- Max row count: aggregate only
- Audit required: true
- Manager AI chat: safe
- Data Intelligence Agent: safe
- Export: CSV aggregate allowed under ENG-281; XLSX, scheduled, and row-level
  exports denied.

### `treatment_revenue_evidence.v1`

- Status: `implemented-v1`
- Owner: revenue analytics
- Service owner: `InteractionService`
- Handler: `run_analytics_query` -> `InteractionService.get_treatment_payment_aggregate`
- Tool query ids: `treatment_revenue_evidence.v1`, alias `revenue_evidence`
- Read model id: `treatment_revenue`
- Questions: Q3, Q4, Q5, Q9, Q12, Q21
- Terms: `treatment_proposed`, `treatment_accepted`,
  `payment_received`, `revenue_evidence`
- Data classes: `billing`, `integration_metadata`
- Output: aggregate treatment/payment evidence
- Max row count: aggregate only
- Audit required: true
- Manager AI chat: safe for aggregate summaries
- Data Intelligence Agent: safe for profiling and gap briefs
- Export: CSV aggregate allowed under ENG-281; XLSX, scheduled, and row-level
  exports denied.
- Notes: V1 exposes billing-sensitive aggregate evidence only. It does not
  expose patient identifiers, clinical procedure text, tooth/surface data,
  notes, or PHI-adjacent row-level treatment details.

### `outstanding_balance_worklist.v1`

- Status: `draft`
- Owner: revenue analytics
- Service owner: `RevenueAnalyticsService`
- Questions: Q6, Q26
- Terms: `balance_outstanding`, `treatment_accepted`,
  `payment_received`
- Data classes: `billing`, `identity`, `integration_metadata`
- Output: row-level worklist and aggregate totals
- Max row count: 500
- Audit required: true
- Manager AI chat: safe after field allowlist review
- Data Intelligence Agent: safe for profiling and gap briefs
- Export: denied until ENG-281

### `source_quality_gaps.v1`

- Status: `review-ready`
- Owner: data quality analytics
- Service owner: `DataIntelligenceService`
- Questions: Q13, Q15, Q23, Q28
- Terms: `carestack_linked`, `source_reference_missing`,
  `unlinked_salesforce_lead`
- Data classes: `ops`, `identity`, `integration_metadata`
- Output: aggregate + row-level data-quality worklist
- Max row count: 1000
- Audit required: false unless row-level identifiers are exposed
- Manager AI chat: safe for summaries; row-level workbench preferred
- Data Intelligence Agent: safe
- Export: denied until ENG-281

## Discovery Contract

Registry discovery should return only metadata safe for the caller:

```json
{
  "query_id": "paid_leads_by_source.v1",
  "title": "Paid leads by source",
  "description": "Count and drill into leads with payment evidence grouped by source.",
  "status": "implemented-v1",
  "question_refs": ["Q16", "Q17"],
  "catalog_terms": {"paid_lead": "v1", "lead_source": "v1"},
  "data_classes": ["ops", "integration_metadata"],
  "output_levels": ["aggregate"],
  "drilldown_available": false,
  "export_available": true,
  "safe_for_manager_ai_chat": true
}
```

Discovery must not return raw provider payloads, SQL, table names, or direct
repository details.

## Execution Order

```text
validated query spec
-> policy preflight
-> registry lookup
-> service handler
-> repository calls
-> result contract
-> audit completion metadata
```

Routes, UI clients, chat planners, and agents never call repositories or SQL
directly.

## Result Schema Families

- `analytics_result.metric.v1`: scalar metric set.
- `analytics_result.table.v1`: bounded rows with field allowlist.
- `analytics_result.funnel.v1`: stage counts and rates.
- `analytics_result.worklist.v1`: row-level operational queue.
- `analytics_result.gap_brief.v1`: data-quality findings for workbench and
  Data Intelligence Agent.

## Implementation Notes

- Registry can begin as Python structured constants or Pydantic models.
- Query ids should be versioned and stable.
- Adding or changing query semantics requires catalog version review.
- A query with `status=blocked` must not execute.
- A query with `status=draft` may be visible in workbench but not production
  chat unless explicitly allowed.

## First Backend Handoff

The first implementation wave should build:

1. registry models and validation;
2. discovery endpoint/service for workbench and chat planner;
3. query lookup by `query_id`;
4. policy preflight integration hooks;
5. no execution until service handlers are implemented under ENG-277.
