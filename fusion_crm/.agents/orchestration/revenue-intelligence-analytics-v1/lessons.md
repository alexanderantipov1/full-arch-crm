# Lessons — revenue-intelligence-analytics-v1 (ENG-504)

- Multi-location data already exists (`tenant.location`,
  `ops.consultation.location_id`); analytics endpoints just lack the location
  filter — wiring task, not a data task.
- Person-anchored funnel dating (ENG-481) must be reused so the ~27k purchased
  CareStack base does not create a false cohort spike.
- Revenue uses the ENG-283 Net-Collected formula (exclude `payment_applied`).
- Treatment-accepted / surgery classification (ENG-511) is the riskiest gap —
  do not guess a CareStack mapping; flag `Needs decision:`.
