# Structured Analytics Query Spec V1

This spec defines the JSON contract used by manager dashboards, manager AI
chat planners, internal workbench screens, Data Intelligence Agent tooling, and
analytics services. The spec is not SQL and must never contain raw SQL.

## Design Goals

- Express approved analytics requests with typed intents, catalog terms,
  filters, dimensions, metrics, output levels, and result options.
- Make ambiguous or unsafe requests explicit before execution.
- Let policy preflight evaluate the request before services run.
- Let UI and chat use the same contract so metric definitions do not drift.

## Top-Level Schema

```json
{
  "schema_version": "analytics_query_spec.v1",
  "request_id": "uuid-or-client-generated-id",
  "intent": "list_cohort",
  "cohort": "paid_lead",
  "question_ref": "Q16",
  "filters": {
    "date_range": {
      "preset": "last_30_days"
    },
    "lead_source": ["facebook_source"],
    "location_id": ["uuid"]
  },
  "dimensions": ["lead_source", "location"],
  "metrics": ["paid_lead_count", "payment_total"],
  "output": {
    "level": "aggregate_drilldown",
    "shape": "table",
    "limit": 100,
    "include_source_references": true,
    "include_definition_versions": true
  },
  "explain": true
}
```

## Required Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | Must be `analytics_query_spec.v1`. |
| `intent` | yes | One approved intent. |
| `cohort` | conditional | Required for cohort/list/funnel requests. Must be a catalog term. |
| `filters` | yes | Typed filter object. Empty object is allowed only for explicitly safe defaults. |
| `dimensions` | yes | List of approved dimensions. Empty list allowed for scalar summaries. |
| `metrics` | yes | List of approved metrics. |
| `output` | yes | Requested output posture and shape. |

## Approved Intents

| Intent | Purpose | Example |
| --- | --- | --- |
| `summarize_metric` | Single metric or small metric set. | payment total for Facebook leads |
| `list_cohort` | Row-level or bounded cohort list. | accepted treatment with no payment |
| `compare_periods` | Compare metrics across two date ranges. | paid lead rate this month vs last month |
| `breakdown_by_dimension` | Group metrics by one or more dimensions. | no-show rate by campaign |
| `trace_conversion` | Funnel or lifecycle path. | lead to consult to treatment to payment |
| `find_gaps` | Data quality or missing evidence. | unlinked Salesforce leads |
| `drilldown` | Row-level expansion from an aggregate result. | rows behind paid lead count |
| `export_allowed_rows` | Export request, disabled until export policy is approved. | CSV of permitted rows |

## Output Levels

| Level | Meaning |
| --- | --- |
| `aggregate` | Counts, sums, rates, and group-bys. |
| `aggregate_drilldown` | Aggregate primary view with row-level drilldown allowed. |
| `row_level` | Bounded row-level worklist. |

Current production users are treated as authorized internal users, so row-level
analytics is allowed in this mission phase. Policy preflight still checks data
classes, field allowlists, source references, audit posture, and PHI routing.

## Allowed Filter Types

```json
{
  "date_range": {
    "preset": "last_30_days",
    "from": "2026-05-01",
    "to": "2026-05-30"
  },
  "lead_source": ["facebook_source", "google_ads_source"],
  "campaign_id": ["string"],
  "utm_source": ["string"],
  "utm_medium": ["string"],
  "utm_campaign": ["string"],
  "location_id": ["uuid"],
  "business_unit": ["string"],
  "owner_id": ["uuid"],
  "provider_id": ["uuid"],
  "consultation_status": ["scheduled", "completed", "no_show", "cancelled"],
  "treatment_status": ["proposed", "accepted", "completed", "not_accepted"],
  "payment_status": ["received", "failed", "refunded", "balance_outstanding"],
  "min_amount": 0,
  "min_days_since_event": 0,
  "as_of_date": "2026-05-30"
}
```

Unknown filters must fail validation or produce a clarification request. The
planner must not silently map unknown fields to raw provider fields.

## Initial Dimensions

- `date`
- `lead_source`
- `semantic_source_channel`
- `campaign`
- `utm_source`
- `utm_medium`
- `utm_campaign`
- `business_unit`
- `location`
- `owner`
- `provider`
- `source_system`
- `consultation_status`
- `treatment_status`
- `payment_status`

