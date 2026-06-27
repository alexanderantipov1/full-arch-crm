# Worker Report — ENG-431 (Block F: governance)

- **Task**: F — Governance: ADR + CLAUDE.md invariants + PHI boundary reaffirmation
- **Linear**: ENG-431
- **Role / agent**: orchestrator+worker / claude-code (self-execute)
- **Branch**: eng-425-full-fidelity-ingestion-v1
- **Status**: COMPLETE — docs-only.

## What changed

- `docs/decisions/ADR-0005-full-fidelity-ingestion.md` — ADR (Accepted)
  recording the invariant, the grep-verifiable decision surface, consequences,
  and alternatives.
- `CLAUDE.md` — new hard architectural invariant #11 (full-fidelity ingestion;
  completeness at raw, curated domain mapping; points to ADR-0005 + doctrine).
- `packages/ingest/CLAUDE.md` — "Full-fidelity capture (ENG-425 / ADR-0005)"
  section: registry, SF dynamic projection (static = fallback only), REST no
  field filter, drift cron, backfill, and the PHI note (registry stores field
  names + types, never values).

## PHI boundary reaffirmation

Recorded in both the ADR and `packages/ingest/CLAUDE.md`: full fidelity includes
PHI at the raw layer under the existing access model
(`PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`); raw stays gated; the registry
never stores values, so PHI field names are metadata, not PHI.

## Verification

- Docs-only; no code/runtime change. ADR README keeps no numbered index, so no
  index edit needed.

## Do-not-merge conditions

- None specific to F. The mission bundle (A–F) wants cross-runtime review
  before integration per the mission contract.
