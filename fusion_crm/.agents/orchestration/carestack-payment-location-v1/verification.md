# Verification — ENG-267

```bash
make lint
mypy .
make test
cd packages/db && alembic check   # no drift — payload-based, no migration
```

Focused checks:
- Location resolved at emit: a payment row with a mapped `locationId` stores the
  correct tenant.location UUID in payload; an unmapped/missing `locationId`
  omits `location_id` and still captures + emits the event.
- Aggregate filter: events with `location_id == X` are counted/summed when the
  aggregate is called with location X; events for other locations and events
  without a location are excluded from a location-filtered call; an unfiltered
  call still counts everything.
- Dashboard: changing the `location` query param changes Collected / Presented /
  Completed / Payments. Outstanding / AR-risk stay constant (tenant-wide).
- No PHI: payload/summary carry only amount, type, location_id — no patient
  identifiers or clinical data.
