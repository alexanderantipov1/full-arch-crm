# Decision Log

- 2026-06-05T15:52:55Z — Handoff: strategy/codex -> orchestrator/codex accepted for ENG-343 after the user requested Linear-backed Orchestrator execution.
- 2026-06-05T15:52:55Z — Created a named mission `agent-runtime-control-plane-v1` instead of overwriting `.agents/orchestration/current`.
- 2026-06-05T15:52:55Z — First implementation slice is ENG-345 Tools Registry Projection V1 because run history, approvals, and audit summaries need a stable list of approved tools before deeper runtime behavior lands.
- 2026-06-05T16:08:14Z — Handoff: orchestrator/codex -> worker/codex self-execute accepted for ENG-345. Isolated worktree launch was deferred because the canonical checkout already contains uncommitted Agent Runtime base changes from the same user-approved workstream.
- 2026-06-05T16:13:30Z — ENG-345 implemented as a safe discovery-only projection. It exposes backend metadata from `packages.tools.registry` plus planned Semantic Catalog tools; it does not execute tools or expose secrets.
- 2026-06-05T16:45:39Z — Handoff: orchestrator/codex -> worker/codex self-execute accepted for ENG-346 after ENG-345 was completed.
- 2026-06-05T17:00:00Z — ENG-346 implemented as persisted safe run summaries in `audit.agent_runtime_run`. This table is not a trace store and must not contain prompts, secrets, raw provider payloads, PHI, raw SQL, or unmasked row-level data.

## 2026-06-05T16:59:59Z — Scope: bugfix

Self-execute approved for ENG-347 via `--workspace self`.

- Linear: ENG-347 — https://linear.app/fusion-dental-implants/issue/ENG-347/ar-04-human-approval-requests-v1
- Prompt size: 1704 chars (under 5000-char threshold)
- Reason: Worker assignment accepted by Orchestrator.
- Allowed scope marker: bugfix

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.

## 2026-06-06T04:47:20Z — Handoff: production-reviewer -> orchestrator

Production review of PR #115 found merge-readiness follow-ups that require
Orchestrator ownership before workers are launched.

- Task bundle: `AR-PR115-REVIEW-FOLLOWUPS`
- Linear status: Needs Linear
- Reason: existing ENG-343 through ENG-350 issues are closed Done; new fix work
  must not be assigned to workers until Orchestrator creates or links active
  Linear issues.
- Report: `reports/PR115-production-review-followups.md`

The Orchestrator must create or link Linear issues for:

1. Gate `/dev/agent-runtime` behind the local-only dev-page policy, or move the
   surface out of `/dev/*` with an explicit production-facing decision.
2. Add backend role/env protection for `/agent-runtime/*`, especially provider
   health checks and approval mutation routes.
3. Persist safe failure/blocked run summaries for OpenAI health-check failures
   and make `ok=False` map to a non-success run status.
4. Synchronize mission ownership/runtime state so repo artifacts, runtime
   telemetry, Linear, and PR readiness agree.

## 2026-06-05T17:31:43Z — Scope: bugfix

Self-execute approved for ENG-348 via `--workspace self`.

- Linear: ENG-348 — https://linear.app/fusion-dental-implants/issue/ENG-348/ar-05-agent-audit-summaries-v1
- Prompt size: 1793 chars (under 5000-char threshold)
- Reason: Worker assignment accepted by Orchestrator.
- Allowed scope marker: bugfix

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.

## 2026-06-05T17:43:45Z — Scope: bugfix

Self-execute approved for ENG-349 via `--workspace self`.

- Linear: ENG-349 — https://linear.app/fusion-dental-implants/issue/ENG-349/ar-06-dia-and-semantic-catalog-linkage-v1
- Prompt size: 1816 chars (under 5000-char threshold)
- Reason: Worker assignment accepted by Orchestrator.
- Allowed scope marker: bugfix

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.

## 2026-06-05T17:57:29Z — Scope: docs

Self-execute approved for ENG-350 via `--workspace self`.

- Linear: ENG-350 — https://linear.app/fusion-dental-implants/issue/ENG-350/ar-07-workbench-documentation-and-verification
- Prompt size: 1738 chars (under 5000-char threshold)
- Reason: Worker assignment accepted by Orchestrator.
- Allowed scope marker: docs

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.

