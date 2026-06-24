# Contract — pm-payments-page-v1

- `GET /dashboard/pm/payments?from&to&location_id&source_provider&q&limit`
  -> { items: [{ person_uid, display_name, lead_status, consultation_status,
       amount, kind, transaction_type, occurred_at, location_id, location_name,
       source_external_id, raw_event_id }], total }. Safe fields only.
- `GET /ingest/dev/inspector/raw-events/{event_id}` -> single raw_event with
  verbatim payload (tenant-scoped). Used by the row drilldown.
- Frontend route `/project-manager/payments` + sidebar item under Leads.
- No schema change.
