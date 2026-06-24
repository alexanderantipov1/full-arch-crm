# PR115 ROUND-2 Production Review Follow-Ups

- Created at: 2026-06-06T19:07:26Z
- Source role: production-reviewer (claude-code)
- Target role: orchestrator (codex/orchestrator-b)
- PR: https://github.com/alexanderantipov1/fusion_crm/pull/115
- Parent Linear issue: ENG-343 (closed Done)
- Current Linear state for these items: Needs Linear
- Execution gate: items 2-6 below await Orchestrator handling; item 1 was
  resolved by the reviewer in the same turn.

## Summary

The first-pass production review (`PR115-production-review-followups.md`)
covered FIX-001 (local-only `/dev/*` gate), FIX-002 (backend authz),
FIX-003 (safe failure run-history semantics), and FIX-004 (mission state
sync). The first-pass orchestrator landed all four product fixes in commit
`b155dfd`, but FIX-004 only synced `ownership.yaml` and did not switch the
canonical `.agents/orchestration/current/` redirect from the orphaned
ENG-312 mission to the live `agent-runtime-control-plane-v1/` mission.

This second-pass review confirms PR #115 is structurally close to merge,
but six open items remain. One is mechanical and has been completed in this
turn (the `current/` symlink switch). Five are decision-bound and listed
below for the Orchestrator.

## State

- Branch `codex-agent-runtime-control-plane-v1` is 3 commits ahead of
  `origin/main`, mergeable, CI green on remote head:
  - `Lint + typecheck + tests` ✓
  - `Web — eslint + tsc + vitest` ✓
  - `Build + deploy api preview revision` ✓ (last run 2026-06-06T05:23Z)
- PR #115 is still DRAFT.
- Mission `agent-runtime-control-plane-v1` reports all ENG-344..ENG-350 as
  `completed` / Linear `Done`, and `AR-PR115-REVIEW-FOLLOWUPS` as
  `completed` with `Missing Linear` documented as a coordination note.
- Verify loop reported green by first-pass orchestrator after `b155dfd`:
  `make lint`, `mypy .`, `make test` (1358 passed), `alembic check` clean.

## Mechanical fix completed by reviewer in this turn

### AR-PR115-FIX-005 — `.agents/orchestration/current/` redirect switch

- Linear: Needs Linear
- Owner: reviewer (claude-code), then orchestrator for commit decision
- Status: done in working tree, not committed.
- What changed:
  - Moved `.agents/orchestration/current/` (ENG-312 spec) to
    `.agents/orchestration/archived/2026-06-02-eng-312-person-dob-ssn-backfill/`.
  - Recreated `.agents/orchestration/current` as a symlink to
    `agent-runtime-control-plane-v1/`.
- Why it was safe:
  - `current/` was a real directory and the only repo-side copy of the
    ENG-312 spec — naive symlink replacement would have erased it. The
    archive step preserves all spec artifacts (goal.md, acceptance.md,
    contract.md, verification.md, ownership.yaml, decision-log.md,
    incidents.md, lessons.md, ENG-312 worker report).
  - The named runtime path
    `~/.fusion-agent-orchestrator/c2db50910d08/eng-312-person-dob-ssn-backfill-v1/`
    already exists from the original mission run, so ENG-312 retains a
    runtime dir as well.
- Dashboard impact: the default mission path
  `.agents/orchestration/current/` now resolves to the live mission spec.

## Orchestrator Tasks (decision-bound)

### AR-PR115-FIX-006 — PR #115 draft -> ready decision

- Linear: Needs Linear
- Suggested priority: High
- Owner: orchestrator (request user input)
- Evidence:
  - All CI checks green; branch mergeable.
  - Mission closure recorded; first-pass and second-pass follow-ups either
    completed or scoped to Orchestrator.
  - PR remains `isDraft: true` on GitHub.
- Acceptance:
  - Either flip PR #115 to ready-for-review and request review per repo
    policy, OR record in `decision-log.md` the explicit reason the PR
    stays draft and who decides when to flip.

### AR-PR115-FIX-007 — ENG-312 mission state (resolved: already merged)

- Linear: ENG-312 (closed in main)
- Status: closed without action — round-1 reviewer error correction.
- Correction (2026-06-06T19:15Z):
  - The first-pass round-2 review claimed the worker artifacts at
    `~/.fusion-agent-orchestrator/c2db50910d08/current/worktrees/ENG-312/`
    were uncommitted. That was wrong.
  - `git log --all --grep="ENG-312"` shows commit `898b1e0` "ENG-312:
    backfill identity.person.dob/ssn from latest CareStack payload"
    is reachable from `origin/main` and local `main`.
  - `infra/scripts/backfill_person_dob_ssn.py` and
    `tests/infra/test_backfill_person_dob_ssn.py` are tracked in HEAD on
    every branch that contains `898b1e0`, including main.
  - The worktree directory under `~/.fusion-agent-orchestrator/...` is
    already empty — the orphan claim was caused by reviewer reading the
    stale worker report rather than git.
- What remains:
  - The spec dir `current/` was stale, not orphaned. Archiving it to
    `archived/2026-06-02-eng-312-person-dob-ssn-backfill/` (done in this
    turn) is the only action needed.
  - No new PR for ENG-312. No `cleanup_worktrees.py` run needed for the
    ENG-312 entry (worktree already gone).

### AR-PR115-FIX-008 — Linear backfill for FIX-001..005

