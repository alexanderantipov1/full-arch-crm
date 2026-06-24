# ENG-341 — Proposal: phone/email non-unique (drop global UNIQUE for shared kinds)

> **Layer A** of epic ENG-552 (Household identity grouping). Task class:
> **contract_change** (touches a hard identity invariant — identifier
> uniqueness). Propose-before-implement. Draft PR only; NO merge / NO deploy.

## 1. Goal

`phone` and `email` become **shared household contacts**: multiple distinct
persons may legitimately hold the same value (spouse, children share one phone).
True 1:1 keys (`carestack_patient_id`, `salesforce_contact_id`, and any future
`ssn` / CareStack `accountId` / portal kind held as a `person_identifier`) stay
**globally unique** at the DB level.

This removes the root cause of the ENG-340 workaround, which silently dropped a
second person's phone/email identifier row to avoid a `UniqueViolation`.

## 2. Current state (verified)

- `packages/identity/models.py:173` — blanket
  `UniqueConstraint("kind","value", name="uq_person_identifier_kind_value")`.
  Not even tenant-scoped: a value is unique across the whole table.
- `packages/identity/service.py:71` — `_SHARED_CONTACT_KINDS = {"phone","email"}`;
  `create_person` (≈777) and `attach_identifier` (≈804) **skip** a shared value
  already owned by another person (ENG-340). Cost: second person's contact is
  not persisted as an identifier row; ENG-542 surfaces household members via the
  hint resolver instead.
- `packages/identity/repository.py:337` — `find_identifier(kind,value)` returns
  **one** row (`.limit(1)`, no `ORDER BY`). With the old constraint there was at
  most one row, so the missing `ORDER BY` was harmless.
- Single alembic head: **`5c46df9990df`** (down_revision for the new migration).

## 3. Design decision — ACCEPTED (recommended design works)

Replace the one blanket constraint with **two guards**:

**(a) Per-person idempotency (all kinds)** — a `UniqueConstraint` on
`("person_id","kind","value")` named `uq_person_identifier_person_kind_value`.
Stops duplicate rows on ONE person; allows the same value across DIFFERENT
persons for every kind.

**(b) Global 1:1 for unique kinds only** — a PARTIAL unique `Index` on
`("kind","value")` named `uq_person_identifier_unique_kind_value`, with
`postgresql_where=text("kind NOT IN ('phone','email')")`. Keeps SSN / CareStack
patient id / Salesforce id / portal globally unique; exempts the two shared
kinds.

Keep the existing non-unique lookup `Index("ix_person_identifier_value","value")`.

### Why a denylist `kind NOT IN ('phone','email')` and not an allowlist

