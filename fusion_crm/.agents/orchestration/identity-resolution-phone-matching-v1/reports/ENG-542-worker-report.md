# ENG-542 — Same-phone surfacing + persist lead phone/email identifiers

**Worker:** claude-code · **Branch:** `eng-542-eng-542` (worktree-isolated) ·
**Parent epic:** ENG-541 · **Date:** 2026-06-20

> **DO NOT MERGE** without reading "Needs decision" below. The literal
> acceptance criterion (the duplicate person carrying a `person_identifier`
> row for the shared phone) is blocked by a hard architectural invariant and
> was intentionally **not** changed in this task. Merge to `main` =
> unattended prod deploy + prod migration.

---

## TL;DR

The user-visible GOAL is delivered and verified end-to-end against the live
DB: **Patrick Newton's card (`73e7523b…`) now surfaces the non-merged
duplicate (`464cc989…`) under "Same phone — not merged: ···7719"**, even
though the two records are not merged and the duplicate has zero identifier
rows.

This was achieved **without** altering the global `UNIQUE(kind, value)`
constraint on `identity.person_identifier` — surfacing is driven by the
verbatim `ingest.normalized_person_hint` value, mapped to the person via
`identity.source_link`. Persisting the shared phone as an actual identifier
row on the duplicate is **impossible** under the current invariant and is
flagged as the ENG-341 follow-up.

---

## Scope decision (why the "safe path")

The task is **Task class: normal**. Dropping the global `UNIQUE(kind, value)`
constraint is a shared-schema/migration change = **contract_change** per the
workflow tripwires (`PARALLEL_WORK_POLICY.md`) and alters a documented
`identity` invariant. The code already names this rework **ENG-341**
(`packages/identity/service.py:67`, `packages/ingest/repository.py` household
docstring). A "normal" task may not silently absorb a contract_change to the
core identity model, especially one that changes `resolve_by_phone` /
`resolve_by_email` semantics used by agent tools, `/identity/resolve`,
`outreach`, and `actor`.

DB evidence the literal acceptance needs ENG-341 (verified on `:5434`,
container `fusion-crm-postgres-1`, db `fusion`):

- Patrick (`73e7523b…`) owns `phone +19167307719` and his email as identifiers.
- Duplicate (`464cc989…`) has **0** `person_identifier` rows; only Patrick
  holds that E.164 value (global unique → no second row possible).
- Of the **783** lead-persons with no identifier, **>99%** of their hint phone
  values (10,113 of 10,125) are **already owned by another person** → a bulk
  identifier backfill collides almost everywhere under the current constraint.

So the chosen scope: **surface the shared contact from hints (covers 100% of
cases), persist identifiers only where the value is free, and flag the
constraint rework as a decision for the operator.**

---

## Needs decision (operator) — ENG-341 constraint rework

To make a non-merged duplicate **carry** the shared phone/email as a real
`identity.person_identifier` row (and to make the 783-row backfill effective),
the global `UNIQUE(kind, value)` must be relaxed to per-person uniqueness
(e.g. `UNIQUE(tenant_id, person_id, kind, value)`), with `resolve_by_phone` /
`resolve_by_email` / `find_identifier` given deterministic multi-person
semantics. That is a **contract_change** with cross-runtime review and a new
Alembic migration. Recommended as a **separate ENG-341 task** (it likely has
its own owner in this parallel-dev epic; this worker did not touch the shared
identity schema to avoid a migration-head race). I tried to raise this via
`AskUserQuestion` twice; the prompt did not return an answer in this worker
context, so I proceeded with the safe, in-scope path and flagged it here.

After ENG-341 lands, this task's already-shipped
`IngestService.backfill_lead_person_identifiers` + `IdentityService.
attach_identifier` become fully effective with **no further change** (they are
collision-aware today and simply stop hitting `collision`).

---

## What was implemented (in scope, reversible, no schema change)

### 1. Shared-phone surfacing regardless of merge status (DO #2 — the GOAL)
- **`packages/ingest/repository.py` → `person_household_members_by_hint`**
  (new, read-only). Surfaces OTHER persons sharing a normalised phone/email
  via `ingest.normalized_person_hint`, mapped to a person through
  `identity.source_link`. Self-values and sibling search both read the union
  of `person_identifier` + hints, so it is symmetric (A-shows-B iff B-shows-A)
  and catches the lead-only case where the shared phone was never persisted as
  an identifier. Tenant-scoped; masks values (`···7719`).
- **`packages/ingest/service.py` → `person_household_members`** now unions
  three resolvers: CareStack-payload, `person_identifier`, and the new hint
  resolver (precedence CareStack > identifier > hint, first-write-wins).

### 2. Card label (DO #2)
- **`apps/web/app/(staff)/persons/[uid]/page.tsx`** — household rows now read
  **"Same phone — not merged: ···7719"** (`sharedContactLabel()` helper;
  `phone` / `email` / `both`). Makes explicit that these are separate person
  records sharing a contact, never an identity merge.

### 3. Persist phone/email on lead-person create/upsert (DO #1)
- **`IdentityService.attach_identifier`** (new) — collision-safe, idempotent
  primitive: `added` / `exists` / `collision` / `invalid`. Mirrors the
  `create_person` ENG-340 guard (a value owned by another person is skipped,
  not an exception). The existing Tier-2 / fallback create paths already
  persist non-colliding values; this primitive is the reusable, tested unit.

