# Decision Log — Dashboard Auto-Track Active Mission

## 2026-05-22T02:25:00Z — Needs decision: adopt pre-existing branch or restart

Branch `eduardk/eng-223-dashboard-auto-track-active-mission` already
carries a complete implementation (commit `0d346fd`, 453 added lines,
19 unit tests, dated 2026-05-21T19:00 PDT) plus an archive sweep
commit (`16924e8`, four completed mission folders moved into
`archived/2026-05-21-<name>/`). No PR was ever opened.

The pre-existing implementation matches the spirit of `acceptance.md`
and `contract.md` written for this mission — the only differences are
cosmetic (`resolution_reason` strings use prose rather than canonical
short codes; tests live under `.agents/dashboard/tests/` rather than
`.agents/skills/agent-orchestrator/tests/`).

Main has advanced one commit since the branch was created (`31c001d`
ENG-222 scheduled ingest, PR #88 merged). A rebase is required to
remove the spurious `-592` deletion lines from the branch diff before
any PR can land cleanly.

### Decision needed

Pick one:
1. **Adopt existing branch (recommended).** Rebase on main, verify
   tests, drop or rewrite the just-created
   `.agents/orchestration/dashboard-auto-track/` mission folder so it
   does not conflict with the archive commit, open PR.
2. **Adopt + adjust.** Same as (1) but also amend the commit to use
   the canonical `resolution_reason` short codes from `contract.md`.
3. **Restart from scratch.** Delete the existing branch, create a
   fresh one, re-implement using `contract.md` as the guide.

### Why (1) is recommended

- Existing work is well-tested and the commit message documents the
  test run as green.
- Difference vs `contract.md` is cosmetic.
- (3) wastes ~450 lines of working code for taste-level deltas.
- Solo dev memory says "do it right first time" — but it does NOT say
  "throw away done work to match a contract written hours after the
  fact."

### Decision

Pending doctor input via `/orchestrator`.
