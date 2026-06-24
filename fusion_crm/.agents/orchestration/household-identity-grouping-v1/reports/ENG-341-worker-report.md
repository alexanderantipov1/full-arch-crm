# ENG-341 — Worker Report

- **Task:** ENG-341 (Layer A of epic ENG-552) — phone/email non-unique (drop
  global UNIQUE for shared kinds). Class: **contract_change**.
- **Branch:** `eng-341-eng-341`
- **Worktree:** `…/household-identity-grouping-v1/worktrees/ENG-341`
- **Status:** ✅ Implemented + verified. **Draft PR only — DO NOT MERGE / DO NOT
  DEPLOY.** Awaiting Codex cross-runtime review + operator approval.
- **Proposal (written first, per contract_change gate):**
  `.agents/orchestration/household-identity-grouping-v1/reports/ENG-341-proposal.md`

## What changed

A phone/email is now a **shared household contact** — multiple distinct persons
may hold the same value. True 1:1 keys stay globally unique.

### Changed files
| File | Change |
|---|---|
| `packages/identity/models.py` | `PersonIdentifier`: removed blanket `UniqueConstraint("kind","value", uq_person_identifier_kind_value)`. Added (a) `UniqueConstraint("person_id","kind","value", uq_person_identifier_person_kind_value)` — per-person idempotency, all kinds; (b) partial unique `Index("uq_person_identifier_unique_kind_value","kind","value", unique=True, postgresql_where="kind NOT IN ('phone','email')")` — global 1:1 for non-shared kinds. Kept `ix_person_identifier_value`. Updated docstrings. |
| `packages/db/alembic/versions/20260621_1700_e9a1c7b4d2f3_eng341_person_identifier_shared_contacts.py` | **NEW** migration, `down_revision=5c46df9990df`. `upgrade()` runs a loud PRE-CHECK (counts only, no PHI/values) for (i) duplicate `(kind,value)` among unique kinds and (ii) duplicate `(person_id,kind,value)`, raising `RuntimeError` before any DDL. Then drops the old constraint and creates the two new guards. `downgrade()` recreates the old constraint with a documented irreversible-in-practice caveat. Pre-check exposed as `precheck_for_shared_contact_guards(conn)` for testing. |
| `packages/identity/service.py` | `_SHARED_CONTACT_KINDS` kept + repurposed (drives kind-aware attach; comment now points at the ENG-341 resolution). `create_person`: shared values are ATTACHED even if owned by another person (skip removed); dedupes identical `(kind,value)` within one payload. `attach_identifier`: shared kind + other owner ⇒ `"added"`; unique kind + other owner ⇒ `"collision"`; same person ⇒ `"exists"`; invalid phone/email ⇒ `"invalid"`. Docstring rewritten. Log key renamed `shared_contact_skipped` → `unique_identifier_collision`. |
| `packages/identity/repository.py` | `find_identifier` now `ORDER BY created_at, id` so for shared kinds (multiple holders) it deterministically returns the **earliest** holder instead of an arbitrary row. Docstring documents the multi-row behavior and points multi-holder enumeration at `list_candidate_persons_by_identifiers`. |
| `tests/identity/test_models.py` | Asserts old constraint gone; new per-person constraint + partial unique index (with its WHERE) present; value lookup index retained. |
| `tests/identity/test_service.py` | Replaced ENG-340 skip tests with ENG-341 behavior: `create_person` attaches a shared value owned elsewhere; payload-dedup test; `attach_identifier` shared⇒added / unique⇒collision / self⇒exists. |
| `tests/integration/test_person_identifier_shared_contacts_sql.py` | **NEW** real-PostgreSQL test: two persons hold the same phone+email (both rows persist); unique kind rejects cross-person dup (`IntegrityError`); duplicate `(person,kind,value)` rejected; migration pre-check stays silent on clean/shared data and raises (counts only, no value) on seeded violating data. |

## Consumer audit (find_identifier may now return multiple rows)