### 4. Backfill (DO #3)
- **`IngestService.backfill_lead_person_identifiers`** (new) — reads lead-person
  hint phone/email and attaches via `attach_identifier`; idempotent +
  collision-safe; writes an append-only `identity.identifier.backfill` audit
  row per genuinely-added identifier; `dry_run` predicts work without writing.
- **`packages/ingest/repository.py` → `lead_person_identifier_hints`** (new,
  read-only) — candidate source from hints via `source_link`.
- **`apps/worker/jobs/backfill_lead_identifiers.py`** (new arq job) +
  registered in `apps/worker/main.py` `WorkerSettings.functions`
  (on-demand only, NO cron). CLI: `python -m
  apps.worker.jobs.backfill_lead_identifiers [--dry-run] [--limit N]
  [--tenant-id UUID]`.
- **`packages/audit/CLAUDE.md`** — taxonomy row for
  `identity.identifier.backfill`.
- Live `--dry-run` (read-only, no writes): **4,834** lead-persons, **8,624**
  candidate values for the doctor's tenant. (Most will report `collision`
  until ENG-341; the card surfaces them via hints regardless.)

---

## Acceptance check

| Criterion | Status |
|---|---|
| New lead-person carries phone/email identifiers | **Partial** — yes for FREE values (existing create paths + new primitive); shared/colliding values blocked by `UNIQUE(kind,value)` → ENG-341 |
| Card `73e7523b…` shows duplicate `464cc989…` under same-phone | **PASS** — verified end-to-end against live DB (`···7719`, "not merged"); needs no identifier backfill (hint-driven) |
| identity + ingest tests green | **PASS** for this change's tests (see below) |

Live end-to-end proof (read-only against `:5434`):
`IngestService.person_household_members(tenant, 73e7523b…)` →
`[(464cc989…, 'phone', '···7719')]`.

---

## Changed files

```
packages/identity/service.py          + attach_identifier (collision-safe primitive)
packages/ingest/repository.py         + person_household_members_by_hint, lead_person_identifier_hints
packages/ingest/service.py            + hint resolver in union, backfill_lead_person_identifiers; audit/Principal imports
apps/worker/jobs/backfill_lead_identifiers.py   NEW arq job (on-demand)
apps/worker/main.py                   register backfill_lead_identifiers
apps/web/app/(staff)/persons/[uid]/page.tsx     "Same <via> — not merged" label
packages/audit/CLAUDE.md              taxonomy: identity.identifier.backfill
tests/identity/test_service.py        + attach_identifier tests (4)
tests/ingest/test_person_household_repository_sql.py   + by_hint + union tests (7)
tests/ingest/test_backfill_lead_identifiers.py  NEW (3)
apps/web/tests/unit/PersonCardIdentity.test.tsx update label assertions (3)
```

No model/migration/`.env`/shipped-revision changes.

## Tests run

- `pytest tests/ingest/test_person_household_repository_sql.py
  tests/ingest/test_backfill_lead_identifiers.py
  tests/identity/test_service.py` → **53 passed**.
- `mypy` on all changed source files → **clean** (0 errors).
- Web: `vitest run tests/unit/PersonCardIdentity.test.tsx` → **16 passed**;
  `tsc --noEmit` → **0 errors**.
- Live read-only verification scripts (household resolver + backfill dry-run).

## Verification (/verify gate)

| Step | Result |
|---|---|
| `make lint` (ruff) | **PASS** |
| `mypy .` | **FAIL — pre-existing only.** 62 errors in 31 files, **none in files I touched** (down from 69; I fixed my 7). All in untouched test/infra files. |
| `make test` (full) | **Not run against the live shared DB.** Integration tests do DDL/seed against `DATABASE_URL=fusion` (the live data this mission inspects). Ran affected mock/unit suites instead — all green. Only non-DB failure in affected dirs is the **pre-existing** appointment-status-mapping bug (`tests/ingest/test_carestack_appointment_service.py`, unrelated to ENG-542; noted in session context #S5317). DB-integration suites need an ephemeral test DB (CI provides it). |
| `cd packages/db && alembic check` | **PASS** — "No new upgrade operations detected" (no schema drift; no migration added). |

## Risks

- **Resolver fan-out cost:** `person_household_members_by_hint` adds 4 indexed
  SELECTs per person-card load. Hints have indexes on
  `(tenant_id, phone_normalized)` / `(tenant_id, email_normalized)`; source_link
  join uses `ix_source_link_source`. Low risk; bounded by the person's value
  set. No N+1.
- **Hint table size:** `normalized_person_hint` is ~927k rows. Queries are
  equality-on-normalised-value + indexed; spot-checked fast on live data.
- **Backfill under current constraint** mostly reports `collision` (expected);
  it persists only free values. Not a correctness risk — surfacing covers the
  rest. Becomes fully effective post-ENG-341.

## Do-not-merge conditions

1. **Operator must decide ENG-341** (relax `UNIQUE(kind,value)`) before the
   literal "duplicate carries a phone identifier row" acceptance can be met.
   This PR deliberately does not change that invariant.
2. Merge to `main` triggers an **unattended prod deploy**; operator-only.
3. `make test` / `mypy .` red lines are **pre-existing**; confirm the CI gate's
   baseline before treating them as regressions (this change adds 0 new mypy
   errors and 0 new test failures).
