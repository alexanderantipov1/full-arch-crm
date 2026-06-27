# DSO Analytics API

Public REST endpoints for DSO partner BI tool integration. All endpoints return JSON and are designed to be consumed by tools like Tableau, Power BI, Metabase, or custom dashboards.

## Authentication

Every request **must** include an `X-Tenant-ID` header identifying the DSO tenant.

```
X-Tenant-ID: <your-tenant-uuid>
```

Missing or empty `X-Tenant-ID` returns:
```json
{ "error": "Missing or empty X-Tenant-ID header", "code": "MISSING_TENANT_ID" }
```

## Caching

All endpoints set `Cache-Control: max-age=300` (5 minutes). BI tools that respect HTTP caching will avoid hammering the server on dashboard refresh.

## HIPAA Audit

Every analytics query is logged to the HIPAA audit trail (`server/audit/logs/`) with:
- `action: "QUERY"`
- `resource: "analytics"`
- `resourceId`: the endpoint name (e.g. `"kpi"`, `"revenue/locations"`)

No PHI values are surfaced — only aggregate counts, rates, and sums.

## Error Shape

All errors return a consistent JSON body:
```json
{
  "error": "Human-readable message",
  "code": "MACHINE_READABLE_CODE"
}
```

---

## Endpoints

### `GET /api/analytics/kpi`

Full KPI snapshot for the tenant — the main dashboard feed.

**Headers:** `X-Tenant-ID: <tenantId>`

**Example request:**
```bash
curl -s \
  -H "X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  https://your-crm-host/api/analytics/kpi
```

**Example response:**
```json
{
  "tenantId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "asOf": "2025-06-27T20:00:00.000Z",
  "totalActivePatients": 148,
  "implantsMTD": 23,
  "revenueMTD": 182500,
  "avgCaseValue": 7935,
  "collectionRate": 91.2,
  "caseAcceptanceRate": 74.5,
  "chairUtilization": 83.0,
  "locations": [
    {
      "locationId": "loc-north",
      "locationName": "Location loc-nort",
      "revenueMTD": 98000,
      "revenueYTD": 612000,
      "revenueLastMonth": 87000,
      "growthPct": 12.6,
      "implantCount": 14,
      "avgCaseValue": 7000
    }
  ],
  "funnel": [
    { "stage": "Lead / Inquiry", "count": 312, "conversionPct": 100 },
    { "stage": "Consultation Scheduled", "count": 248, "conversionPct": 79.5 },
    { "stage": "Consultation Completed", "count": 201, "conversionPct": 81.0 },
    { "stage": "Treatment In Progress", "count": 148, "conversionPct": 73.6 },
    { "stage": "Treatment Complete", "count": 89, "conversionPct": 60.1 }
  ]
}
```

---

### `GET /api/analytics/revenue/locations`

Revenue breakdown by DSO location. Supports optional date range filtering.

**Headers:** `X-Tenant-ID: <tenantId>`

**Query parameters:**

| Parameter   | Type   | Required | Description                              |
|-------------|--------|----------|------------------------------------------|
| `startDate` | string | No       | ISO date string (e.g. `2025-01-01`)      |
| `endDate`   | string | No       | ISO date string (e.g. `2025-06-30`)      |

**Example request:**
```bash
curl -s \
  -H "X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  "https://your-crm-host/api/analytics/revenue/locations?startDate=2025-01-01&endDate=2025-06-30"
```

**Example response:**
```json
[
  {
    "locationId": "loc-north",
    "locationName": "Location loc-nort",
    "revenueMTD": 98000,
    "revenueYTD": 612000,
    "revenueLastMonth": 87000,
    "growthPct": 12.6,
    "implantCount": 14,
    "avgCaseValue": 7000
  },
  {
    "locationId": "loc-south",
    "locationName": "Location loc-sout",
    "revenueMTD": 84500,
    "revenueYTD": 524000,
    "revenueLastMonth": 79000,
    "growthPct": 6.9,
    "implantCount": 9,
    "avgCaseValue": 9389
  }
]
```

