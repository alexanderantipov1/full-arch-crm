# STATUS — identity-phone-format-dedup

Ticket: **ENG-562** (related: ENG-341 / ENG-463 / ENG-541)
Branch: `feat/identity-phone-format-dedup` (worktree off `origin/main`, HEAD 4226e71)
Date: 2026-06-21

## Phase 1 — code (DONE, verified, NOT committed/pushed)

Canonical match-key so phone matching is format-independent. No new duplicates.

- `packages/identity/canonical.py` (new) — `normalise_phone` / `normalise_email`
  moved here (no import cycle), plus `phone_match_key` / `email_match_key` /
  `identifier_match_key` (total, never raise).
- `packages/identity/service.py` — re-exports the normalisers from `canonical`
  (all existing `from packages.identity.service import normalise_phone` callers
  unaffected); dropped now-unused `phonenumbers` import.
- `packages/identity/models.py` — `PersonIdentifier.value_match_key` column +
  `ix_person_identifier_kind_match_key (kind, value_match_key)`.
- `packages/identity/repository.py` — `add_identifier` stamps the match key
  (single insert choke point); the three exact-match read sites
  (`find_identifier`, `list_candidate_persons_by_identifiers`,
  `find_persons_sharing_identifier`) now compare on the match key with a
  raw-value OR fallback (`_value_or_match_key`) so there is no gap pre-backfill.
- Migration `e2f4a6c8b0d1` (additive: column + index only; backfill is OFF the
  deploy path).
- `infra/scripts/backfill_phone_match_key.py` (new) — idempotent, batched,
  dry-run default; fills `value_match_key` for the ~150k legacy rows.

### Verification (all green)
- `pytest tests/identity` → 119 passed (incl. 13 new unit tests).
- New integration test `tests/integration/test_phone_format_match.py` →
  1 passed against a **real migrated Postgres** (disposable `fusion_pf_test`):
  proves the digit-only ↔ E.164 pair now matches via both repository read paths.
- `ruff` clean, `mypy` clean (4 modules).
- `alembic heads` → single head `e2f4a6c8b0d1`.
- `alembic check` against migrated DB → **No new upgrade operations detected**
  (model ↔ migration parity confirmed).

## Phase 2 — data cleanup (PREVIEW ONLY, nothing written)

Reuses the existing `infra/scripts/merge_phone_duplicate_persons.py` (name-aware).

Dry-run on the local prod-copy (read-only):

```
1107 true-duplicate clusters, 1113 persons would merge into survivors.
```

These are the **name-compatible** same-phone clusters (the incident pair is
one of them). The broader ~3,560 format-collision groups minus these are
households (same phone, different name) — correctly LEFT SEPARATE — plus a small
malformed/international tail for manual review. Then `backfill_phone_match_key.py`
fills the column and `replay_identity_matches.py --live` re-checks open candidates.

## NOT done (needs operator go — irreversible / outward-facing)
- commit / open PR
- merge to main (= prod auto-deploy + prod migration)
- run backfill on prod
- run merge `--apply` on prod (1,113 person merges)
