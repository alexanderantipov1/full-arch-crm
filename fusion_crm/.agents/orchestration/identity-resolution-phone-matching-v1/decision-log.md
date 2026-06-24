# Decision log — identity-resolution-phone-matching-v1

## 2026-06-20 — Mission created from operator investigation

Handoff: User (operator) → Orchestrator. Origin: live investigation of person
`73e7523b-…` (Patrick Newton) on the staff card.

Findings (reproduced against local DB):
- Salesforce lead ingestion works (444k `lead.pull`, 64k source_links, 63k
  ops.lead). The specific lead `00QVw00000bKFvGMAW` was captured + hinted with
  `phone_normalized=+19167307719`, identical to the CareStack person's phone.
- Matcher did NOT link: name came reversed (`family_name="Newton Patrick"`, no
  given_name, no email) → `name_compatible=false` → phone_name (0.95) blocked →
  `phone_only_ambiguous` (0.70, open) + a **duplicate person** `464cc989-…`.
- Duplicate has 0 person_identifier rows → card same-phone block can't see it.
- Scale: 6,287 open match_candidates; 783 lead-persons with no identifier (656
  had a phone in the hint).

Operator requirements: (1) same phone ⇒ always surfaced on card even unmerged;
(2) reversed-name compatibility; (3) empty lead with name+phone ⇒ auto-resolve;
(4) fix systematically + backfill all existing cases.

Decisions:
- Scope = large / architectural. Task class **contract_change** (ENG-185).
- Structure: epic ENG-541 + children ENG-542 (A, P0) / ENG-543 (B) / ENG-544 (C).
- Owner: Claude implements + Codex cross-runtime review.
- Order: A (safety net) → B (rules) → C (backfill, dry-run first).
- Gate: no merge to main / no deploy without explicit operator approval.

Next: launch ENG-542 worker (worktree-isolated). ENG-543 must start with a
proposal step before implementation (contract_change).

## 2026-06-20 — Launches & proposal

- Handoff: Orchestrator → Worker (claude-code) for ENG-542 (P0). Background
  worker started (pid 3050), worktree `eng-542-eng-542`, draft-PR only, no merge.
  Linear ENG-542 → In Progress.
- ENG-543 proposal written (reports/ENG-543-proposal.md) + posted as Linear
  comment. Root cause: `_names_compatible` compares whole name fields, not words.
  Recommended fix: word-level tokenization, **Option B (subset match)**. Awaiting
  operator pick A/B/C + confirm "different names on one phone are surfaced, not
  auto-merged". No implementation until approved (contract_change, ENG-185).

## 2026-06-20 — ENG-543 proposal APPROVED

Needs decision RESOLVED. Operator approved **Option B (subset name match)** and
**surface-only for different-name same-phone** (no auto-merge; stays open +
shown in card). ENG-543 unblocked for implementation under the standard
contract_change gate (Codex cross-review, no merge without sign-off).

## 2026-06-20 — ENG-543 launched
Handoff: Orchestrator → Worker (claude-code) for ENG-543. Background pid 20699,
worktree-isolated, Option B baked into prompt. Draft-PR only; STOP for Codex
cross-review before integration; no merge without operator sign-off.

## 2026-06-20 — ENG-543 Codex cross-review: PASS
Handoff: Reviewer (codex) → Orchestrator. Verdict PASS on all 5 design checks,
no blockers (reports/ENG-543-codex-review.md; reviewer was read-only so
orchestrator persisted the file). Gate satisfied. ENG-543 PR #193 ready to merge
pending OPERATOR approval (merge to main = unattended prod deploy). ENG-544
backfill becomes runnable after merge. Monitoring loop stopped — decision now
with operator.

## 2026-06-20 — Merges + ENG-544 launch (operator-approved)
Operator explicitly approved merging both PRs in-conversation.
- ENG-543 PR #193 → MERGED to main (squash), Linear Done. Prod deploy triggered.
- ENG-542 PR #194 → MERGED to main (squash), Linear Done. Surfacing shipped;
  literal identifier-persistence deferred to ENG-341 (separate contract_change,
  operator-chosen). ENG-341 commented with the live confirmation.
- ENG-543/542 worktrees pruned.
- Handoff: Orchestrator → Worker (claude-code) ENG-544 (pid 84973), worktree off
  updated main. DRY-RUN ONLY; STOP before live merges for operator sign-off;
  draft PR + Codex review. Monitoring loop re-armed on ENG-544.

