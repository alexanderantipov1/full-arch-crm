# ENG-551-A — Worker Report

**Task:** Resolve Operation + Doctor via `treatment_procedure` (backend-only fix).
**Linear:** ENG-551 — follows ENG-547 (PR #202, merged).
**Branch:** `eng-551-eng-551-a` · isolated worktree off `main`.
**Status:** ✅ Implemented, verified, draft PR opened. **Do NOT merge** (conditions below).

---

## The bug (one line)
`accounting_transaction.procedureCodeId` is **not** a CDT catalog id — its value
is a `treatment_procedure.id` (instance id). The shipped ENG-547 code joined it
straight to `catalog.procedure_code` → 0 matches → Operation always "—".

## What changed (backend only — DTO/Zod/frontend UNCHANGED)
`IngestService.get_payment_procedure_doctor_refs` keeps its exact signature and
4-field return shape (`operation_code` / `operation_description` / `doctor_name`
/ `doctor_provider_id`). Only the internal resolution changed to the real chain:

```
accounting.procedureCodeId (= treatment_procedure INSTANCE id)
  → treatment_procedure.upsert raw payload (by payload id)
  → its real CDT procedureCodeId → catalog.procedure_code (code + description)
  → its providerId               → carestack_provider display name
```

- **Doctor preference:** the treatment procedure's `providerId` (filled ~100%)
  wins whenever a procedure is linked; the accounting `providerId` (~77% filled)
  is the fallback **only** when no procedure is linked. `doctor_provider_id`
  echoes whichever id was used.
- **Operation:** comes ONLY from the tp→catalog chain; `None`/"—" when no linked
  procedure or the CDT id is not in the catalog.

### New repository read
`IngestRepository.get_treatment_procedure_refs(tenant_id, tp_ids) -> {tp_id: (cdt_code_id, provider_id)}`
- Reads `carestack.treatment_procedure.upsert` raw payloads keyed by
  `payload->>'id' IN (...)` — tenant-scoped, event_type-pinned, batched.
- `DISTINCT ON (payload->>'id') ORDER BY received_at DESC` → newest payload per
  procedure wins (a procedure is re-pulled on every lifecycle change).
- **Selects only `id`, `procedureCodeId`, `providerId`** — never tooth /
  surfaces / notes / statusId / dates. No clinical field leaves the raw layer.

## Touched files
| File | Change |
|------|--------|
| `packages/ingest/repository.py` | + `get_treatment_procedure_refs` (new batched read) |
| `packages/ingest/service.py` | Rewrote `get_payment_procedure_doctor_refs` internals + docstring to the two-hop chain; doctor preference/fallback |
| `tests/integration/test_payment_procedure_doctor_refs.py` | Rewrote fixture to the real two-hop shape; added cases for the new chain |

No DTO, schema, router, migration, or frontend change. Import matrix respected
(`ingest → catalog` is allowed; `interaction` untouched).

## Tests run + results
Project venv `/Users/eduardkarionov/dev/Fusion_crm/.venv`, DB = canonical
checkout Postgres on :5434 (`.env` copied into the worktree, gitignored, not
committed).

- `ruff check` on all touched files → **All checks passed!**
- `pytest tests/integration/test_payment_procedure_doctor_refs.py tests/api/test_dashboard_pm_payments.py -q`
  → **20 passed** (8 integration + 12 API).

Integration coverage (rewritten): full chain resolves code+doctor; tp missing →
"—" + doctor falls back to accounting provider; tp present but CDT not in catalog
→ code "—" yet provider resolves; doctor prefers tp provider over accounting;
newest tp payload wins; batched across many rows; clinical fields never surface;
non-accounting raw ignored; provider lookup tenant-scoped.

The API test (`test_dashboard_pm_payments.py`) mocks the service method directly
and asserts route plumbing only — the contract is unchanged (same method, same
4-field shape), so all 12 pass unmodified.

## Live-probe evidence (real prod-sync DB on :5434)
Found a real accounting raw whose `procedureCodeId` exists as a
`treatment_procedure.id`, then called the new service:

```
candidate raw_id=ceca7fef-5761-4ecf-94dd-ee4260b73d29 tp_instance_id=9932752 cdt_id=6109
service result: {'operation_code': 'D6056',
                 'operation_description': 'Prefabricated abutment - includes modification and placement',
                 'doctor_name': 'Kevin Clifford', 'doctor_provider_id': 26890}
PROBE PASSED: operation_code = D6056
```

This matches the issue's predicted real output (D6056 / D6058). The pre-fix
direct join returned `None` for the same row.

Coverage snapshot (local prod-sync, confirms Layer 2 is the limiter):
```
total accounting legs        119,817
legs with a procedureCodeId  112,796
legs with a LINKED tp present   9,894   (~8.8% of procedure-bearing legs)
```

## Risks
- **Coverage is ingest-gated, not code-gated.** The chain is correct; only legs
  whose `treatment_procedure` is already captured locally resolve. Local
  `treatment_procedure` is under-ingested (track B fixes this).
- Extra batched read per page (`get_treatment_procedure_refs`) — one query,
  `DISTINCT ON` over the tenant+event_type index; negligible.
- `treatment_procedure` payloads with multiple captures: newest wins by
  `received_at` then `id` — matches the existing `treatment_procedure_code_ids_by_patient`
  dedup convention.

## Do-not-merge conditions
1. **Codex cross-runtime review pending** (ENG-551 calls for it before merge).
2. **Operator approval pending** — merge to `main` auto-deploys prod.
3. **Track B (ops) not done:** `treatment_procedure` backfill on prod +
   scheduled-pull coverage verification still needed for full Operation
   coverage. Merging A alone fixes the resolution path but leaves ~80%+ of legs
   unresolved until B lands. Prod coverage to be confirmed separately (recon was
   on local prod-sync).
