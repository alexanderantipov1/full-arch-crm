---
description: Open or sync the interactive fix-lane worktree for small fixes / debugging (keeps them out of the canonical checkout).
---

Fix-lane arguments (optional): **$ARGUMENTS**

Use this when you are about to do interactive "fix here, fix there" work — small
fixes or debugging that should NOT happen in the canonical checkout (where it
collides with autonomous work on shared HEAD).

## Run it

```bash
python3 .agents/skills/agent-orchestrator/scripts/fix_lane.py          # day lane + print cd path
python3 .agents/skills/agent-orchestrator/scripts/fix_lane.py seo       # per-area lane (parallel-safe)
python3 .agents/skills/agent-orchestrator/scripts/fix_lane.py --status  # status only
python3 .agents/skills/agent-orchestrator/scripts/fix_lane.py --sync    # fast-forward onto latest origin/main
```

The lane is a worktree `../fusion-fix-lane` on branch `fix/<YYYY-MM-DD>` off
fresh `origin/main`. `cd` into the printed path, then make your fixes there.
Pass an **area label** (`seo`, `billing`, …) for a per-area lane
(`../fusion-fix-<area>`) so several debug sessions — Codex + multiple Claude
terminals — run in parallel without colliding. One lane per session, partitioned
by non-overlapping area.

## Discipline (see PARALLEL_WORK_POLICY → "The interactive fix-lane")

- Batch small logical commits in the lane; merge via the fast path.
- Track the whole session under the standing umbrella issue **ENG-537**
  (Maintenance / misc interactive fixes) — one issue per session, not per edit.
- **Smell test:** if a change touches >1 ownership area, a shared
  contract / DTO / API schema / query id / read-model meaning / metric or
  date-time semantics / PHI / audit, or needs a migration / env / deploy /
  secret change — it is NOT a tiny fix. Give it its own `normal` /
  `contract_change` ticket + worktree (and cross-runtime review for contracts).
- The script only manages the worktree/branch; it never pushes, deletes remote
  refs, deploys, or edits code.
