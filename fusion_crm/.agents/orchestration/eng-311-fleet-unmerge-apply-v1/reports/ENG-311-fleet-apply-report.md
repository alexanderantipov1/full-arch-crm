# ENG-311 Fleet Un-Merge `--apply` — Operation Report

- **Task:** ENG-311-FLEET-APPLY (fleet split of wrong-merged CareStack persons)
- **Linear:** ENG-311 (Done) — DO-NOT-MERGE #3 deferred fleet apply to separate operator go
- **Role/agent:** orchestrator / claude (hybrid pattern)
- **Target:** local Docker Postgres `:5434` (prod-copy), tenant `11111111-1111-4111-8111-111111111111`
- **Branch/worktree:** main / `.` (operational run of an already-merged script; no code change)
- **Date:** 2026-06-02

## Result — SUCCESS
- Wrong-merged persons (DOB OR SSN mismatch): **3,808 → 0**.
- Splits performed this mission: **3,808** (canary 50 + fleet 3,758). With the prior
  Torosyan single split → **3,809** total `identity.person.split` audit rows.
- New Person rows created: persons total 110,042 → **114,334** (+~4,292; multi-bucket
  households spawn >1 new person).
- Errors: **0** across all batches. `needs_manual_review` rows flagged per design
  (ops.lead / followup_task / person_location_profile / non-patient events stay on the
  surviving person).
- Idempotent re-run after completion: `split=0 scanned=0` — confirmed.
- Legitimate same-human multi-pid persons (e.g. Gaiane Torosyan, same dob+ssn) preserved:
  1,224 multi-pid persons remain, all internally consistent, none wrongly split.

## Batch trajectory
canary 50 → 3,758 · 500 → 3,258 · 500 → 2,758 · 500 → 2,258 · 500 → 1,758 ·
500 → 1,258 · 500 → 758 · 500 → 258 · 258 → 0.

## Verification (real data, not mocked)
- **Audit rows PHI-clean:** `extra` carries counts + uuids only
  (`bucket_count`, `source_links_moved`, `consultations_moved`, `interaction_events_moved`,
  `surviving_person_uid`, `new_person_uids`). No dob/ssn/name VALUES.
- **Per-human financials via REAL API (`:8000`, MSW disabled):**
  - canary `1e80cb31` → pid `[1663653]`, paid **1905.6**, scoped to its single pid.
  - `000b6682` → `[1449750]` / `c4a269aa` → `[1460933]` — household pair cleanly partitioned.
  - Gaiane `5758e85c` → both legit pids `[1461274, 2171827]`, count=2 (correctly NOT split).
- **Re-audit:** `wrong_merged=0, dob_mismatch=0, ssn_mismatch=0`.

## Backup / reversibility
- Pre-apply dump: `~/fusion-backups/fusion_5434_pre-eng311-apply_20260602T005726Z.dump`
  (131 MB, custom format). Verified via container PG16 `pg_restore --list` (37 table-data
  entries incl. identity.person / source_link / audit.access_log).
  NOTE: restore must use PG16 (container) — local `pg_restore` is PG15.

## Adversarial review (Workflow wf_e10505fb-c34)
- no-PHI-leak = PASS, idempotency/safety = PASS, correctness = FAIL (1 major).
- Major ("surviving person.dob/ssn not updated") triaged ACCEPT — empirically inert:
  `identity.person.dob` is NULL in 0/110042 rows, so the ENG-309 veto (which needs both
  sides non-null) never fires on the surviving person. See incidents.md.

## Risks / follow-ups (non-blocking)
1. **ENG-312** (retroactive `person.dob/ssn` backfill) is now MORE relevant: post-split,
   new persons carry bucket dob/ssn while ~110K surviving/legacy persons stay NULL.
   ENG-312 should backfill uniformly from latest CareStack payload. Sequencing clean.
2. Minor: `--commit-every` flushes on `split` (success) not `processed`; only matters
   under high error rate (here error_count=0). Optional script hardening.

## Do-not-merge / commit status
- No product code changed. Repo changes are orchestration artifacts only (mission spec,
  archived ENG-310, this report, kickoff update). NOT committed — awaiting operator.
