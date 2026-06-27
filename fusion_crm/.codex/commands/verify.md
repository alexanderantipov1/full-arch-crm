---
description: Fusion CRM verify loop for Codex sessions.
---

Run the following steps in order and stop on the first failure:

1. `make lint`
2. `mypy .`
3. `make test`
4. `cd packages/db && alembic check`

Report each step as PASS or FAIL. On failure, include the first useful
error lines and do not auto-fix unless the user asks.
