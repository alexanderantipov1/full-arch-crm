# Lessons — ENG-225 (M-2) Worktree-As-Default + Self-Execute Guardrail

## When the launcher contract changes, the conftest defaults must follow

**Trigger:** Adding `--workspace worktree` as the default for `--role
worker` broke 11 existing tests and produced 8 errors during local
`pytest .agents/skills/agent-orchestrator/tests/` runs. The tests
shelled out to `launch_worker.py` with no workspace flags, so the new
default kicked in, the launcher tried to provision a real git worktree
against a `tmp_path` that wasn't a git repo, and SystemExit'd.

**Rule:** Whenever the launcher CLI grows a new flag with a non-trivial
default behavior, the hermetic test scaffolding has to follow:

1. `conftest.make_args` Namespace default mirrors the safest-hermetic
   choice for that flag (here: `workspace="self"`,
   `allow_self_execute=True`, `scope="tiny"`).
2. Tests that subprocess-invoke the launcher CLI pass the same trio
   on their argv.
3. `run_wave.py` task JSON fields that drive the launcher get a
   pass-through update too, so wave-level tests don't bypass the
   contract.

**Generalization:** New CLI flags must come with new conftest defaults
in the same PR. A green pytest run locally is the gate that catches
this — never push without it (M-1 lesson reinforced).

## File-level `# ruff: noqa: S603, S607` is the precedent for tests
that need subprocess

**Trigger:** `make verify` failed ruff S603 ("untrusted input") and
S607 ("partial executable path") on the three new test files
(`test_workspace_guardrail.py`, `test_workspace_isolation.py`,
`test_cleanup_worktrees.py`) because they invoke `git` via subprocess.

**Rule:** Tests that legitimately need `subprocess.run(["git", ...])`
or similar adopt the existing project precedent:

```python
# ruff: noqa: S603, S607
# Tests intentionally invoke `git` via subprocess against tmp repos.
```

at the top of the file, with a one-line comment explaining why. Cost
of cycle: one local `make verify` run; cheap if you actually run it
before push (M-1 lesson).

## `make verify` BEFORE push prevents CI cycle waste

**Trigger:** PR #91 was green out of the gate. PR #90 (M-1) needed
one CI cycle because I'd only run pytest locally. This PR ran `make
verify` (ruff + mypy + pytest) locally; one ruff S603/S607 cycle was
caught on the laptop and fixed before push.

**Rule:** The hard gate before push is `make verify`. Not pytest, not
py_compile — `make verify`. M-1 lessons.md said this; M-2 honored it
and saved a CI cycle. Future missions: keep doing it.
