# AGENTS.md — Fusion CRM platform (Codex entry point)

This repository already keeps its authoritative project rules in
`CLAUDE.md` files. For Codex sessions, treat those files as
first-class repository policy.

Before editing:

1. Read the root `CLAUDE.md`.
2. If you are touching `apps/`, `packages/`, `infra/`, or a
   documented integration area, read the local `CLAUDE.md` there too.
3. If `AGENTS.md` and `CLAUDE.md` ever diverge, follow the stricter
   rule and update both files together.

Non-negotiable reminders for Codex work in this repo:

- Conversation with the user is in Russian.
- Everything written into the repository is in English.
- Respect all hard architectural invariants from `CLAUDE.md`.
- Do not edit `.env*` or shipped Alembic revisions.
- Do not commit, push, or run destructive commands without explicit
  user approval.
- Before changing deployment, env vars, secrets, OAuth/CORS URLs,
  Cloud Run services/jobs, deploy scripts, or GitHub Actions deploy
  workflow, read and follow `docs/DEPLOYMENT_RULES.md`.
- For the environments / permission model (local needs no approval but
  must be signalled; production = merge-to-`main` = deploy, explicit
  per-session approval) and parallel-agent isolation, see
  `docs/DEV_WORKFLOW.md`.

Codex workflow for this repo:

- For non-trivial work, surface the plan before structural changes.
- Interactive small fixes / debugging go in the fix-lane, never the canonical
  checkout. Codex has no slash commands — run the script directly:
  `python3 .agents/skills/agent-orchestrator/scripts/fix_lane.py [area]` for an
  isolated worktree (per-area label enables parallel lanes). Track the session
  under standing umbrella issue `ENG-537`. The moment a fix crosses a tripwire
  (3rd file, 2nd domain, shared contract/DTO/schema/migration/env/metric/
  date-time/PHI/audit, or a dependency chain) STOP and reclassify as a
  `normal`/`contract_change` task. See
  `.agents/orchestration/PARALLEL_WORK_POLICY.md` → "The interactive fix-lane"
  and `.agents/orchestration/RUNBOOK_OPERATOR.md`.
- Repo hygiene check (Codex has no configurable statusline like Claude Code's
  `⚠ steward` badge — so do it on demand). At session start, and again before
  any merge/push, run:
  `python3 .agents/skills/repo-steward/scripts/steward.py --json --no-drift`
  If it reports unpushed commits (`ahead`), local auto-deletable merged branches
  (`local_deletable`), or a non-empty `queue`, say so in your first reply and
  recommend `/repo-steward` (operator runs irreversible items). Do NOT push or
  delete remote branches yourself — that needs explicit operator approval.
- Use the same verify loop documented for Claude:
  - `make lint`
  - `mypy .`
  - `make test`
  - `cd packages/db && alembic check`
- When a new area needs local instructions, add both `CLAUDE.md` and
  `AGENTS.md`.

See `CLAUDE.md` for the full policy and architecture context.
