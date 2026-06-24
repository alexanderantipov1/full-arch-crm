# ENG-539 (B1.5) — Implant `case_type` dimension on `fact_patient_journey`

**Worker:** Claude (claude-code), session `edec39c9059b`
**Branch / worktree:** `eng-539-eng-539` (off `main`, contains ENG-511 + ENG-538)
**Status:** Implementation complete; **left UNCOMMITTED** per task. Static
verification (ruff + mypy) green; **pytest + `alembic check` could not run in the
worker sandbox** (Python execution + DB env are gated) — orchestrator must run
them. See *Verification* and *Do-not-merge conditions*.

---

## TL;DR

`case_type` is a new nullable, CDT-derived implant-case dimension on
`analytics.fact_patient_journey`. It is a rebuildable projection
(`manual > auto > unresolved`), derived in the fact builder from each person's
treatment-procedure CDT codes. No new `interaction.event` kind; no PHI added to
any payload or log; the ENG-511 event-payload contract (no `procedureCodeId`/CDT
in events) is **untouched**.

---

## Key design decision (needs operator/Codex awareness)

**Data source = raw treatment-procedure events, NOT `interaction.event` payloads.**

The task suggested adding the resolver as a `packages/interaction` aggregate +
the builder. I deviated on the *source*: `interaction.event` safe payloads
**deliberately exclude** `procedureCodeId`/CDT (ENG-511 PHI contract:
*"NEVER the procedureCodeId / CDT / tooth / surfaces / financials — those stay in
the gated raw_event only"*). They only carry an `is_implant_surgery` flag, which
cannot distinguish single vs full-arch vs overdenture vs bridge. So an interaction
aggregate genuinely cannot see the CDT granularity `case_type` needs.

Chosen path (derive in the analytics read-model from canonical data via services):

1. `IngestService.treatment_procedure_code_ids_by_patient(tenant)` →
   `{patientId: [procedureCodeId, …]}` (one entry per **distinct** procedure;
   raw layer; CareStack-id scalars only — no clinical fields leave `ingest`).
2. Builder maps `patientId → person_uid` via
   `IdentityService.source_links_for_external_records` (CareStack `patient` links).
3. Builder resolves `procedureCodeId → CDT` via
   `CatalogService.resolve_procedure_codes` (ENG-538 real catalog).
4. Builder applies the in-house precedence resolver
   (`packages/analytics/case_type.py`) per person.

**Why this is better than stamping a signal into event payloads:**
- Zero change to the ENG-511 event-payload PHI contract; nothing new in payloads/logs.
- Works on **existing** data immediately — `raw_event` always has
  `procedureCodeId`. (Stamping a token into events would require re-emitting
  every historical treatment event, which the capture change-guard suppresses.)
- `case_type` stays a pure analytics-derived dimension (the read-model doctrine:
  *derive from canonical schemas via services*).

**New read edges (both read-only, via services, no repo/schema access):**
`analytics (fact_builder) → ingest` and `analytics → catalog`. Both are
consistent with the analytics read-model doctrine and the catalog CLAUDE.md
(*"Read by … future analytics … via `CatalogService.resolve_procedure_codes`"*).
`analytics → phi` is **not** introduced. Flagged here for Codex cross-runtime
review since it widens what the builder imports.

---

## CDT → case_type for operator confirmation (DRAFT, `# OPERATOR-CONFIRM`)

Held in-house in `packages/analytics/case_type.py` (`_CDT_CASE_SIGNAL`), bootstrapped
from the real ENG-538 implant-category (cdtCategoryId=8) codes. Matching is exact on
`code.strip().upper()`.

| CDT code(s) | per-procedure signal | meaning |
|---|---|---|
| `D6010` | `placement` | single surgical placement — **counted** for single vs multiple |
| `D6010.A` | `all_on_x` | custom "Implant All on X" (catalog id 228501) |
| `D6114`, `D6115`, `D6118` | `all_on_x` | implant/abutment-supported fixed denture, edentulous arch (full-arch) |
| `D6053`, `D6054` | `overdenture` | implant/abutment-supported **removable** denture |
| `D6065`, `D6066`, `D6068`, `D6075` | `implant_bridge` | implant-supported FPD retainers/crowns |
| `D6011`, `D6011NC`, `D6012`, `D6013`, `D6040`, `D6050`, `D6056`, `D6057`, `D6058`, `D6080`, `D6100`, `D6103`, `D6104` | `implant_other` | implant-category but **non-determinative** (second-stage, abutments/crowns, mini/interim/eposteal/transosteal placement variants, maintenance/removal/graft) |

**Per-person precedence (documented):**
`all_on_x > overdenture > implant_bridge > multiple_implants > single_implant`

- `all_on_x` ← any `all_on_x` signal present
- else `overdenture` ← any `overdenture`
- else `implant_bridge` ← any `implant_bridge`
- else `multiple_implants` ← ≥ 2 `D6010` placements
- else `single_implant` ← exactly 1 `D6010` placement
- else → **`unclassified`** (`case_type` NULL): `has_implant=True` if any
  implant code at all (→ review surface), `has_implant=False` if no implant code
  (not an implant patient, not flagged).

**Allowed column values:** auto = `single_implant`, `multiple_implants`,
`all_on_x`, `overdenture`, `implant_bridge`. NULL = unclassified / non-implant.

**Out of auto scope — manual-only / future (NEVER auto-guessed):** `all_on_4`,
`all_on_6` (CDT only says "All on X"), `zygomatic` (no standard CDT),
`full_arch_upper` / `full_arch_lower` / `dual_arch` (arch side not in CDT). These
are settable via the ENG-513 enrichment path and validated against the allowed set.

**Two conservative choices for operator review (flagged, not guessed):**
1. **Only `D6010` counts as a placement** for single-vs-multiple (per spec). Other
   surgical-placement variants (`D6012`/`D6013`/`D6040`/`D6050` — interim/mini/
   eposteal/transosteal) map to `implant_other`, so a patient whose ONLY implant
   code is e.g. a mini-implant becomes *unclassified* (surfaced for review) rather
   than auto-labeled. If the operator wants these counted as placements, move them
   to `placement` in `_CDT_CASE_SIGNAL`.
2. `D6065`/`D6066`/`D6068`/`D6075` are treated as `implant_bridge`. Confirm the
   exact restorative-vs-bridge split with the operator.

---

## Per-person resolver behaviour

`resolve_case_type(cdt_codes)` → `CaseTypeResolution(case_type, has_implant)`.
`case_type='auto'` provenance in the builder when resolved; NULL +
`method='unresolved'` otherwise. Manual override (ENG-513) wins on rebuild via
`merge_provenance` + `_preserve_manual_values` (`case_type` added to both
`_UPSERT_COLUMNS` and `_MANUAL_PRESERVE_FIELDS`).

## Review surface (unclassified)

Persons with implant procedures but no determinative signal ship `case_type`
NULL. On every build the builder logs (no PHI — count + person_uids only):

```
fact_patient_journey.case_type.needs_review  unclassified_implant_count=<n> person_uids=[…]
```

mirroring the ENG-538 `catalog.procedure_codes.needs_review` line. The same cohort
is queryable: it is the set of persons returned by the per-person resolver with
`has_implant and case_type is None` (the resolver consumes
`IngestService.treatment_procedure_code_ids_by_patient`). The column itself is
filterable via the new partial index `WHERE case_type IS NOT NULL`.

---

## Changed files

**New**
- `packages/analytics/case_type.py` — in-house taxonomy + resolver (`# OPERATOR-CONFIRM`).
- `packages/db/alembic/versions/20260620_0000_c3d4e5f6a7b8_eng539_fact_case_type.py`
  — new immutable revision, `revision=c3d4e5f6a7b8`, `down_revision=b2c3d4e5f6a7`
  (the prior single head). Adds the column + partial index. No CHECK on values
  (taxonomy is operator-editable; mirrors the free-string `source` dimension).
- `tests/analytics/test_case_type.py` — mapping + precedence + unclassified +
  allowed-value tests.

**Modified**
- `packages/analytics/models.py` — `case_type String(32)` nullable column +
  partial index in `__table_args__`.
- `packages/analytics/fact_repository.py` — `case_type` in `_UPSERT_COLUMNS`
  (flows through `existing_for_merge` + `upsert_many` automatically).
- `packages/analytics/fact_builder.py` — inject `ingest` + `catalog`;
  `_resolve_case_type_by_person`; project `case_type` + provenance; `case_type`
  in `_MANUAL_PRESERVE_FIELDS`; `needs_review` log.
- `packages/analytics/enrichment_service.py` — `case_type` overridable (new
  `case_type` value-kind, validated against `ALL_CASE_TYPES`, accepts manual-only
  labels).
- `packages/analytics/schemas.py` — `case_type` in `FactOverridableField`.
- `packages/ingest/repository.py` — `treatment_procedure_code_ids_by_patient`
  (DISTINCT-ON-`external_id` newest payload per procedure; patient/code scalars only).
- `packages/ingest/service.py` — thin pass-through of the above.
- `apps/worker/jobs/fact_patient_journey_refresh.py` — wire `ingest` + `catalog`
  into the builder.
- `tests/analytics/test_fact_builder.py` — fakes for ingest/catalog/identity
  source-links; 3 case_type wiring tests (resolved / unresolved / manual>auto).
- `tests/analytics/test_fact_enrichment_service.py` — 2 case_type override tests.
- `tests/integration/test_fact_patient_journey_builder.py`,
  `tests/integration/test_journey_metrics.py` — inject `ingest`+`catalog` into the
  builder fixtures. (`test_journey_metrics` was **also missing `actor=`** since
  ENG-507 — a latent break only caught now because integration tests need a real
  PG DB; fixed in passing while touching the signature.)

---

## Tests

New / updated unit tests (DB-free):
- `test_case_type.py` — `classify_cdt` per-code mapping (incl. case/whitespace
  normalisation); precedence (all_on_x beats overdenture/bridge/multiple/single;
  overdenture beats bridge+placement; bridge beats placement; multiple beats
  single); unclassified-with-implant; not-an-implant; empty; resolver never emits
  a manual-only value.
- `test_fact_builder.py` — `case_type` auto-resolved (D6010+D6114 → `all_on_x`),
  unresolved for non-implant persons, manual `all_on_4` preserved over auto on rebuild.
- `test_fact_enrichment_service.py` — manual override accepts `all_on_4`; rejects
  an unknown value.

Integration tests (need real PG): builder + journey-metrics fixtures updated to
the new constructor signature.

## Verification

| Gate | Result |
|---|---|
| `ruff check` (all touched files) | **PASS** — all checks passed |
| `mypy packages apps` | **PASS** — no issues in 335 files |
| `pytest` (unit) | **NOT RUN — blocked**: Python execution is approval-gated in the worker sandbox |
| `cd packages/db && alembic check` | **NOT RUN — blocked**: requires `DATABASE_URL`/`SECRET_KEY`/`REDIS_URL` (unset in sandbox) |

Migration linearity confirmed by inspection: `c3d4e5f6a7b8` is the **sole new
head**, chained off `b2c3d4e5f6a7` (the prior head); model declares the column +
index so `alembic check` should report only the new revision.

### Reproduce (orchestrator)
```bash
# from worktree root, with test env (DATABASE_URL/SECRET_KEY/REDIS_URL) set:
ruff check .
mypy packages apps
python -m pytest tests/analytics/test_case_type.py \
                 tests/analytics/test_fact_builder.py \
                 tests/analytics/test_fact_enrichment_service.py -q
python -m pytest tests/integration/test_fact_patient_journey_builder.py \
                 tests/integration/test_journey_metrics.py -q   # real PG test DB
cd packages/db && alembic upgrade head && alembic check   # expect: only c3d4e5f6a7b8, no drift
```

### DB-backed verification (real catalog)
After `alembic upgrade head`, run the fact refresh for the tenant
(`refresh_fact_patient_journey`) on a DB with ENG-538 catalog + CareStack
treatment procedures, then:
```sql
SELECT case_type, count(*) FROM analytics.fact_patient_journey GROUP BY 1 ORDER BY 2 DESC;
```
Expect `case_type` populated for known implant persons (e.g. D6010-only →
`single_implant`/`multiple_implants`, D6010.A/D6114-15-18 → `all_on_x`, etc.), and
the `fact_patient_journey.case_type.needs_review` log to list unclassified-implant
persons. No env/DB was reachable from the worker sandbox to run this.

---

## Risks

- **patientId ↔ source_link string match.** The builder matches the ingest
  `patientId` string against `identity.source_link.source_id` for CareStack
  `patient` links (instance `carestack-main`). Both derive from the same CareStack
  id; a formatting mismatch (unlikely) would drop a person's case_type to NULL
  (fails safe → unclassified, never a wrong label). DB verification will confirm
  coverage.
- **Full-table reads.** Like the rest of the builder, the new aggregate is a
  full-table scan per build (no incremental narrowing on the read side) — same
  posture as existing ENG-506 reads; acceptable at current data volume.
- **DRAFT mapping.** `_CDT_CASE_SIGNAL` is provisional (`# OPERATOR-CONFIRM`),
  especially the two conservative choices noted above.

## Blockers

- None functional. The only open items are the **unrun pytest + alembic check**
  (sandbox limitation, not a code issue) and **operator confirmation of the DRAFT
  mapping**.

## Do-not-merge conditions

1. **Operator confirms the DRAFT CDT→case_type mapping + precedence** (this report).
2. **`pytest` (unit + integration) green** on a real PG test DB.
3. **`alembic upgrade head` + `alembic check` clean** (only `c3d4e5f6a7b8`, no drift).
4. **DB-backed verification** shows `case_type` populating for known implant
   persons against the real ENG-538 catalog.
5. **Codex cross-runtime review** of the new `analytics → ingest` / `analytics →
   catalog` read edges and the design decision above.
6. Merge to `main` **auto-deploys prod + runs this migration** — gate strictly on
   explicit operator go. This worker performed **no** commit/push/PR/merge/deploy.

## Runtime telemetry note

`runtime.json` / `runlog.md` live under the runtime home
(`…/d42647cef5fc/revenue-intelligence-analytics-v1/`), which is **outside the
worker's allowed working directory** (sandbox blocked access). Could not update
them; this in-repo report is the authoritative status.
