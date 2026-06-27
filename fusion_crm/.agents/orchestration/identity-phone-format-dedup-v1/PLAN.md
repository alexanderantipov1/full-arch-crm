# Remediation plan — phone-format identity duplicates

> Status: **DRAFT for operator review** · Date: 2026-06-21 · Owner: TBD
> Related: ENG-463 (E.164 on arrival), ENG-541/550 (phone matching + replay),
> ENG-340/341 (shared-contact unique constraint), ENG-552 (household grouping)

## 1. Problem statement

The same human is being stored as **multiple `identity.person` rows** that the
matcher never collapses, because the same phone number is persisted in
**different string formats** and every comparison is exact-string.

Concrete trigger (the case the operator hit):

| Person | Created | Source | `person_identifier.value` (phone) | DOB |
|--------|---------|--------|-----------------------------------|-----|
| `27323d75-…` | 2026-06-09 | CareStack | `2015550123` (digit-only) | yes |
| `514d0368-…` | 2026-06-19 | Salesforce | `+12015550123` (E.164) | no |

Both are the **same person**, same number. The `phone_name` Tier-1 auto-accept
rule (0.95) *should* have merged them regardless of which source arrived first.
It did not, because `2015550123 != +12015550123` as strings.

### Root cause

- ENG-463 (commit `e387d21`, 2026-06-15) made `normalise_phone()` emit E.164
  (`+1XXXXXXXXXX`) for **new** writes, but **no backfill** of existing rows shipped.
- All identity lookups compare the **raw stored string** exactly:
  `repository.find_identifier`, `list_candidate_persons_by_identifiers`,
  `find_persons_sharing_identifier` (all `PersonIdentifier.value == <value>`).
- So any post-2026-06-16 E.164 lead silently fails to match its pre-2026-06-16
  digit-only counterpart and creates a duplicate. The dedup sweep / ENG-550
  replay cannot recover it either — they also key on exact value.

### Blast radius (measured on the prod copy in local DB, 2026-06-21)

- `identity.person_identifier` phones: **99,323 legacy digit-only** vs **386 E.164**.
- Phone digit lengths: 62,697 ten-digit, 36,617 eleven-digit (leading `1`),
  ~265 with 12–21 digits, ~130 with 7–9 digits (malformed / international tail).
- **~3,560 phone "cores"** are stored across **>1 person AND in >1 format** —
  i.e. ~3,560 likely phantom-duplicate groups.
- Emails are clean (54,491 rows, all lower-cased, no spaces) → **phone-only problem**.
- This is **actively generating new duplicates** every day until fixed.

## 2. Design decision (the fork)

There are two ways to make matching format-independent:

- **Option A — backfill `value` to E.164 + keep global `UNIQUE(kind,value)`.**
  Rejected as the primary fix. It collides with two realities:
  1. Cross-person collisions on backfill = exactly the dup pairs (must merge first).
  2. **Household sharing** — two different people legitimately share one phone
     (different names, ENG-340/341/552). Backfilling both to the same E.164 value
     violates the global unique constraint. Coupling remediation to the ENG-341
     schema rework would balloon scope.

- **Option B — canonical match-key, comparison on canonical (RECOMMENDED).**
  Stop comparing raw strings. Maintain a canonical phone key
  (E.164 via `normalise_phone`, with a deterministic fallback for the
  unparseable tail) and compare canonical-to-canonical. This:
  - fixes matching for ALL formats immediately, at ingest, regardless of order/source;
  - does **not** touch the global unique constraint (no household regression);
  - lets the existing merge/replay machinery clean up history unchanged;
  - leaves stored display values alone (optional cosmetic backfill later, under ENG-341).

**Recommendation: Option B.** Phases below assume it.

## 3. Phased plan

### Phase 0 — Verify & freeze the picture (no writes)
- Re-run the blast-radius queries against **prod** (read-only) to confirm counts
  match the local copy. (Operator approval required for the prod read.)
- Snapshot: dump `merge_event` count + the 3,560-group query result to a report
  file under `reports/` so we can diff before/after.

### Phase 1 — Canonical match-key + format-independent comparison (code)
Goal: **no new duplicates**, matching works across formats at ingest.

1. Add a single canonicalizer `phone_match_key(value) -> str` in
   `packages/identity` (reuse `normalise_phone`; for the unparseable tail return
   a stable digit-core, e.g. last-10-digits, never empty). One function, used
   everywhere — no scattered logic.