- Linear: Needs Linear
- Suggested priority: Medium
- Owner: orchestrator (needs Linear MCP / web access)
- Evidence:
  - First-pass `AR-PR115-REVIEW-FOLLOWUPS` and round-2 mechanical
    `AR-PR115-FIX-005` shipped in the working tree without Linear issues.
  - Parent ENG-343 is closed Done; closure evidence currently lives only
    in mission reports.
  - Per `.agents/CLAUDE.md`, active execution without a Linear issue is a
    protocol violation; the deviation is documented but not closed.
- Acceptance:
  - Either create one umbrella Linear issue under the Agent Runtime
    project covering FIX-001 through FIX-008 with backlinks to the two
    follow-up reports, OR create one issue per fix.
  - Update `linear-sync.md`, `runtime.json`, and `board.md` once Linear
    ids are available.

### AR-PR115-FIX-009 — Untracked `.agents/` directories disposition

- Linear: Needs Linear
- Suggested priority: Low
- Owner: orchestrator + user decision
- Evidence (`git status` at handoff time):
  - `.agents/orchestration/20260517-103524-eng-178-eng-180-deploy-smoke-recovery/`
  - `.agents/orchestration/20260517-113000-parallel-startup-wave/`
  - `.agents/skills/source-command-verify/`
- Acceptance:
  - For the two `20260517-*` mission dirs: move to
    `.agents/orchestration/archived/` under the existing date-prefix
    convention, OR add to `.gitignore` if they are local-only scratch.
  - For `source-command-verify` skill dir: inspect contents and either
    commit (if it is an intended new skill) or `.gitignore` (if it is a
    scratch experiment).

### AR-PR115-FIX-010 — Pre-merge code re-read (optional)

- Linear: Needs Linear
- Suggested priority: Low
- Owner: orchestrator decides whether to schedule
- Evidence:
  - `apps/api/routers/agent_runtime.py` authz guards (404-in-prod +
    admin/system-only) added in `b155dfd`; tests added in the same
    commit. Not exercised against real auth middleware in a promoted
    preview.
  - `packages/agent_runtime/service.py` `ok=False` failure-run-summary
    path added in `b155dfd`; covered by unit tests, not by preview deploy.
  - Two new Alembic revisions (`d3e4f5a6b7c8`, `e5f6a7b8c9d9`) — verify
    down_revision chain and additivity.
- Acceptance:
  - Either record an explicit "no further code re-read required" decision
    in `decision-log.md`, OR schedule a focused reviewer pass before
    flipping the PR to ready.

### AR-PR115-FIX-011 — Scope-tag recalibration (advisory)

- Linear: Needs Linear (or a process note rather than a fix)
- Suggested priority: Low
- Owner: orchestrator process improvement
- Evidence:
  - ENG-347, ENG-348, ENG-349 self-execute approvals all used
    `--scope bugfix`, but each delivered a new public API surface
    (approval mutation routes, audit summaries DTOs, DIA/catalog linkage
    DTOs). The launcher accepted because the prompt was under 5000 chars,
    but the scope intent (small blast radius) was stretched.
- Acceptance:
  - Add a one-paragraph note to
    `.agents/skills/agent-orchestrator/SKILL.md` or to
    `.agents/orchestration/CLAUDE.md` clarifying that public-API-adding
    work should not be tagged `bugfix` for self-execute, even if the
    prompt fits the size cap.

## Next Orchestrator Actions (ordered)

1. Inspect the working tree change made by the reviewer
   (`git status` shows the symlink + archive move). Either accept and
   commit alongside the PR follow-up Linear backfill, or revert if a
   different redirect strategy is preferred.
2. Decide PR #115 ready/draft (FIX-006) — request user input.
3. Decide ENG-312 orphan disposition (FIX-007) — request user input.
4. Create Linear umbrella/per-fix issues for FIX-001..010 (FIX-008) —
   request user help if the active session lacks Linear write capability.
5. Decide `.agents/` untracked dirs disposition (FIX-009) — request user
   input.
6. Decide whether to schedule a code re-read (FIX-010).
7. Update `.agents/orchestration/CLAUDE.md` and/or orchestrator skill with
   the scope-tag note (FIX-011).
8. Re-run focused verification if any product code changes; otherwise
   keep the verify-loop evidence from `b155dfd`.

## Coordination markers

- `Handoff:` — production-reviewer -> orchestrator, recorded in
  `runtime.json` (handoff id `handoff-production-review-pr115-round2`) and
  `runlog.md`.
- `Needs decision:` — items FIX-006, FIX-007, FIX-009.
- `Needs approval:` — FIX-008 if Linear MCP is unavailable in the
  orchestrator session, same as round 1.
- `Missing Linear:` — entire round-2 bundle.

## Reviewer commitments (do-not-merge conditions)

- Reviewer did not touch product code, did not commit, and did not push.
- The only working-tree mutation is the `current/` archive + symlink
  switch and the mission-state file updates documenting the handoff.
- If the orchestrator decides not to keep the symlink approach, the
  archive move is reversible by `mv` back.

## Orchestrator Mergeability Disposition — 2026-06-06T21:36:49Z

The Orchestrator re-checked PR #115 after the round-2 follow-ups.

- PR: https://github.com/alexanderantipov1/fusion_crm/pull/115
- Head: `ebaacef947193a4f7d6114a32a7f81b49c89c9e3`
- Draft state: ready (`isDraft=false`)
- Mergeability: `MERGEABLE`
- Merge state: `CLEAN`
- Checks:
  - `Lint + typecheck + tests`: pass
  - `Web — eslint + tsc + vitest`: pass
  - `Build + deploy api preview revision`: pass
- Local checkout: clean against `origin/codex-agent-runtime-control-plane-v1`.

Disposition:

- FIX-006 is closed; the PR is no longer draft.
- No additional product-code work is required for mergeability.
- Orchestrator recommends merging PR #115 when the repository owner is ready.
