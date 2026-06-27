# Acceptance Criteria

## Mission Acceptance

The mission is accepted when:

- Linear parent issue ENG-286 and child issues ENG-287 through ENG-299 are
  linked under `Semantic Context And Analytics Foundation`.
- Mission runtime files record the Strategy Agent to Orchestrator `Handoff:`.
- Approved local tools can profile real local data without direct database
  access by agents.
- All outputs include data-class and masking posture.
- Row-level samples are capped, masked, and audit/logged.
- PHI and raw provider payload ordinary outputs are denied.
- Billing evidence is marked and bounded.
- Semantic mapping proposals and gap briefs can be generated without mutating
  catalog truth automatically.
- Local workbench docs/visibility exist if ENG-298 is executed.
- Verification covers positive and denial paths.
- Production review finds no architecture invariant violations.

## Issue Acceptance Map

- ENG-287 / DIA-01: Mission folder, runtime state, Linear sync, board, runlog,
  and handoff event exist.
- ENG-288 / DIA-02: Tool policy and allowlist are explicit and deny unsafe
  access.
- ENG-289 / DIA-03: Service-owned Data Intelligence contract exists.
- ENG-290 / DIA-04: Registry/dataset discovery tool is available.
- ENG-291 / DIA-05: Field profile tool enforces allowlists, caps, and denials.
- ENG-292 / DIA-06: Linkage/source coverage tool reports safe aggregate rates
  plus bounded masked examples.
- ENG-293 / DIA-07: Evidence coverage tool profiles consultation, treatment,
  payment, owner, location, campaign, and source evidence availability.
- ENG-294 / DIA-08: Bounded masked sample tool enforces caps and redaction.
- ENG-295 / DIA-09: Mapping proposal generator returns review-only proposals.
- ENG-296 / DIA-10: Gap brief writer creates stable non-sensitive briefs.
- ENG-297 / DIA-11: Success and denial calls are audit/logged.
- ENG-298 / DIA-12: Local workbench visibility is local/dev gated and has no
  MSW dependency for real backend-backed data.
- ENG-299 / DIA-13: Verification and production review are complete.
