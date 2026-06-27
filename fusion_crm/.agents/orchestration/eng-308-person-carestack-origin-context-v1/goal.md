# Goal — ENG-308: surface true CareStack identity & origin context

Make the CareStack identity context on the person card **honest and
complete**: stop misrepresenting `source_link.first_seen_at` as "patient
since" (it's our ingest date, not CareStack's reality), surface multi-link
patients (one person → multiple CS patient_ids — the Torosyan-shape case is
common), expose the city/state hint already in the payload, and resolve the
`defaultProviderId` raw integer into a readable "Dr First Last" via a new
CareStack providers sync.

Frontend changes are the visible win; backend lands a new per-pid origin
aggregator + a providers ingest + a one-off backfill script.

Linear: ENG-308
URL: https://linear.app/fusion-dental-implants/issue/ENG-308/person-card-surface-true-carestack-identity-and-origin-context
Parent: ENG-250 — Related: ENG-306 (data + UI for financials, merged
50da948 / a44a5da / 0d44247).