2. Persist the key: add nullable `value_match_key` column to
   `identity.person_identifier` (new Alembic revision; **additive, immutable
   rule respected**). Backfill the column for all existing rows in the same
   migration (computed, not value-rewriting — display `value` untouched).
   Index `(kind, value_match_key)`.
3. Write path: populate `value_match_key` on every insert/upsert of an identifier.
4. Read path: change the **three** comparison sites in
   `packages/identity/repository.py` to filter on `value_match_key` (computed
   from the incoming normalized value) instead of raw `value`:
   - `find_identifier`
   - `list_candidate_persons_by_identifiers`
   - `find_persons_sharing_identifier`
5. Keep `UNIQUE(kind, value)` as-is for now (still allows both formats as rows;
   harmless once matching is canonical). Do **not** add a unique on the match-key
   yet — that's the household/ENG-341 question.
6. Tests: unit (`phone_match_key` across +1 / 1 / 10-digit / international / junk),
   and an integration test reproducing the cross-format pair → asserts
   `phone_name` auto-accept now fires regardless of ingest order.

**Risk:** read-path change to the resolver. Mitigated by tests + the fact that
new writes are already E.164 (canonical ⊇ exact). Cross-runtime (Codex) review
required — this is a contract-touching change.

### Phase 2 — Clean up existing duplicates (data, dry-run first)
Reuse what exists; do **not** reinvent merge mechanics.

1. `infra/scripts/merge_phone_duplicate_persons.py` already clusters by
   canonical E.164 phone **+ name compatibility** (won't merge different-name
   household members) and repoints all cross-domain refs
   (`ops.lead/followup_task/consultation/opportunity`, `interaction.event`,
   `phi.consultation/patient_profile`, `actor.actor`, `outreach.send`,
   `integrations.external_entity`, `ingest.normalized_person_hint`,
   `attribution.lead_attribution`, `ops.person_location_profile`), with
   collision-safe move/delete on the unique-constrained tables, and records
   `merge_event(reason='duplicate_phone')`.
   - **Dry-run pass** → produce a report of every cluster it would merge
     (count, person UUIDs, surviving UUID, names) for operator review.
   - Carve out the malformed/international tail (digits not in 10–11, leading
     non-`1`): **do not auto-merge**, list for manual review.
2. `apps/worker/jobs/replay_identity_matches.py` (`--live`) re-evaluates any
   remaining `status='open'` match candidates under the new canonical policy.
   - Dry-run first; review the would-merge sample; then live.
3. After Phase 1 ships, the natural ingest sweep also catches these going forward.

**Reversibility:** merges are append-only `merge_event` rows; ENG-311 unmerge
tooling exists if a cluster was wrong. Dry-run + sample review before any live pass.

### Phase 3 — (Optional, deferred) cosmetic value backfill + constraint rework
- Rewrite stored `value` to E.164 for display consistency. **Only** meaningful
  once ENG-341 relaxes `UNIQUE(kind,value)` to permit shared household contacts;
  otherwise it re-introduces the collision. **Defer and couple to ENG-341 /
  ENG-552**, do not block Phases 1–2 on it. With the canonical match-key in
  place, this phase is purely cosmetic and non-urgent.

## 4. Sequencing & gating
1. Phase 1 lands behind tests + Codex review → merge → auto-deploys prod
   (operator must approve the deploy session per merge=deploy policy).
2. Phase 2 dry-run report → operator reviews clusters → live pass on prod
   (explicit confirmation; it's a bulk mutate).
3. Phase 3 only after ENG-341.

## 5. Open questions for the operator
1. **Auto-merge vs review for Phase 2:** auto-merge all name-compatible
   same-phone clusters (≈3,560), or generate the report and merge in batches
   after you eyeball them? (Recommend: dry-run report first, then auto-merge the
   clean 10/11-digit US set, manual-review the tail.)
2. **Phase 3 timing:** fold the cosmetic E.164 backfill into ENG-341, or skip
   indefinitely (canonical key makes it unnecessary)?
3. **Ticket:** new Linear issue under the identity epic, or extend ENG-341?

## 6. Files in scope (Phase 1)
- `packages/identity/service.py` — `phone_match_key`, write-path population.
- `packages/identity/repository.py` — 3 comparison sites → match-key.
- `packages/identity/models.py` — `value_match_key` column.
- `packages/db/alembic/versions/<new>.py` — add column + index + backfill.
- `tests/identity/…` — unit + integration repro.

Phase 2 uses existing scripts (no new code expected beyond a tail-carve flag).
