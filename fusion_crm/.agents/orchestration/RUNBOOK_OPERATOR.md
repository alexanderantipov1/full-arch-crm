# Operator Runbook — daily parallel-dev workflow

How to run Fusion CRM development across Codex + several Claude Code terminals
without the work colliding, and how to handle the rework/debugging phase after
autonomous Workers finish. This is the human-facing companion to
`PARALLEL_WORK_POLICY.md` (the enforcement rules) and the `/reviewer`,
`/repo-steward`, `/fix-lane` skills.

## The lifecycle of one mission

1. **Build (autonomous).** Orchestrator creates the mission + Linear issues and
   launches Workers, each in its own `git worktree`. Workers build, run focused
   verification, and leave a **draft PR + report**. They do NOT merge to `main`
   — that is the operator's call.
2. **Integrate (you, from the canonical checkout = cockpit).** This is where
   "commit / push" happens — per PR, not by hand-editing:
   - read each Worker's draft PR / report;
   - contract-changing ones get **cross-runtime review** (Codex reviews Claude's
     work and vice versa);
   - merge **one PR at a time**; when `main` advances, sync it into the other
     open worktrees;
   - `git push origin main`; `/repo-steward` (or the cron) tidies branches /
     worktrees; the `⚠ steward` statusline badge clears when clean.
3. **Review the running result (you).** The app is already up (`dev-up.sh`).
   Click through, read the pages, collect a list of "this is off, that is off."
   Do NOT fix as you go — first **triage** the findings (next section).
4. **Rework.** Run the fixes through the fix-lane (below).

## Triage: which lane does a finding belong to?

| Finding | Lane |
| --- | --- |
| Cosmetic / single-area / 1–2 files | **fix-lane**, under ENG-537 |
| Several related fixes in the feature you just built | the feature's worktree if still open; else a small follow-up task |
| Cross-cutting, contract, multi-area, needs migration/env | **new `normal` / `contract_change` task + worktree** |

## You can't always tell upfront — use tripwires

A "small fix" often turns out big mid-stream. Don't try to classify perfectly at
the start. Instead **stop the moment you cross an objective tripwire** — and make
the AGENT responsible for watching them, so it doesn't depend on operator memory:

- **3rd file / 2nd domain:** the fix touches a third file or a second domain
  package → STOP.
- **Contract tripwire (size-independent):** editing a DTO / Pydantic schema /
  API route signature / Alembic migration / env var / metric definition /
  date-time semantics / PHI / audit behavior → STOP.
- **Dependency chain:** fixing A forces changing B which forces C → it's a task.
- **Budget:** past ~3 commits or ~30 min and not done → STOP, reclassify.
- **Verify tripwire:** the fix breaks tests in another area → it's cross-cutting.

**When you hit a tripwire you do NOT lose work.** You are already in the fix-lane
with commits. Convert it: open a real Linear task, keep the fix-lane branch as
that task's branch (or cherry-pick the relevant commits into a fresh task
worktree), and continue under the full workflow with review.

Agents are instructed (CLAUDE.md / AGENTS.md / this runbook) to STOP and ask the
operator to reclassify when a tripwire fires — so the catch happens even if you
forgot to watch for it.

## Concurrency — fixes on Codex + several Claude terminals at once

One global fix-lane would collide if two agents share it. Rule: **one lane per
session, partitioned by non-overlapping area** — the same principle that keeps
big tasks from colliding.

```bash
/fix-lane seo        # -> ../fusion-fix-seo     on fix/seo-<date>
/fix-lane billing    # -> ../fusion-fix-billing on fix/billing-<date>
```

- Codex + two Claude terminals can debug in parallel **as long as they touch
  different areas / files**.
- If two fixes genuinely touch the same file, they are not independent → do them
  in one lane sequentially, or it is actually a single task.
- Codex has no slash commands — it runs
  `python3 .agents/skills/agent-orchestrator/scripts/fix_lane.py [area]`
  directly. Same lanes, same rules.

## A debug session, start to finish

```text
1. New terminal.
2. /fix-lane <area>            # isolated worktree off fresh origin/main
3. cd ../fusion-fix-<area>
4. Start ONE agent session there (Claude or Codex).
5. Give it the whole fix LIST at once: "fix A, B, C."
6. It fixes -> small commits -> all under ENG-537.
   (Agent STOPS if any fix crosses a tripwire -> you reclassify.)
7. Focused verify -> fast-path merge -> push -> /repo-steward tidies.
```

fix-lane = the *place* (isolated worktree). The agent = *who types*. One debug
session = one lane = one agent = one umbrella issue (ENG-537). Not one agent per
fix; not a new mission for a handful of small fixes.

## You don't need to remember the commands

- The fix-lane rule lives in **root `CLAUDE.md`** (every Claude session reads it)
  and **`AGENTS.md`** (every Codex session reads it) — a fresh session will
  itself propose the fix-lane when you say "fix here and there."
- Type `/fix` and let autocomplete fill `/fix-lane`; `/reviewer`, `/repo-steward`
  the same way.
- The `⚠ steward` statusline badge is a passive reminder to tidy/push.

## Command quick reference

| Goal | Command |
| --- | --- |
| Big feature with sub-tasks | Orchestrator + Workers (mission, Linear, worktrees) |
| "Where do we stand / what's unfinished" | `/reviewer` (read-only) |
| Tidy branches/worktrees, see what to push | `/repo-steward` (or the statusline badge) |
| Small fixes on the live result | `/fix-lane [area]` + one agent session, under ENG-537 |
| A fix turned out contract/multi-area | new `normal` / `contract_change` task |
| Bring the local stack up | `make up` then `./infra/scripts/dev-up.sh` |