The shared set is small and closed (`phone`, `email`); the unique set is
open-ended (every other / future kind should default to unique 1:1). A denylist
makes "new kind ⇒ unique by default" the safe default and matches the model
docstring convention ("adding a new identifier kind: just use a new `kind`
string — no DDL needed"). The shared denylist is the single source of truth
mirrored in service code as `_SHARED_CONTACT_KINDS`.

### Tenant-scoping note (intentional carry-over)

The old constraint was global (not tenant-scoped). To keep this migration a
**minimal, reversible** contract change, guard (b) stays **global** too (same
scope as before, minus the two shared kinds). Tightening unique kinds to
tenant-scoped is a behavior change out of scope for ENG-341; flagged as a
follow-up, not done here. Today there is a single tenant, so global vs
tenant-scoped is not observable in prod.

## 4. Migration plan

New file only: `packages/db/alembic/versions/<ts>_<rev>_eng341_person_identifier_shared_contacts.py`,
`down_revision = "5c46df9990df"`.

### upgrade()
1. **PRE-CHECK, fail loudly** (so a prod run aborts safely instead of a silent
   `CREATE UNIQUE INDEX` failure mid-deploy):
   - (i) duplicate `(kind,value)` among **unique** kinds
     (`kind NOT IN ('phone','email')`) with `COUNT(*) > 1`;
   - (ii) duplicate `(person_id,kind,value)` with `COUNT(*) > 1`.
   Emit **counts only** (no `kind`, no `value`, no `person_id` — values can be
   PHI/PII) and `raise RuntimeError` if either is > 0. Message points at the
   dedup remediation (ENG-541 / `merge_phone_duplicate_persons.py`).
2. `op.drop_constraint("uq_person_identifier_kind_value", "person_identifier",
   schema="identity", type_="unique")`.
3. `op.create_unique_constraint("uq_person_identifier_person_kind_value", ...,
   ["person_id","kind","value"], schema="identity")`.
4. `op.create_index("uq_person_identifier_unique_kind_value", ..., ["kind","value"],
   unique=True, schema="identity",
   postgresql_where=sa.text("kind NOT IN ('phone','email')"))`.

### downgrade()
- Drop the two new guards; recreate `uq_person_identifier_kind_value`.
- **Documented caveat (irreversible-in-practice):** if shared phone/email
  duplicates were created while the new schema was live, recreating the blanket
  unique constraint will FAIL. This is expected — the downgrade is best-effort
  and a real rollback after shared data exists requires manual dedup first. A
  comment in the migration states this.

### Migration safety
- `CREATE UNIQUE INDEX` is **not** `CONCURRENTLY` (alembic runs in a
  transaction); on the current small `person_identifier` table this is a brief
  lock, acceptable. Noted as a risk for future scale, not changed here.
- Pre-check runs **before** any DDL, so a violating prod DB aborts with a clear
  count and no partial change.

## 5. Service changes (`packages/identity/service.py`)

- `_SHARED_CONTACT_KINDS` (≈71): **kept** — now it is the canonical shared-kind
  set used to drive kind-aware attach logic (no longer "skip" semantics).
  Comment updated: ENG-340 skip → ENG-341 resolution. Mirrors the migration's
  `('phone','email')` denylist (the one place to change if the set grows).
- `create_person` (≈777): for shared kinds, **attach** even when another person
  owns the value (drop the skip). Still avoid a duplicate identical
  `(person,kind,value)` — but because identifiers are attached to a brand-new
  person here, a same-person duplicate can only arise from a repeated identifier
  in the same payload; dedupe the payload's identifiers per `(kind,value)`
  before insert.
- `attach_identifier` (≈804): kind-aware.
  - shared kind + value owned by ANOTHER person ⇒ **attach**, return `"added"`.
  - same person already holds value ⇒ return `"exists"` (idempotent).
  - UNIQUE kind + value owned by another person ⇒ keep `"collision"` (no attach,
    no raise).
  - phone/email failing normalisation ⇒ `"invalid"` (unchanged).
  - Docstring rewritten: the global UNIQUE no longer applies to phone/email;
    "collision" now means a true 1:1-kind conflict; cites ENG-341 as the
    resolution (not future work).

## 6. Consumer audit (single-row assumption)

`find_identifier(kind,value)` may now return MULTIPLE rows for a shared kind.
Audited every caller:

| Caller | Risk | Resolution |
|---|---|---|
| `IdentityService.resolve_by_phone` / `resolve_by_email` (service 514-520) | Returns "a" person for a shared phone/email; previously exactly one existed. Now non-deterministic which holder is returned. | Make `find_identifier` **deterministic** (add `ORDER BY created_at, id`) so it returns the **earliest** holder — stable, no behavior surprise. These are best-effort point lookups (tools, outreach recipient lookup, API `/identity/resolve`); cross-provider matching does NOT go through them. Documented that for shared kinds they return the earliest holder; household-aware lookup is the hint resolver / ENG-542 path. |
| `attach_identifier` (service 845) | Needs to know if THIS person already holds the value vs another. `.limit(1)` earliest-owner is sufficient for the "exists vs added vs collision" decision: we check `existing.person_id == person.id` first; if a different person owns it and kind is shared we attach regardless. | Logic reworked to be kind-aware; one representative row is enough. |
| `upsert_by_identifier` (service 883) | For a shared kind, returns the earliest holder if any identifier exists, else creates. | Acceptable: find-or-create by contact returns the earliest existing holder (deterministic after the ORDER BY). No correctness break — it never relied on global uniqueness, only on "is there at least one". |
| `create_person` shared-kind branch (service 782) | Was used to SKIP. | Removed (now attaches). |
| `list_candidate_persons_by_identifiers` (repository 289) | Already returns **ALL** matching persons (distinct), the correct multi-row behavior for the hint resolver. | No change needed — it already treats phone/email as ambiguous multi-candidate hints. This is the canonical cross-provider matching path; it is unaffected and already correct. |
| `resolve_or_create_from_hint` (service 1223) | Uses `list_candidate_persons_by_identifiers`, not `find_identifier`. Already tiered/ambiguous on phone/email. | No change. |
| `actor` package `find_identifier` (`packages/actor/*`) | Separate `actor.actor_identifier` table + its own constraint; out of ENG-341 scope (identity domain only). | No change. Noted for completeness. |
| ingest services (`sf_lead`, `sf_contact`, `carestack_patient`, `carestack_treatment_plan`) | All call `resolve_or_create_from_hint`, never `find_identifier` directly. One docstring in `carestack_patient_service.py:244` references `uq_person_identifier_kind_value` — comment-only, harmless; left as-is (not editing ingest in this task) unless it misleads. | No code change. |

**Conclusion:** the only single-row hazard is the non-determinism of which
holder `resolve_by_phone/email`/`upsert_by_identifier` return. Fixed by a
deterministic `ORDER BY created_at, id` in `find_identifier`. No consumer relied
on phone/email being globally unique for correctness; the cross-provider matcher
already enumerates all candidates.

## 7. Tests (`tests/identity/` + `tests/integration/`)

- **Model metadata** (`tests/identity/test_models.py`, unit): assert the blanket
  `uq_person_identifier_kind_value` is gone; assert the new
  `uq_person_identifier_person_kind_value` constraint and the partial
  `uq_person_identifier_unique_kind_value` index (with its `WHERE`) exist;
  `ix_person_identifier_value` still present.
- **Service** (`tests/identity/test_service.py`, mocked repo): `attach_identifier`
  shared kind + other owner ⇒ `"added"`; unique kind + other owner ⇒
  `"collision"`; same person ⇒ `"exists"`. `create_person` attaches a shared
  value already owned elsewhere (no skip).
- **Integration, real PostgreSQL** (new
  `tests/integration/test_person_identifier_shared_contacts_sql.py`, COMMIT +
  throwaway-tenant cleanup, mirrors
  `test_merge_phone_duplicate_persons_sql.py`):
  1. two persons CAN hold the same `phone` (and `email`) — both rows persist;
  2. a unique kind (`carestack_patient_id`) STILL rejects a cross-person
     duplicate (`IntegrityError`);
  3. same `(person,kind,value)` re-insert violates
     `uq_person_identifier_person_kind_value`;
  4. migration pre-check helper raises on seeded violating data (call the
     migration's pre-check function against a seeded duplicate of a unique kind
     and a seeded `(person,kind,value)` duplicate; assert `RuntimeError` with
     counts and no values).

## 8. Risks & do-not-merge conditions

- **One-way constraint drop.** Once shared phone/email duplicates exist,
  downgrade can't recreate the blanket unique constraint. Documented; expected.
- **Prod data may already violate** the new unique-kind or per-person guards →
  the pre-check aborts the migration loudly (by design). Operator must dedup
  first (ENG-541 tooling) if it fires.
- **Lock on `CREATE UNIQUE INDEX`** (non-concurrent) — fine at current scale;
  flagged for future.
- **Do not merge** until: ruff + mypy clean on `packages/identity` + the new
  migration; `tests/identity` green; integration test green on the real test DB;
  `alembic upgrade head → downgrade -1 → upgrade head` clean on local test
  PostgreSQL; `alembic check` (drift) clean; single alembic head preserved;
  Codex cross-runtime review + operator approval (contract_change).

## 9. Out of scope (explicitly NOT done here)

- Household/family grouping entity (Layer B), marketing projection (C),
  duplicate Messenger alert (D), merge UI (E) — separate epic children.
- Tenant-scoping the unique-kind guard (behavior change; follow-up).
- Editing ingest services or actor identifiers.