## Initial Metrics

- `lead_count`
- `consultation_scheduled_count`
- `consultation_completed_count`
- `consultation_conversion_rate`
- `no_show_count`
- `no_show_rate`
- `treatment_proposed_count`
- `treatment_accepted_count`
- `treatment_accepted_amount`
- `payment_count`
- `payment_total`
- `paid_lead_count`
- `paid_lead_rate`
- `outstanding_balance_total`
- `stale_followup_count`
- `reactivation_candidate_count`
- `link_rate`
- `time_to_consultation`
- `time_to_payment`

## Validation Rules

1. `intent` must be one of the approved intents.
2. `cohort`, dimensions, metrics, and semantic filters must reference catalog
   terms or registry-approved fields.
3. Query specs must not contain SQL strings, table names, join clauses, or raw
   provider field paths.
4. Requested output level must be allowed by catalog and policy preflight.
5. Row-level requests must include a bounded date range or explicit limit.
6. Export requests must be denied until export policy is approved.
7. PHI data classes require `PhiService` routing and audit; V1 terms should not
   require clinical-note PHI.
8. Ambiguous source attribution, stale thresholds, payment evidence definition,
   or balance source-of-truth must produce clarification or use a catalog
   default with the default shown in the result explanation.

## Clarification Shape

```json
{
  "type": "clarification_required",
  "reason": "ambiguous_attribution_model",
  "question": "Should this use first-touch, last-touch, or the catalog default attribution model?",
  "options": ["catalog_default", "first_touch", "last_touch"],
  "safe_default": "catalog_default"
}
```

## Result Contract

Every service result should include:

```json
{
  "query_id": "paid_leads_by_source.v1",
  "generated_at": "2026-05-30T00:00:00Z",
  "definition_versions": {
    "paid_lead": "v1",
    "facebook_source": "v1"
  },
  "applied_filters": {},
  "data_classes": ["ops", "identity", "billing"],
  "output_level": "aggregate_drilldown",
  "row_count": 10,
  "rows": [],
  "warnings": [],
  "drilldown_available": true,
  "export_available": false
}
```

## Examples

### Paid Facebook Leads

```json
{
  "schema_version": "analytics_query_spec.v1",
  "intent": "breakdown_by_dimension",
  "cohort": "paid_lead",
  "question_ref": "Q17",
  "filters": {
    "date_range": {"preset": "last_30_days"},
    "lead_source": ["facebook_source"]
  },
  "dimensions": ["location"],
  "metrics": ["paid_lead_count", "payment_total"],
  "output": {
    "level": "aggregate_drilldown",
    "shape": "table",
    "limit": 100,
    "include_source_references": true,
    "include_definition_versions": true
  },
  "explain": true
}
```

### No Next Action Worklist

```json
{
  "schema_version": "analytics_query_spec.v1",
  "intent": "list_cohort",
  "cohort": "no_next_action",
  "question_ref": "Q2",
  "filters": {
    "date_range": {"preset": "last_90_days"},
    "min_days_since_event": 7
  },
  "dimensions": [],
  "metrics": ["stale_followup_count"],
  "output": {
    "level": "row_level",
    "shape": "worklist",
    "limit": 100,
    "include_source_references": true,
    "include_definition_versions": true
  },
  "explain": true
}
```

### Data Quality Gap

```json
{
  "schema_version": "analytics_query_spec.v1",
  "intent": "find_gaps",
  "cohort": "unlinked_salesforce_lead",
  "question_ref": "Q28",
  "filters": {
    "date_range": {"preset": "last_30_days"}
  },
  "dimensions": ["lead_source"],
  "metrics": ["lead_count", "link_rate"],
  "output": {
    "level": "aggregate_drilldown",
    "shape": "table",
    "limit": 100,
    "include_source_references": true,
    "include_definition_versions": true
  },
  "explain": true
}
```

## Handoff To Policy Preflight

Policy preflight receives the validated spec plus authenticated principal and
environment context. It decides:

- allow;
- deny;
- clarify;
- allow with warnings;
- allow aggregate but deny export.

## Handoff To Query Registry

The query registry maps specs to approved service-owned query ids. A valid
spec does not imply a query is implemented; it only proves the request is
well-formed and policy-evaluable.