| Consumer | Outcome |
|---|---|
| `resolve_by_phone` / `resolve_by_email` (service) | No code change beyond the deterministic `ORDER BY` in `find_identifier`. They return the **earliest** holder — stable. Best-effort point lookups (tools, outreach, API `/identity/resolve`); cross-provider matching does not use them. |
| `upsert_by_identifier` | Returns earliest existing holder for a shared kind, else creates. Never relied on global uniqueness. OK. |
| `list_candidate_persons_by_identifiers` (repository) | Already returns ALL matching persons — the correct multi-row path the hint resolver uses. Unchanged. |
| `resolve_or_create_from_hint` + ingest services (`sf_lead`, `sf_contact`, `carestack_patient`, `carestack_treatment_plan`) | All go through `resolve_or_create_from_hint` / `list_candidate_persons_by_identifiers`, never `find_identifier` directly. No change. (One comment-only `uq_person_identifier_kind_value` reference in `carestack_patient_service.py:244` left as-is — not editing ingest in this task.) |
| `actor` package `find_identifier` | Separate `actor.actor_identifier` table + its own constraint. Out of ENG-341 scope (identity domain only). No change. |

**No consumer relied on phone/email being globally unique for correctness.**
The only single-row hazard (non-determinism of which holder is returned) is
fixed by the deterministic ordering.

## Tests run + results (venv: `~/dev/Fusion_crm/.venv`)

| Check | Result |
|---|---|
| `ruff check` (identity + migration + new/changed tests) | ✅ All checks passed |
| `mypy packages/identity` + migration | ✅ no issues (6 files) |
| `pytest tests/identity` | ✅ 111 passed |
| `pytest tests/integration/test_person_identifier_shared_contacts_sql.py` | ✅ 1 passed (real PostgreSQL) |
| `alembic upgrade head → downgrade -1 → upgrade head` | ✅ clean (local test PostgreSQL, port 5434) |
| `alembic check` (drift) | ✅ "No new upgrade operations detected" |
| `alembic heads` | ✅ single head `e9a1c7b4d2f3` |
| Regression: `test_merge_phone_duplicate_persons_sql`, `test_merge_split_lead_persons` | ✅ pass individually (combined run trips the known per-process event-loop teardown artifact, not a code regression) |

**DB hygiene:** verification applied the migration to the shared dev DB, then
**downgraded it back to main's head `5c46df9990df`** (old constraint restored)
so parallel sessions are unaffected. The migration applies for real on merge.

## Risks

- **One-way constraint drop.** Once shared phone/email duplicates exist,
  `downgrade` cannot recreate the blanket unique constraint (it will fail on the
  shared rows). Documented in the migration; expected/irreversible-in-practice.
- **Prod data may violate the new guards** → the pre-check aborts the migration
  loudly with counts (no values). Dev DB was clean (0/0). Operator must dedup
  first (ENG-541 tooling) if it fires in prod.
- **`CREATE UNIQUE INDEX`** is non-concurrent (alembic transactional DDL) — a
  brief lock, fine at current `person_identifier` size; flagged for future scale.
- **Tenant-scoping unchanged.** The unique-kind guard stays global (same scope
  as the old constraint, minus shared kinds) to keep this a minimal reversible
  change. Tightening to tenant-scoped is a separate follow-up (single tenant
  today, so not observable).

## Do-not-merge conditions

1. **Codex cross-runtime review** of the contract_change is required before
   ready-for-integration.
2. **Operator merge approval** — merge to `main` auto-deploys prod + runs the
   prod migration unattended. The pre-check makes a violating prod abort safely,
   but operator must consciously approve the deploy this session.
3. CI must re-confirm single alembic head after any rebase (concurrent-head
   guard, ENG-545).

## Scope boundaries (NOT done here)

Household grouping entity (B), marketing projection (C), duplicate Messenger
alert (D), merge UI (E), tenant-scoping the unique guard, editing ingest/actor
code — all out of ENG-341.
