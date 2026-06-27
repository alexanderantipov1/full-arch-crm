# Contract — carestack-event-location-backfill-v1

- Migration backfills `interaction.event.payload.location_id` for CareStack
  billing/treatment events that lack it, resolved from the linked raw_event's
  CS locationId via tenant.location mapping. Same-tenant only.
- No schema/model change; no API change. Dashboard location filters start
  returning correct non-zero values automatically once events carry location_id.
