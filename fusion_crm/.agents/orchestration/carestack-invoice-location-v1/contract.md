# Contract — carestack-invoice-location-v1

- `invoice_created` event payload gains `location_id` (str UUID of tenant.location),
  resolved from the invoice row's `locationId`. Optional — omitted when unmapped.
- No API/aggregate signature change: `get_treatment_payment_aggregate` already
  filters `invoice_created` by `payload["location_id"]` (ENG-267). This makes
  `invoice_count` and `payment_total_amount` location-scoped once events carry it.
