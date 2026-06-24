# Goal — location-scope CareStack payment & treatment metrics (ENG-267)

Make the dashboard **Treatment & payments** track respect the **location** filter,
like leads/consultations already do. Attach location to each payment/treatment
`interaction.event` at emit time (CareStack rows carry `locationId`), then filter
the aggregate by location.

- No new schema: store resolved `location_id` (our tenant.location UUID) in the
  event payload (consistent with how `amount` is stored/queried).
- Resolver: `TenantService.find_by_carestack_id(tenant_id, carestack_location_id)`.
- In scope: Collected / Presented / Completed / Payments recalc by location.
- Out of scope: Outstanding / AR-risk (payment_summary has no location) — stay
  tenant-wide, label clearly.

Linear: ENG-267. Read-only CareStack, no PHI.
