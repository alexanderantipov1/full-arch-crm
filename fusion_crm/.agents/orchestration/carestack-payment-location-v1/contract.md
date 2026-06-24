# Contract — carestack-payment-location-v1

- Event payload gains `location_id` (string UUID of tenant.location) on CareStack
  payment + treatment events. Optional — omitted when CS location is unmapped.
- `get_treatment_payment_aggregate(..., location_id: UUID | None = None)` filters
  by `Event.payload["location_id"].astext` when set.
- Dashboard `DashboardTreatmentPaymentsOut` numbers (collected_total,
  treatment_presented_count, treatment_completed_count, invoice_count,
  payment_total_amount, payment_event_count) become location-scoped.
  outstanding_total / outstanding_patient_count / ar_risk_count remain tenant-wide.