## 2026-06-06T19:07:26Z — Handoff: production-reviewer (round 2) -> orchestrator

Second-pass production review on PR #115 surfaced six open items after the
first-pass follow-ups landed in `b155dfd`. Reviewer (claude-code) did the
mechanical mission-state fix in the same turn (the symlink switch below) and
handed the remaining decisions to the Orchestrator.

- Task bundle: `AR-PR115-ROUND-2-FOLLOWUPS`
- Linear status: Needs Linear (same coordination gap as round 1)
- Report: `reports/PR115-ROUND-2-followups.md`

Open items for Orchestrator:

1. PR #115 draft -> ready decision (or document why it stays draft).
2. ENG-312 orphan disposition: commit the worktree artifacts + open separate PR,
   or archive the named mission and drop the worktree.
3. Linear backfill for AR-PR115-FIX-001..004 (and the round-2 bundle itself).
4. `.gitignore` vs archive vs commit for three untracked `.agents/` dirs:
   - `.agents/orchestration/20260517-103524-eng-178-eng-180-deploy-smoke-recovery/`
   - `.agents/orchestration/20260517-113000-parallel-startup-wave/`
   - `.agents/skills/source-command-verify/`
5. Optional pre-merge code re-read: `apps/api/routers/agent_runtime.py` authz,
   `packages/agent_runtime/service.py` `ok=False` path, two new Alembic revisions.
6. Scope-tag recalibration: ENG-347/348/349 were approved as `bugfix` but added
   public API surface; future feature-sized self-executes should not reuse the
   `bugfix` scope marker.

## 2026-06-06T19:15:00Z — Reviewer error correction: ENG-312 not orphaned

The round-2 review initially flagged ENG-312 (person.dob/ssn backfill) as an
orphaned mission with uncommitted worker artifacts. That was wrong.
`git log --all --grep="ENG-312"` shows commit `898b1e0` "ENG-312: backfill
identity.person.dob/ssn from latest CareStack payload" is reachable from
`origin/main` and local `main`. The product code is tracked in HEAD and the
worktree dir under `~/.fusion-agent-orchestrator/...` is already empty.

The mission spec dir at `.agents/orchestration/current/` was stale, not
orphaned — it was simply left in place after the merge. Archiving it to
`archived/2026-06-02-eng-312-person-dob-ssn-backfill/` (done earlier in this
turn) is the only correct action. No new ENG-312 PR is needed.

Updated `reports/PR115-ROUND-2-followups.md` FIX-007 section to reflect the
correction. Removed the cleanup_worktrees.py acceptance branch — nothing to
clean.

## 2026-06-06T19:07:26Z — Mission state: switched `current/` to active mission

Reviewer (claude-code) performed the mechanical half of FIX-004 that the
first-pass orchestrator left undone:

- `.agents/orchestration/current/` was a real directory describing ENG-312
  (the orphaned mission) and was the only repo-side copy of its spec files.
- ENG-312 spec moved to
  `.agents/orchestration/archived/2026-06-02-eng-312-person-dob-ssn-backfill/`.
- `.agents/orchestration/current` recreated as a symlink to
  `agent-runtime-control-plane-v1/`.
- Dashboard default mission path now resolves to the live mission.

No product code touched. No commit. The change is staged in the working tree
for the user to inspect before the orchestrator decides commit timing
alongside the other round-2 follow-ups.

## 2026-06-06T21:36:49Z — Orchestrator disposition: PR #115 is mergeable

User asked the Orchestrator to inspect mergeable PR #115. The Orchestrator
checked GitHub PR state and mission runtime state.

- PR: https://github.com/alexanderantipov1/fusion_crm/pull/115
- Head: `ebaacef947193a4f7d6114a32a7f81b49c89c9e3`
- Base: `main`
- Draft state: ready (`isDraft=false`)
- Mergeability: `MERGEABLE`
- Merge state: `CLEAN`
- GitHub checks:
  - `Lint + typecheck + tests`: pass
  - `Web — eslint + tsc + vitest`: pass
  - `Build + deploy api preview revision`: pass
- Local checkout: clean against `origin/codex-agent-runtime-control-plane-v1`.

Decision: FIX-006 is closed. PR #115 is ready for owner merge when repository
review policy is satisfied. No additional Orchestrator worker assignment is
needed for mergeability.
