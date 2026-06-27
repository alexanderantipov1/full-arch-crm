# Lessons — ENG-224 (M-1) Runtime State Out Of The Repository

## Run `make verify` locally before pushing, not just `pytest`

**Trigger:** PR #90 first CI run failed on ruff `S324` (insecure hash —
sha1) in `paths.py:32`. Local verification had run `python3 -m
py_compile` + `pytest .agents/...` + `pytest .agents/dashboard/tests/`
but skipped `make verify` (which also runs `ruff check .` and `mypy`).
Burned one CI cycle to learn it.

**Rule:** Before any `git push` on a worker branch, always run the full
`make verify` (or its CI-mirror equivalent). Pytest does not catch lint
or type errors.

**Generalization:** "Tests passing" ≠ "CI will pass". CI is a superset
of pytest. Worker prompts and the verification.md template should list
the full `make verify` command explicitly, not just the pytest
invocation.

## When opening a mission, the gitignore rules from THIS mission affect
THIS mission

**Trigger:** After `make verify` and pytest passed, `git add
.agents/orchestration/runtime-state-out-of-repo/` silently dropped this
mission's own `runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`,
and `prompts/` — the `.gitignore` rules added by this same PR blocked
them.

**Resolution:** The PR description called this out explicitly so the
verifier understood the orchestration trail lives in the worker report
plus this `lessons.md`, not in the runtime telemetry.

**Rule:** When a PR changes `.gitignore`, run `git add` against a dry
target (`git add --dry-run`) or `git check-ignore` to confirm intent
before the final commit. Don't be surprised when your own rule applies
to your own files.

## paths.py is the primary enforcement; .gitignore is defense in depth

**Trigger:** Worker prompt and contract.md both say "paths.py is the
primary layer; .gitignore is defense in depth". CI failure flagged the
sha1 usage in paths.py — the primary layer's correctness matters more
than the .gitignore catching mistakes.

**Rule:** Treat the helper module (paths.py) as the load-bearing
contract. Tests cover its behavior. .gitignore is the safety net for
when the helper is bypassed, not the primary mechanism.
