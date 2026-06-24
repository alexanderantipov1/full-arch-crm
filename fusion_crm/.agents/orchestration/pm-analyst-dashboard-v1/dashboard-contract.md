# PM/Analyst Dashboard V1 Contract Draft

## Route Shape

Default to one staff dashboard route with PM/Analyst tabs:

- `GET /dashboard/pm`
- `GET /dashboard/analytics`
- `GET /dashboard/drilldown`

The backend may implement this as one service/read model with two response
profiles. Routes remain thin composers.

## Shared Filters

All dashboard reads should accept the same filter family:

| Parameter | Type | Notes |
|---|---|---|
| `from` | datetime/date | Inclusive lower bound. Default: start of last 30 days. |
| `to` | datetime/date | Exclusive upper bound. Default: now. |
| `business_unit` | string | Salesforce `Business_Unit__c` once enriched. |
| `location_id` | uuid | Tenant location id, usually CareStack-derived. |
| `center` | string | Transitional display filter until `location_id` is complete. |
| `lead_source` | string | Salesforce `LeadSource`. |
| `utm_source` | string | Salesforce UTM enrichment. |
| `utm_campaign` | string | Salesforce UTM enrichment. |
| `owner_id` | string | Salesforce Lead owner id once enriched. |
| `stage` | enum | Normalized stage; service-derived. |
| `consultation_status` | enum | `ops.consultation.status`. |
| `treatment_status` | enum | Requires CareStack treatment/payment classification. |
| `payment_status` | enum | Requires CareStack treatment/payment classification. |
| `source_provider` | enum | `salesforce`, `carestack`, or both. |
| `q` | string | Authenticated staff search over name, phone, email, SF id, CS patient id. |

## PM Response Profile

Primary job: daily manual operations.

Suggested top-level shape:

```json
{
  "filters": {},
  "kpis": [],
  "funnel": [],
  "breakdowns": [],
  "risk_rows": [],
  "sync_health": [],
  "recent_activity": [],
  "drilldown_links": []
}
```

Required KPI cards:

- active pipeline;
- consults scheduled;
- consults completed;
- no-show / cancelled / rescheduled;
- treatment accepted / pending where available;
- payment / AR risk where available;
- sync health.

Required risk rows:

- stale lead;
- no next action;
- no-show;
- cancelled consult;
- consult completed with no next step;
- AR-like risk once payment data lands.

## Analyst Response Profile

Primary job: attribution and reporting.

Required breakdowns:

- business unit;
- center/location;
- lead source;
- UTM source;
- UTM campaign;
- owner / TC owner when available;
- normalized stage;
- consult status;
- treatment/payment aggregates where available.

## Drilldown Contract

`GET /dashboard/drilldown?metric=<metric>&...filters`

Returns the rows behind a count or aggregate:

```json
{
  "metric": "no_show",
  "items": [
    {
      "person_uid": "...",
      "display_name": "...",
      "source_providers": ["salesforce", "carestack"],
      "stage": "consult_completed",
      "lead_status": "qualified",
      "consultation_status": "no_show",
      "treatment_summary": null,
      "payment_summary": null,
      "last_activity_at": "..."
    }
  ],
  "total": 1
}
```

`display_name`, phone, and email are allowed only because this is an
authenticated staff surface. Raw provider payloads remain excluded.

## Normalized Stage V1

Initial stage derivation can ship before treatment/payment:

1. `consult_completed` if any completed `ops.consultation`.
2. `consult_scheduled` if any scheduled/rescheduled `ops.consultation`.
3. `closed_lost` if lead status maps to lost.
4. `qualified` if lead status maps to qualified/contacted.
5. `new` if lead exists.
6. `unknown`.

Treatment/payment stages can be added after CareStack classification:

- `treatment_presented`;
- `treatment_accepted`;
- `payment_started`;
- `ar_risk`.

## Implementation Notes

- Build on current canonical tables first.
- Keep dashboard metrics server-side.
- Keep browser filters as UI state only.
- Do not add provider-shaped dashboard tables.
- Add Salesforce enrichment only where reporting needs stable dimensions.
- Add CareStack treatment/payment aggregates only after classification.
