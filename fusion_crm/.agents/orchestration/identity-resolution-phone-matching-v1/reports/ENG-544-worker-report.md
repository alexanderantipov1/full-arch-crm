# ENG-544 — Backfill/replay: reprocess candidates + dedup-merge

**Task:** C — Backfill/replay: reprocess open match candidates + dedup-merge
**Linear:** [ENG-544](https://linear.app/fusion-dental-implants/issue/ENG-544) ·
**Parent epic:** ENG-541 · **Class:** normal (mutates identity data — worktree-isolated)
**Branch:** `eng-544-eng-544` · **Worktree:** `worktrees/ENG-544` (isolated, NOT canonical)
**Runtime:** claude-code · **Date:** 2026-06-20

> **DO NOT MERGE without operator sign-off, and DO NOT run the LIVE pass.**
> This task delivers the job + a **DRY-RUN ONLY** verification. Zero live
> mutations were performed (verified against the DB — see below). Merge to
> `main` = unattended prod deploy + prod migration.

---

## TL;DR

A new on-demand arq job **`replay_identity_matches`** walks every OPEN
`identity.match_candidate` and re-evaluates it under the **current** (ENG-543
word-level) policy by reusing `IdentityService` / `_evaluate_match_policy` —
**no re-implemented matching**. Dry-run (the DEFAULT) mutates nothing and emits
counts + a representative sample.

**Live dry-run against the local DB** (`:5434`, container
`fusion-crm-postgres-1`, db `fusion`, tenant `11111111-…-111111111111`):

| metric | value |
|---|---|
| scanned (open candidates) | **6,287** |
| **would_merge** | **315** |
| would_stay_open | **5,740** |
| skipped (no current match) | **232** |
| merged_applied / leads_reassigned | **0 / 0** (dry-run) |

The **Patrick Newton** acceptance pair is in the sample and resolves exactly as
required: `464cc989… 'Newton Patrick'` **would_merge → `73e7523b… 'Patrick
Newton'`**, rule `phone_name`, reason `cross_provider_match`, `applied=false`.

Post-run DB checks confirm **zero mutations**: candidate `71432e05…` still
`open`, open count still `6,287`, `0` merge_events with replay evidence, the
duplicate's source link unmoved.

---

## Pre-flight (important)

The worktree was cut from an **older** main and was **5 commits behind**
`origin/main` — it did **not** contain **ENG-543** (the word-level name rule
this task depends on) or **ENG-542**. I fast-forwarded the clean feature branch
(`b0453cd → 4702f99`, no local commits) so the replay runs against the policy
the task assumes. Without this, "Newton Patrick" tokenizes to `{'newton
patrick'}` (old field-level rule) and would NOT merge.

---

## How the replay reuses policy (no re-implementation)

For each open candidate the service reconstructs the original ingest hint and
re-runs the **existing** `_evaluate_match_policy`:

- **Names / DOB / SSN** come from the source person (the lead duplicate).
- **The shared identifier** (phone for `phone_only_ambiguous`, email for
  `email_only_ambiguous`) is read off the **candidate person** — the lead
  dropped its copy under the ENG-340 shared-contact guard (verified: 3,855 of
  4,972 phone_only sources hold **zero** identifiers), so the value lives on the
  canonical person + in `ingest.normalized_person_hint`.
- The source person's own free identifiers ride along for the other kind so the
  ambiguity count stays faithful.

Classification:

- **would_merge** — a single Tier-1 auto-accept whose target **is exactly the
  recorded candidate person**. Survivor = the existing canonical person; merged
  = the lead duplicate. (If the policy auto-accepts to a *different* person, the
  pair is kept open — out of scope for this recorded pair.)
- **would_stay_open** — multiple Tier-1 candidates (`auto_accept_eligible>1`) or
  a genuine name disagreement. A strong phone match never overrides a real name
  conflict. (Sample examples: `Michael Trofimenko` vs `Natalie Trofiminko`;
  `Olga Baymagametova` vs `Karina Baymagambetova` — household members sharing a
  phone, correctly left open.)
- **skipped** — no current match (identifier gone / person missing / ENG-309
  DOB·SSN hard veto).

### Live-pass mechanics (implemented, NOT run)

`apply=True` performs, in one unit of work:
1. `IdentityService.record_merge(survivor, merged, reason)` — append-only
   `merge_event`. `reason='cross_provider_match'` when the two persons originate
   in different providers (the SF-lead vs CareStack-patient case), else
   `duplicate_phone` / `duplicate_email`.
2. move the merged person's `source_link` rows onto the survivor
   (`IdentityRepository.reassign_source_links`).
3. mark the candidate `accepted` with `merge_event_id` linked.
4. the **job** then moves `ops.lead` rows via `OpsService.reassign_leads`
   (cross-domain, so the job orchestrates it; identity never imports ops).

Reversible (append-only merge model; the merged person row is kept as a
tombstone) and audited.

---

## Changed files

| File | Change |
|------|--------|
| `apps/worker/jobs/replay_identity_matches.py` | **NEW** arq job (dry-run default + `--live`); pages open candidates, aggregates counts, builds sample (always includes the acceptance pair). Registered in `apps/worker/main.py` `WorkerSettings.functions` (on-demand, **NO cron**). |
| `apps/worker/main.py` | Register `replay_identity_matches`. |
| `packages/identity/service.py` | `replay_open_match_candidate` (reuses `_evaluate_match_policy`), `list_open_match_candidates` (cursor paging), `count_open_match_candidates`, internal `_apply_replay_merge` + `_replay_merge_reason`. |
| `packages/identity/repository.py` | `list_open_match_candidates_after` (id-cursor), `count_open_match_candidates`, `reassign_source_links`. |
| `packages/identity/schemas.py` | `MatchReplayDecisionOut`, `MatchReplaySummaryOut` DTOs. |
| `packages/ops/service.py` | `reassign_leads`. |
| `packages/ops/repository.py` | `reassign_leads` (+ `update` import). |
| `tests/identity/test_replay_open_match_candidate.py` | **NEW** — 7 tests (acceptance pair, live side-effects, name-disagreement stays open, multi-candidate stays open, no-match skip, missing source skip, same-provider reason). |
| `tests/worker/test_replay_identity_matches.py` | **NEW** — 3 tests (dry-run count aggregation + focus sample, live lead reassignment, `--limit` cap). |

No model/migration/`.env`/shipped-revision changes. The 9th-schema and the
`UNIQUE(kind,value)` constraint (ENG-341) are **untouched**.

## Tests run

- `pytest tests/identity/ tests/worker/test_replay_identity_matches.py` →
  **108 passed** (94 prior identity + 7 new replay + 3 new worker, plus others).
- `pytest tests/ops` → **75 passed, 2 failed**. The 2 failures
  (`test_covering_opportunity.py`, a `ConsultationOut.source_status` MagicMock
  fixture issue at `ops/service.py`) are **pre-existing** — confirmed they fail
  identically with `origin/main`'s ops files (`git stash` of my ops edits).
  Unrelated to `reassign_leads`.
- `mypy` on all 7 changed source files → **Success, 0 issues**.
- `ruff check` + `ruff format --check` on changed files → **clean**.
- `cd packages/db && alembic check` → **"No new upgrade operations detected"**
  (no schema drift).

## Verification (`/verify` gate)

| Step | Result |
|------|--------|
| `ruff` (lint + format) | **PASS** (changed files) |
| `mypy` | **PASS** — 0 issues in the 7 changed source files |
| tests | **PASS** for all new/affected logic; the only red lines are the **pre-existing** ops/covering-opportunity mock baseline (identical on `origin/main`) |
| `alembic check` | **PASS** — no drift |
| local dry-run | **PASS** — counts produced; acceptance pair confirmed; **0 live mutations** (verified in DB) |

## Risks

- **Reconstruction approximation (multi-value candidate person).** When a
  canonical person owns multiple phones/emails, the replay picks the
  deterministic first of the shared kind. For the dominant single-value case
  (the lead-duplicate population) this is exact; multi-value canonicals are rare
  and only affect which value seeds the ambiguity query — never causes a merge
  to a name-incompatible person (the subset name rule + single-Tier-1 guard
  still gate every merge).
- **Cross-domain rows beyond `ops.lead`.** The live pass moves `source_link` +
  `ops.lead` (the task scope; the duplicates are lead-created). It does **not**
  move `ops.consultation` / `ops.opportunity` / `interaction.event` /
  `phi.*` rows keyed to the merged person. For the lead-duplicate population
  those are typically absent, but a broader "reference rewrite on merge" is a
  follow-up before a general-purpose merge tool. Flagged below.
- **Live transaction size.** The live pass commits one page (default 500) per
  transaction and is resumable (decided rows leave the open work-list). Tune
  `page_size` if needed.
- **315 would_merge is conservative by design.** Most shared-phone pairs are
  genuinely different people (household members) and correctly stay open;
  avoiding wrong merges > avoiding duplicates (`packages/identity/CLAUDE.md`).

## Needs decision

- **Needs decision:** scope of cross-domain reference rewrite on merge. This
  task moves `source_link` + `ops.lead` (per the deliverable). If the operator
  wants the live pass to also re-point `ops.consultation` / `ops.opportunity` /
  `interaction.event` for merged persons, that is an additive follow-up
  (separate small task) — not silently absorbed here.

## Do-not-merge conditions

1. **Operator sign-off required for the LIVE pass.** This task is **DRY-RUN
   ONLY**; `merged_applied=0`, zero DB mutations performed. **Awaiting operator
   sign-off before any live `--live` / `dry_run=False` run.**
2. **Operator-only merge/deploy.** Merge to `main` auto-deploys prod + runs the
   prod migration with no gate — do NOT self-merge. Ships as **DRAFT PR**.
3. Prefer **Codex cross-runtime review** — this consumes the ENG-185/ENG-543
   identity matching policy and writes merges in the live path.
4. The ops/covering-opportunity test red lines are **pre-existing baseline**;
   confirm against CI baseline before treating as regressions (this change adds
   **0** new failures, **0** new mypy errors).

---

## How to run

```bash
# dry-run (default, read-only) — produces counts + sample:
python -m apps.worker.jobs.replay_identity_matches --tenant-id <uuid>

# LIVE (operator-only, mutates) — perform the merges:
python -m apps.worker.jobs.replay_identity_matches --tenant-id <uuid> --live
```
Enqueue form: `await pool.enqueue_job("replay_identity_matches",
tenant_id="<uuid>", dry_run=True)`.

Dry-run JSON artifact saved to the runtime logs:
`~/.fusion-agent-orchestrator/<repo-hash>/identity-resolution-phone-matching-v1/logs/ENG-544-dryrun-report.json`.

**Awaiting operator sign-off for the live pass.**

---

## Codex review fixes (PR #196, second pass — 2026-06-20)

Codex cross-review verdict was **CHANGES-REQUESTED**. Items 1, 2, 6 PASS as
shipped. Items 3, 4, 5 are addressed below. Branch unchanged (`eng-544-eng-544`);
still **DRY-RUN ONLY**, no live pass run, do NOT merge without operator sign-off.

### FIX 3 + 4 — live-pass safety + idempotency (double-merge guard)

**Problem (Codex):** the live replay path had no guard that `source_person_uid`
was already retired. If one source person owned **multiple** open
`match_candidate` rows, row 1 merged source → survivor A and a later row
re-merged the same tombstone source → survivor B — a double-merge, non-idempotent
across re-runs.

**Fix — two layers:**

1. **Authoritative service guard (idempotent, re-runnable).**
   New `IdentityRepository.is_person_retired(tenant_id, person_uid)` —
   `EXISTS(merge_event WHERE merged_person_uid = person_uid)`. In
   `IdentityService.replay_open_match_candidate`, the `would_merge` branch now,
   when `apply=True`, checks this **before** `_apply_replay_merge`. An
   already-retired source returns `outcome="skipped"`,
   `detail="source_already_retired"`, `applied=False` — never a re-merge.
   Because `add_merge_event` flushes, a merge recorded earlier in the **same**
   page transaction is visible to the guard, so it also dedupes same-source
   candidates within a page; committed merges from a previous page or a prior
   run are caught too. The live pass is now safely re-runnable.
2. **Job-level within-pass short-circuit.** `_replay_tenant` tracks
   `merged_source_uids`; a later candidate whose source was already merged this
   pass is counted `skipped` without re-evaluating the policy. The service guard
   is the backstop; this just avoids a redundant evaluation.

**Regression tests added:**
- `tests/identity/test_replay_open_match_candidate.py::test_double_merge_guard_skips_already_retired_source`
  — one source, two open candidates, `apply=True`: first → `would_merge`
  (applied), second → `skipped` / `source_already_retired`; asserts
  `add_merge_event` awaited **exactly once** (no second merge_event for that
  `merged_person_uid`).
- `tests/worker/test_replay_identity_matches.py::test_live_pass_dedupes_two_candidates_for_same_source`
  — job live pass: two candidates share one source → `merged_applied=1`,
  `skipped=1`, `replay_open_match_candidate` awaited once.

### FIX 5 — no names in logs (audit/PHI, HARD rule)

**Problem (Codex):** `MatchReplayDecisionOut` carried `source_display_name` /
`candidate_display_name`; the CLI/job serialises the whole DTO to stdout +
runtime artifacts, so names reached logs — root `CLAUDE.md` forbids names in
logs.

**Fix:** removed both `*_display_name` fields from the DTO and from the `base`
dict in `replay_open_match_candidate`. The DTO now identifies persons by
`person_uid` only (`source_person_uid`, `candidate_person_uid`,
`survivor_person_uid`, `merged_person_uid`) plus `match_rule` / `merge_reason` /
`detail` / counts. Repo-wide grep confirms **zero** remaining
`source_display_name` / `candidate_display_name` references in code/DTO/stdout.
The Patrick Newton pair is identified in the dry-run sample by **uid**
(`464cc989… → 73e7523b…`). Human-readable names appear ONLY in this markdown
report, never in the DTO/stdout/logs.

### Verification (second pass)

- `ruff check` (touched files) — **clean**.
- `mypy packages/identity apps/worker/jobs/replay_identity_matches.py` —
  **Success, no issues**.
- `pytest tests/identity tests/worker` — **209 passed** (includes the 2 new
  regression tests).
- **Dry-run by uid:** the `would_merge` Patrick Newton classification is pinned
  by `test_reversed_packed_name_would_merge_dry_run` (survivor = canonical,
  merged = source, rule `phone_name`, reason `cross_provider_match`,
  `applied=False`) — unchanged. The DB-backed dry-run counts above remain valid:
  this pass changed only the live-apply guard + removed name fields, not the
  classification logic.
- **Alembic drift:** the diff touches **zero** ORM models and **zero** migration
  files (added a read-only repository query + service/DTO/job logic only), so no
  schema drift is possible. `alembic check` itself needs live DB credentials,
  which this isolated worktree does not carry (they live in the canonical
  `.env`); it was not run here for that reason, not because of a model change.

### Changed files (this pass)

- `packages/identity/repository.py` — `is_person_retired` + `exists` import.
- `packages/identity/service.py` — retired guard in `would_merge`; dropped name
  fields from `base`.
- `packages/identity/schemas.py` — removed `source_display_name` /
  `candidate_display_name`; docstring now states uid-only.
- `apps/worker/jobs/replay_identity_matches.py` — within-pass `merged_source_uids`
  dedup.
- `tests/identity/test_replay_open_match_candidate.py`,
  `tests/worker/test_replay_identity_matches.py` — regression tests + mock for
  `is_person_retired`.

### Do-not-merge conditions (unchanged)

- DRY-RUN ONLY. No live pass run. Merge to `main` = unattended prod deploy +
  prod migration — operator sign-off required.

**ready for Codex re-review**
