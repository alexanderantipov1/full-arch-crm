# Contract

## Architecture Constraints

- Root invariants apply: no DB access from agents; routes/jobs call services;
  services own logic; repositories stay data-only.
- Raw provider payloads stay in `ingest.raw_event`.
- Ordinary timeline and agent-facing outputs expose source references and safe
  summaries only.
- `ops` stays marketing/operations-safe.
- Clinical notes, treatment details, insurance details, and raw
  patient-linked ledger payloads do not enter `ops`.
- `PhiService` remains the only path for PHI domain writes/reads.
- `interaction.event` remains append-only.
- Re-pulls must be idempotent or no-op unless a watched provider field
  changed.
- No deployment, env var, secret, Cloud Run, OAuth URL, or GitHub Actions
  deploy changes are in scope for this mission.

## Open Human Decisions

1. Timeline route name: `GET /persons/{uid}/operational-timeline` versus
   extending `GET /persons/{uid}/timeline`.
2. Whether call URLs are shown to authorized builders in the first UI workbench,
   or stored only as source references until the PHI-capable call analysis lane
   is approved.
3. Whether Salesforce Task action-oriented rows create `ops.followup_task`
   immediately, or first land as review-only events.
4. Whether event taxonomy uses snake_case values or adopts a dotted external API
   vocabulary while DB literals remain snake_case.

