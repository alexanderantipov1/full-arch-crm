# Decision log — household-identity-grouping-v1

## 2026-06-21 — Mission created from operator vision (epic ENG-552)
Handoff: Strategy → Orchestrator. Source: operator vision after the ENG-541
dedup epic + ENG-550 prod live pass (178 merges; 1,144 ambiguous candidates
left open). Strategy doc: `.agents/strategy/HOUSEHOLD_IDENTITY_GROUPING_DESIGN.md`.

Linear: epic ENG-552 + A=ENG-341 / B=ENG-553 / C=ENG-554 / D=ENG-555 /
E1=ENG-556 / E2=ENG-557.

Operator decisions (2026-06-21): (2) marketing = separate projection YES;
(3) alert routed per location → leads channel, tag "lead", reuse ENG-458;
(4) provider push later YES; (5) ALWAYS alert on shared-contact reuse (not only
suspicious) to nudge distinct-contact capture; (1) household anchor assumed
CareStack accountId + fallback — confirm at B design.

Operator: "делай всё по порядку." → start Layer A (ENG-341).

## 2026-06-21 — Layer A (ENG-341) launched — proposal-first
Recommended design (baked into worker prompt, worker writes proposal first):
- Replace blanket `UniqueConstraint("kind","value")` on
  `identity.person_identifier` with a **partial unique index** that EXCLUDES
  shared kinds: `unique (kind, value) WHERE kind NOT IN ('phone','email')`.
  Keeps 1:1 enforcement for ssn / carestack_patient_id / carestack accountId /
  salesforce ids / portal; lets phone/email repeat across persons.
- Migration with a **pre-check**: fail loudly if any duplicate (kind,value)
  already exists among the unique kinds before creating the partial index.
- Make the identifier-attach paths kind-aware:
  `create_person` / `attach_identifier` must now PERSIST a shared phone/email on
  a 2nd person (drop the ENG-340 skip for shared kinds; keep same-person
  idempotency). Unique kinds keep the collision guard.
- Tests: shared phone persists on 2nd person; unique-kind collision still
  blocked; migration pre-check.

Task class **contract_change** (identity invariant + prod migration). Draft-PR
only; STOP for Codex cross-review; **no merge/deploy without operator approval**
(merge = prod migration). D (ENG-555) starts after A is in prod.
