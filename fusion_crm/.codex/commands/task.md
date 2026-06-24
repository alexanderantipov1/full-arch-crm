---
description: Plan-then-execute workflow for non-trivial changes in Fusion CRM.
---

For the user's request: **$ARGUMENTS**

Follow this sequence:

1. Restate the goal in one sentence.
2. List the files you expect to touch.
3. Identify the architectural invariants from `CLAUDE.md` that apply.
4. Check whether the area has a local `CLAUDE.md` or `AGENTS.md` and
   surface any extra constraints.
5. Flag risky paths up front:
   - `.env*`
   - `packages/db/alembic/versions/*`
   - destructive commands
6. Present the plan before structural changes.
7. After implementation, run `.codex/commands/verify.md`.
8. Stop without committing unless the user explicitly asks.
