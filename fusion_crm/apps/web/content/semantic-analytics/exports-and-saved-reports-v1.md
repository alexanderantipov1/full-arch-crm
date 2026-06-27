# Exports And Saved Reports V1

ENG-281 V1 follows the approved recommendation:

- CSV exports only.
- Saved report definitions only.
- No XLSX.
- No scheduled reports.
- Aggregate results only.
- Allowed data classes: `ops`, `integration_metadata`, and billing aggregate.
- Denied data classes: PHI, clinical detail, and raw provider payloads.
- Row-level export disabled.
- Every export and saved definition is audited.

## Tool Surface

### `export_analytics_csv`

Exports one approved aggregate analytics query as CSV.

Input:

```json
{
  "query_id": "lead_conversion_funnel.v1",
  "params": {
    "created_from": "2026-05-01T00:00:00Z",
    "created_to": "2026-06-01T00:00:00Z"
  },
  "filename": "may-lead-conversion"
}
```

Output:

```json
{
  "export": {
    "format": "csv",
    "content_type": "text/csv",
    "filename": "may-lead-conversion.csv",
    "content": "section,key,label,count,metric,value\n...",
    "row_count": 6,
    "scheduled": false,
    "xlsx_available": false
  },
  "source": {
    "query_id": "lead_conversion_funnel.v1",
    "read_model_id": "lead_conversion",
    "data_classes": ["ops", "integration_metadata"],
    "definition_versions": {"lead_source": "v1"},
    "filters": {},
    "warnings": []
  }
}
```

### `save_analytics_report_definition`

Creates an audited portable saved-report definition artifact. V1 does not
persist a database row and does not schedule delivery.

Input:

```json
{
  "name": "Monthly paid leads",
  "query_id": "paid_leads_by_source.v1",
  "params": {
    "source_provider": "salesforce"
  }
}
```

Output includes:

- stable deterministic `definition.id`;
- report `name`;
- canonical `query_id`;
- `read_model_id`;
- structured `params`;
- `output_level = aggregate`;
- `format = csv`;
- allowed `data_classes`;
- `scheduled = false`;
- `xlsx_available = false`;
- `row_level = false`.

## CSV Shape

CSV columns:

```text
section,key,label,count,metric,value
```

Aggregate bucket fields are exported as:

- `section`: result section, such as `lead_status`;
- `key`: bucket key;
- `label`: human label;
- `count`: bucket count.

Scalar metrics are exported as:

- `section = metric`;
- `metric`: metric name;
- `value`: metric value.

## Audit

`export_analytics_csv` writes:

- principal and tenant through `AuditService`;
- `query_id`;
- `read_model_id`;
- `format = csv`;
- exported row count;
- data classes;
- billing inclusion flag;
- filename.

`save_analytics_report_definition` writes:

- principal and tenant through `AuditService`;
- saved definition id;
- `query_id`;
- `read_model_id`;
- `format = csv`;
- param keys only;
- data classes;
- billing inclusion flag.

## Denied In V1

- XLSX export.
- Scheduled reports.
- Email delivery.
- Row-level export.
- Raw SQL.
- Raw provider payloads.
- PHI or clinical detail.
- Clinical procedure text, tooth/surface data, notes, or patient identifiers.

## Future Decisions

Before adding V2 exports, decide:

- XLSX formatting and workbook schema;
- persisted saved report storage;
- scheduled report delivery mechanism;
- recipient allowlist;
- row-level field allowlist;
- row caps;
- retention policy;
- download URL expiration policy.
