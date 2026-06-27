# Goal — Identity resolution: phone-strong matching & same-phone surfacing

**Epic:** ENG-541 · Project: Fusion CRM — Engineering · Team: Engineering

## Business goal
A shared phone number must always tie people's records together — both in the
matcher (so duplicates don't get created) and in the person card (so an operator
always sees another record with the same phone, even when records are not
merged). Salesforce leads with reversed/single-field names and no email must
stop spawning duplicate persons.

## Why now
Operator found a real case: person `73e7523b-…` (Patrick Newton, CareStack,
phone `+19167307719`) whose Salesforce Lead `00QVw00000bKFvGMAW` (same phone,
name reversed, no email) was invisible. The matcher created a duplicate person
`464cc989-…` and parked an open match_candidate. Scale: 6,287 open candidates;
656 lead-persons carry a phone in the hint that was never persisted as an
identifier (so the card's same-phone block is structurally blind to them).

## Expected outcome
1. Same-phone records always surfaced on the card (safety net), independent of
   merge — ENG-542.
2. Order-invariant name compatibility + phone-strong / empty-lead auto-accept in
   `resolve_or_create_from_hint` — ENG-543.
3. Backfill/replay that finds and dedup-merges existing cases (dry-run first) —
   ENG-544.

## Constraints
- Changes ENG-185 identity-resolution policy → **contract_change**:
  propose-before-implement + **Codex cross-runtime review** before integration.
- Hard invariants stand: phi separation, append-only audit, UUID PKs, services-
  only, full-fidelity raw capture.
- **No merge to `main` / no deploy without explicit operator approval**
  (merge to main = unattended prod deploy + prod migration).
- Worktree-isolated; never the canonical checkout.
