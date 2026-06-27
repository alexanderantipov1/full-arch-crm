---
description: Plan-then-execute workflow for non-trivial changes. Enforces propose-before-implement and verify-before-commit per CLAUDE.md.
---

For the user's request: **$ARGUMENTS**

Follow this exact sequence. Do not skip steps.

### 1. Plan (no code yet)

- Restate the goal in one sentence.
- List the files you intend to touch.
- Identify which **hard architectural invariants** from `CLAUDE.md` apply (cross-domain imports, PHI gating, audit append-only, immutable migrations, no DB in routes, etc.).
- Flag any paths or commands that fall under the deny-list in `.claude/settings.json` (e.g. `packages/db/alembic/versions/*`, `.env*`, `alembic downgrade`).
- If a sub-area `CLAUDE.md` exists for the area being touched (e.g. `apps/api/CLAUDE.md`, `infra/CLAUDE.md`), read it and surface its constraints.

### 2. Pause and confirm

Present the plan. **Wait for explicit user approval** before writing any code. If the user requests changes, revise and re-present.

### 3. Execute the approved plan

Implement step by step. Stop at the first ambiguity rather than guess.

### 4. Verify

Run `/verify`. If any step fails, present the failure and propose a fix — do **not** auto-retry without user direction.

### 5. Stop without committing

Show the resulting diff (`git diff`) and ask whether the user wants to commit. Per `CLAUDE.md`: never commit unless the user explicitly asks.

### Refuse-to-proceed conditions

If the request requires:
- Editing a merged Alembic migration → propose a new revision instead.
- `UPDATE` or `DELETE` on `audit.access_log` → refuse and explain the append-only invariant.
- Cross-domain import (e.g. `ops` importing `phi`) → refuse and propose service-layer mediation.
- Touching `.env*` → refuse and instruct the user to edit by hand.
