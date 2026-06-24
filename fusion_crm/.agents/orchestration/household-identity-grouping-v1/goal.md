# Goal — Household identity grouping, duplicate alerting & merge

**Epic:** ENG-552 · Project: Fusion CRM — Engineering · Team: Engineering
**Design:** `.agents/strategy/HOUSEHOLD_IDENTITY_GROUPING_DESIGN.md`

## Business goal
A phone/email is a shared household contact, not a unique identity key. Distinct
persons may share a phone/email; they are linked into a family/account block;
only genuine same-person duplicates get merged. Operators are always informed
when a contact is reused (nudge to capture distinct contacts), and have a merge
mechanism (our side now, provider-side later).

## Layers (Linear)
- **A — ENG-341** (foundation): phone/email non-unique. Drop the global
  `UNIQUE(kind,value)` for shared kinds; keep it for true 1:1 keys.
- **B — ENG-553**: household/family grouping over persons (anchor: CareStack
  `accountId` + shared-contact + fallback — confirm at design).
- **C — ENG-554**: marketing/outreach "one phone = one outreach target"
  projection over identity (never an identity merge).
- **D — ENG-555**: ALWAYS alert (Messenger) on shared-contact reuse, routed per
  location to the leads channel (reuse ENG-458/ENG-498).
- **E1 — ENG-556**: operator merge action (our side).
- **E2 — ENG-557**: push merges to CareStack/Salesforce (later phase).

## Sequencing
A → (B, D parallel) → E1 → C → E2.

## Constraints
Hard identity invariant (global person, identifier uniqueness, append-only
`merge_event`, DOB/SSN never logged). Propose-before-implement, real patient
data, migrations immutable. **No merge to main / no deploy without explicit
operator approval** (merge = unattended prod deploy + prod migration). Worktree-
isolated; keep the marketing projection (C) out of `identity`; provider write-
back (E2) gated hard.
