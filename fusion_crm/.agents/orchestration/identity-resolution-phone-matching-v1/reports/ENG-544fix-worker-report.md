# ENG-544fix — Codex review fixes (double-merge guard + no names in logs)

**Task:** ENG-544fix · **Linear:** [ENG-544](https://linear.app/fusion-dental-implants/issue/ENG-544)
**Parent epic:** ENG-541 · **Class:** normal (mutates identity data in live path — worktree-isolated)
**Branch:** `eng-544-eng-544` (PR #196) · **Worktree:** `worktrees/ENG-544fix` (isolated, NOT canonical)
**Runtime:** claude-code · **Session:** 870fb625554c · **Date:** 2026-06-20

> **DO NOT MERGE without operator sign-off, and DO NOT run the LIVE pass.**
> Fix pass only. No live mutations. Merge to `main` = unattended prod deploy.

---

## TL;DR

Addresses Codex CHANGES-REQUESTED items **3, 4, 5** on PR #196. Items 1, 2, 6
already PASS.

- **FIX 3+4 (idempotency / double-merge):** live replay now skips a
  `source_person_uid` that is already retired (`merge_event.merged_person_uid`),
  so one source is merged at most once — within a page, across pages, and across
  re-runs. Authoritative guard in the service (`is_person_retired`), plus a
  job-level within-pass short-circuit.
- **FIX 5 (no names in logs):** removed `source_display_name` /
  `candidate_display_name` from `MatchReplayDecisionOut` and the service. The
  replay DTO (the thing serialised to stdout/runtime artifacts) is now
  uid-only. Patrick Newton pair is identified by uid `464cc989… → 73e7523b…`.

## Changed files

| File | Change |
|---|---|
| `packages/identity/repository.py` | `is_person_retired(tenant_id, person_uid)` (EXISTS over `merge_event.merged_person_uid`) + `exists` import |
| `packages/identity/service.py` | retired-source guard in the `would_merge` branch (`apply=True`); removed `*_display_name` from `base` |
| `packages/identity/schemas.py` | removed `source_display_name` / `candidate_display_name`; docstring now uid-only |
| `apps/worker/jobs/replay_identity_matches.py` | within-pass `merged_source_uids` dedup short-circuit |
| `tests/identity/test_replay_open_match_candidate.py` | `test_double_merge_guard_skips_already_retired_source` + `is_person_retired` mock |
| `tests/worker/test_replay_identity_matches.py` | `test_live_pass_dedupes_two_candidates_for_same_source` |

No ORM model, migration, `.env`, or shared-contract changes.

## Tests run

- `ruff check` (touched files) — **clean**
- `mypy packages/identity apps/worker/jobs/replay_identity_matches.py` — **Success, no issues**
- `pytest tests/identity tests/worker` — **209 passed** (incl. 2 new regression tests)
- Dry-run Patrick Newton `would_merge`-by-uid pinned by
  `test_reversed_packed_name_would_merge_dry_run` (unchanged logic).

## Verification result

**PASS** — lint + typecheck + identity/worker suites green. Alembic drift not
applicable (zero model/migration changes); `alembic check` needs live DB
credentials absent from this isolated worktree.

## Risks

- Within a live page the idempotency guard relies on `add_merge_event` flushing
  before the next candidate is evaluated (it does — `repository.add_merge_event`
  calls `session.flush()`). Across pages/runs the committed `merge_event` rows
  are the source of truth.
- The dry-run path is unchanged and does not call the retired guard (pure
  classification); the guard is gated on `apply=True` to avoid an extra query
  per row on the 6,287-row dry-run scan.

## Blockers

None.

## Do-not-merge conditions

- DRY-RUN ONLY; no live pass run. Operator sign-off required before merge
  (merge to `main` auto-deploys prod + runs prod migration).
- Prefer Codex re-review before integration (this touches the live identity
  merge path).

**ready for Codex re-review**
