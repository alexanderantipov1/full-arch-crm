---
name: "source-command-verify"
description: "Run the Fusion CRM verify loop (lint + typecheck + tests + alembic drift check)."
---

# source-command-verify

Use this skill when the user asks to run the migrated source command `verify`.

## Command Template

Run the following steps in order. Halt on the first failure and report.

1. `make lint` — ruff check (no auto-fix; we want to see what's wrong)
2. `mypy .` — strict type check (per `pyproject.toml`)
3. `make test` — `pytest -q`
4. `cd packages/db && alembic check` — verify no schema drift between models and migrations

For each step, report **PASS** or **FAIL**. On FAIL, paste the first 20 lines of error output and stop. Do **not** attempt to auto-fix — surface the failure to the user for direction.

End with a one-line summary: `verify: 4/4 PASS` or `verify: N/4 — failed at <step>`.