## 2026-06-20 — ENG-544 dry-run complete
Handoff: Worker (claude-code) → Orchestrator. PR #196 (draft), CI green.
Dry-run vs local DB: 6,287 scanned → would_merge 315 / stay_open 5,740 / skip 232;
0 live mutations (verified). Patrick Newton pair would_merge (phone_name,
cross_provider_match). Live mode implemented, NOT run. Awaiting operator: (a)
Codex cross-review of #196, (b) run LIVE pass. Monitoring loop stopped.

## 2026-06-20 — ENG-544 Codex review: CHANGES-REQUESTED → fix pass
Handoff: Reviewer (codex) → Orchestrator → Worker (claude-code). Codex found 3
real issues (verdict persisted to reports/ENG-544-codex-review.md): (3/4)
double-merge of an already-retired source when a source has multiple open
candidates in a page = non-idempotent live pass; (5) display_name in replay DTO +
CLI JSON output = names in logs (forbidden). PASS on policy-reuse, conservatism,
schema. Live pass NOT safe to run. Fix worker launched (pid 41104) on branch
eng-544-eng-544 (updates PR #196): add already-retired guard + same-source dedupe
+ regression test; strip names from DTO/output. Then Codex re-review. Operator
chose live pass = later/after review. Monitoring re-armed on fixer.

## 2026-06-20 — ENG-544 fixes pushed → Codex re-review
Handoff: Worker (claude-code) → Reviewer (codex). Fix commit ef20e12 on
eng-544-eng-544 (PR #196): already-retired-source guard + same-source dedupe +
2 regression tests; display_name removed from DTO + all job/CLI output. 209
identity/worker tests pass; CI lint+web green (preview deploy pending). Codex
re-review launched (pid 54073) focused on items 3/4/5 + live-pass safety.

## 2026-06-20 — ENG-544 Codex RE-review: PASS (live pass SAFE)
Handoff: Reviewer (codex) → Orchestrator. Verdict PASS; live 315-merge pass
declared SAFE to run from the reviewed code path (verdict persisted to
reports/ENG-544-codex-rereview.md). Items 3/4 fixed (is_person_retired guard +
merged_source_uids short-circuit + 2 regression tests), item 5 fixed (uid-only DTO/output).
Orchestrator verified the reviewer's infra-file mention was a stale-main artifact —
real diff is 11 ENG-544 files only, no deploy/schema/env changes. Gate satisfied.
Handed to operator: (a) merge PR #196, (b) run live pass + which DB. Monitoring stopped.

## 2026-06-20 — ENG-544 merged + LIVE pass on local :5434 — EPIC COMPLETE
Operator approved merge + live pass (local). PR #196 merged (c05b795, prod deploy
of the job triggered). Live replay run on local :5434: open 6287→5972 (−315),
315 accepted, 315 merge_events (134 cross_provider_match). Patrick Newton dup
464cc989 retired, source_link + ops.lead moved to canonical 73e7523b — card now
surfaces the Salesforce lead. ENG-544 + epic ENG-541 → Done. Worktrees pruned.
CAVEAT: the 315 historical merges were applied to LOCAL only; PROD still carries
the old duplicates until the operator runs `replay_identity_matches --live` on
prod. The matcher fix (ENG-543) + surfacing (ENG-542) ARE in prod (stop new dups).
Follow-up: ENG-341 (drop global UNIQUE phone/email) for literal identifier persistence.

## 2026-06-21 — Mission reopened: prod live pass — GO decision + execution-gap found
Handoff: Operator → Orchestrator. Operator delegated the GO/NO-GO on running
`replay_identity_matches --live` against PROD (the 315 historical dedup merges
applied to local only on 2026-06-20).

Orchestrator GO decision (delegated authority): **GO, conditioned on a PROD
dry-run first.** Rationale: same reviewed code path (PR #196), Codex re-review
PASS declaring the live pass SAFE, idempotent + resumable (retired-source guard
+ same-source dedupe), append-only `merge_event` so every merge is reversible,
and a companion un-merge tool exists (`split_wrong_merged_persons.py`, ENG-311).

**Execution gap found (corrects the operator's mental model):** there is NO
Cloud Run Job wired for `replay_identity_matches`. PR #196 shipped the job CODE
into the prod image but `deploy_cloud_run.sh` defines no `fusion-job-*` to invoke
it. So "run --live on prod" is not a single command — it requires, in order:
  1. (Linear gate) reopen ENG-544 or open a child execution issue for the prod pass.
  2. Add an on-demand Cloud Run Job def (ENG-510 pattern) to `deploy_cloud_run.sh`,
     default dry-run, `--live` opt-in via `--args`. → deploy-config change,
     needs DEPLOYMENT_RULES + Codex cross-review.
  3. Deploy the job to prod (prod deploy → operator approval).
  4. Run a PROD dry-run first (prod data may differ from the local snapshot;
     re-confirm the would_merge count before mutating). Operator reviews counts.
  5. Run `--live` on prod (315-ish patient-identity merges → hard-to-reverse
     outward action → explicit operator confirmation).

Two hard gates require explicit operator sign-off this session: (b) deploy the
new job to prod, and (e) execute `--live`. `Needs approval:` raised — surfaced
to operator with the plan above before any prod action.

## 2026-06-21T21:43:32Z — Scope: tiny

Self-execute approved for ENG-550 via `--workspace self`.

- Linear: ENG-550 — https://linear.app/fusion-dental-implants/issue/ENG-550
- Prompt size: 2898 chars (under 5000-char threshold)
- Reason: Worker assignment accepted by Orchestrator.
- Allowed scope marker: tiny

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.

## 2026-06-21 — ENG-550 created + PR #203 + Codex review PASS (deploy gate reached)
Operator chose "Full GO with checkpoint". Orchestrator executed prep:
- Linear ENG-550 (child of ENG-541) created for the prod-pass execution gap.
- Worktree `eng-550-prod-identity-replay-job` off origin/main (843ca21); added
  `fusion-job-identity-replay` to `deploy_cloud_run.sh` (ENG-510 pattern,
  default dry-run, live via explicit `--args` override). `bash -n` OK.
- PR #203 (draft) opened. No new secret/env/scheduler/migration/model change.
- Handoff: Orchestrator → Reviewer (codex, pid 88229) → Orchestrator. Verdict
  **PASS**, no blocking findings (reports/ENG-550-codex-review.md; reviewer
  read-only, orchestrator persisted). Contract_change gate satisfied.

CHECKPOINT 1 (operator): merge PR #203 + run prod full deploy to provision the
Job. `Needs approval:` — merge-to-main = unattended prod deploy. Pending
operator GO. After deploy: prod DRY-RUN first (checkpoint 2) before any --live.

## 2026-06-21 — PR #203 MERGED + job provisioned + PROD DRY-RUN (checkpoint 2)
Operator approved "Merge #203 + surgical deploy".
- PR #203 squash-merged → c823cd6. deploy-prod run 27918550192 SUCCESS (no rc=35
  rollback). CI_MODE skips Job provisioning, as expected.
- Surgically provisioned `fusion-job-identity-replay` via single idempotent
  `gcloud run jobs deploy` (create only, no service redeploy), pinned to the
  validated api image fusion-api:c823cd6 (mirrored sibling job's exact
  SA/vpc/env/secrets/resources). No service impact.
- PROD DRY-RUN execution fusion-job-identity-replay-f9ktj — SUCCESS, read-only
  (merged_applied=0, applied=false everywhere, exit 0).
  PROD counts (tenant 11111111-…): scanned 1328 / would_merge 178 /
  would_stay_open 1144 / skipped 6. (Local snapshot was 6287/315/5740/232 — prod
  has a smaller open backlog; this is why a prod dry-run was required.)
  All would_merge = single_tier1_auto_accept (phone_name/duplicate_phone),
  conservative; all stay_open = phone_only/email_only ambiguous.

CHECKPOINT 2 (operator): run the LIVE pass (~178 merges) on prod? `Needs
approval:` — hard-to-reverse outward action on patient identity. Pending GO.

## 2026-06-21 — PROD LIVE pass DONE — mission complete on prod
Operator approved GO. Live execution fusion-job-identity-replay-clx2m — SUCCESS,
0 errors: merged_applied **178**, leads_reassigned **163** (= dry-run would_merge
178, deterministic). Verification dry-run fusion-job-identity-replay-2cffx:
scanned 1150 (1328−178), would_merge **0** (backlog drained, idempotent),
would_stay_open 1144 (genuinely ambiguous phone_only/email_only — surfaced on the
card per ENG-542, correctly NOT merged), skipped 6.

Epic ENG-541 now fully shipped to prod (matcher + surfacing + historical dedup).
ENG-550 → Done. Job fusion-job-identity-replay remains provisioned for future
on-demand runs (re-run is a safe no-op). Follow-up unchanged: ENG-341 (drop global
UNIQUE phone/email). Worktree eng-550 pruned.