---

### `GET /api/analytics/funnel`

Patient conversion funnel across all pipeline stages. Each stage shows the count of patients at that stage and the conversion percentage from the prior stage.

**Headers:** `X-Tenant-ID: <tenantId>`

**Example request:**
```bash
curl -s \
  -H "X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  https://your-crm-host/api/analytics/funnel
```

**Example response:**
```json
[
  { "stage": "Lead / Inquiry",            "count": 312, "conversionPct": 100.0 },
  { "stage": "Consultation Scheduled",    "count": 248, "conversionPct": 79.5 },
  { "stage": "Consultation Completed",    "count": 201, "conversionPct": 81.0 },
  { "stage": "Treatment In Progress",     "count": 148, "conversionPct": 73.6 },
  { "stage": "Treatment Complete",        "count":  89, "conversionPct": 60.1 }
]
```

> `conversionPct` is the percentage of the *prior* stage's patients who advanced to this stage. The first stage is always 100%.

---

### `GET /api/analytics/implants/trends`

Monthly implant case volume and associated revenue. Ideal for trend charts and investor reporting.

**Headers:** `X-Tenant-ID: <tenantId>`

**Query parameters:**

| Parameter | Type    | Required | Default | Description                          |
|-----------|---------|----------|---------|--------------------------------------|
| `months`  | integer | No       | `12`    | Trailing months to return (1–60)     |

**Example request:**
```bash
curl -s \
  -H "X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  "https://your-crm-host/api/analytics/implants/trends?months=6"
```

**Example response:**
```json
[
  { "month": "2025-01", "count": 18, "revenue": 126000 },
  { "month": "2025-02", "count": 21, "revenue": 147000 },
  { "month": "2025-03", "count": 25, "revenue": 175000 },
  { "month": "2025-04", "count": 19, "revenue": 133000 },
  { "month": "2025-05", "count": 22, "revenue": 154000 },
  { "month": "2025-06", "count": 23, "revenue": 161000 }
]
```

> Revenue is derived from paid insurance claims linked to implant appointments. When claims are not yet posted, a $3,500 per-case estimate is used.

---

### `GET /api/analytics/acceptance/coordinator`

Case acceptance rates and average time-to-accept per treatment coordinator. Useful for performance dashboards and coaching.

**Headers:** `X-Tenant-ID: <tenantId>`

**Example request:**
```bash
curl -s \
  -H "X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  https://your-crm-host/api/analytics/acceptance/coordinator
```

**Example response:**
```json
[
  { "coordinatorId": "coord-001", "acceptanceRate": 82.3, "avgDaysToAccept": 1.8 },
  { "coordinatorId": "coord-002", "acceptanceRate": 75.0, "avgDaysToAccept": 3.2 },
  { "coordinatorId": "coord-003", "acceptanceRate": 68.4, "avgDaysToAccept": 4.7 }
]
```

> Results are sorted descending by `acceptanceRate`. `avgDaysToAccept` is the calendar-day average from treatment plan creation to patient acceptance.

---

## Response codes

| Code | Meaning                                                     |
|------|-------------------------------------------------------------|
| 200  | Success                                                     |
| 400  | Bad request — missing `X-Tenant-ID` or invalid query param  |
| 500  | Internal error — check server logs                          |

## Integration notes

- **Tenant isolation**: All queries are strictly scoped to the provided tenant. Cross-tenant data is never mixed.
- **Rate limiting**: Subject to the global `generalApiLimiter` — avoid sub-second polling.
- **Date formats**: All dates in responses are ISO 8601 UTC strings. Months in trend data use `YYYY-MM` format.
- **Revenue units**: All monetary values are in USD cents × 1 (i.e. whole dollars). `revenueMTD: 98000` means $98,000.
