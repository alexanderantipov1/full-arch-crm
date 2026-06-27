# Worker Report — ENG-225 (M-2) Worktree-As-Default + Self-Execute Guardrail

- **Task:** ENG-225 — Worktree-as-default for workers + self-execute guardrail (M-2)
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-225/worktree-as-default-for-workers-self-execute-guardrail-m-2
- **Linear status at handoff:** In Progress
- **Role / Agent:** worker / claude-code (self-execute via /orchestrator)
- **Branch:** `eduardk/eng-225-worktree-as-default`
- **Worktree:** `.` (current checkout — worktree-as-default not yet
  on main when this work began; the irony is captured in the M-2
  meta-commit message)
- **Allowed scope:** per `ownership.yaml`. Confirmed no file outside
  scope was touched. No product code, no `.env*`, no archived missions.

## Touched files

```
.agents/skills/agent-orchestrator/scripts/launch_worker.py      (M-2 argparse + worktree + guardrail)
.agents/skills/agent-orchestrator/scripts/cleanup_worktrees.py  (new — prune helper)
.agents/skills/agent-orchestrator/scripts/run_wave.py           (pass-through M-2 fields)
.agents/skills/agent-orchestrator/tests/test_paths.py            (+1 nesting invariant test)
.agents/skills/agent-orchestrator/tests/test_workspace_guardrail.py  (new — 12 unit tests)
.agents/skills/agent-orchestrator/tests/test_workspace_isolation.py  (new — 4 integration tests)
.agents/skills/agent-orchestrator/tests/test_cleanup_worktrees.py    (new — 9 unit tests)
.agents/skills/agent-orchestrator/tests/test_runtime_json_schema.py  (add workspace=self to launcher invocation)
.agents/skills/agent-orchestrator/tests/test_background_survival.py  (add workspace=self to launcher invocation)
.agents/skills/agent-orchestrator/tests/test_linear_gate.py          (add workspace=self to launcher invocation)
.agents/skills/agent-orchestrator/tests/test_sighup_resilience.py    (add workspace=self to launcher invocations)
.agents/skills/agent-orchestrator/tests/test_wave_wrappers.py        (add workspace=self to task JSON)
.agents/skills/agent-orchestrator/tests/conftest.py                  (make_args defaults to workspace=self for hermetic tests)
.agents/orchestration/CLAUDE.md                                      (Workspace Isolation section)
.agents/skills/agent-orchestrator/SKILL.md                           (workspace + cleanup CLI docs)
.agents/skills/agent-orchestrator/tests/README.md                    (new fixture docs)
.agents/orchestration/worktree-as-default/*                          (mission folder, this report)
```

## Task-by-task summary

### Task A — `paths.worktree_dir()` confirmation ✅

Helper already shipped in M-1; added one positive test that asserts
`worktree_dir(mission_id, task_id)` nests under
`mission_runtime_dir(mission_id)` (compositional invariant).

### Task B — Launcher argparse additions ✅

Added 4 new flags: `--workspace worktree|self`, `--allow-self-execute`,
`--scope tiny|bugfix|docs|none`, `--branch-base` (default `main`).
Helper `_resolve_default_workspace(role)` returns `worktree` for
`worker`, `self` for `verifier`/`integrator`.

### Task C — Worktree provisioning + dirty-base preflight ✅

`_preflight_clean_base()` runs `git status --porcelain` and SystemExits
on dirty trees, listing up to 5 dirty paths.

`_provision_worktree()` creates the branch (with `-<sid[:6]>` suffix
on collision) and `git worktree add`s under
`paths.worktree_dir(mission_id, task_id)`. Sets `args.worktree` and
`args.branch` for downstream uses.

### Task D — Self-execute guardrail ✅

`_enforce_self_execute_guardrail()` enforces three preconditions:
- `--allow-self-execute` present
- prompt ≤ 5000 chars
- `--scope` ∈ {tiny, bugfix, docs} (not `none`)

`_record_scope_marker()` appends a structured `## YYYY-MM-DDTHH:MM:SSZ
— Scope: <value>` block to `decision-log.md` with Linear id, prompt
size, reason, and a certification statement.

The launcher's runlog also picks up a `scope` marker line:
`- TS | orchestrator | TASK-X | scope | Scope: bugfix (...)`.

### Task E — `cleanup_worktrees.py` helper ✅

Walks `_paths.runtime_root()` looking for `<mission>/worktrees/<task>/`
directories. `classify()` computes eligibility:
- Mission archived AND branch merged into `main` → eligible.
- Mission archived, branch unmerged → eligible-with-force.
- Otherwise → skip.

Default mode is dry-run. `--apply` requires per-item `y/N`
confirmation. `--force` permits unmerged-branch removal with a second
confirmation per item. Exit codes: `0` success, `2` guardrail, `3`
git failure, `4` user declined.

### Task F — Tests + docs ✅

- **test_paths.py:** +1 nesting invariant test (11 total).
- **test_workspace_guardrail.py:** 12 tests — workspace defaults,
  five rejection cases, two acceptance paths, decision-log writer,
  preflight clean / dirty cases.
- **test_workspace_isolation.py:** 4 integration tests on a real
  `git init` tmp repo — distinct branches, no file bleed, collision
  suffix, dirty-base refusal.
- **test_cleanup_worktrees.py:** 9 tests — list_worktrees, archived
  matching, dry-run no-removal, force-without-apply guardrail, accept
  / decline confirmation flows, unmerged skip, force-removes-unmerged
  with two confirmations.
- **Existing test fixes:** `conftest.make_args` defaults to
  `workspace=self + allow_self_execute=True + scope=tiny` so legacy
  tests don't trigger worktree provisioning against tmp_path. CLI
  invocations in test_runtime_json_schema / test_background_survival /
  test_linear_gate / test_sighup_resilience now pass the safety triple
  on the command line. Wave task JSONs in test_wave_wrappers pass
  them as task-dict fields; `run_wave.build_args` propagates them.
- **Docs:** new "Workspace Isolation" section in
  `.agents/orchestration/CLAUDE.md`; new "Workspace flags" block in
  `SKILL.md`; new fixtures + integration notes in `tests/README.md`.

## Tests run

```
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/  → 70 passed, 4 skipped
.venv/bin/python -m pytest .agents/dashboard/tests/                  → 19 passed
make verify                                                          → ruff ✓ mypy ✓ pytest 25 passed
```

`make verify` was run BEFORE this report was written (M-1 lesson — do
NOT push without running it). One ruff cycle was wasted because the
new test files needed `# ruff: noqa: S603, S607` at the top to match
the precedent set by existing subprocess-using tests; fixed in-place
before this report.

## Acceptance recheck

All boxes in `acceptance.md` checked with evidence in the task
summary above. The pivotal acceptance criterion — "two parallel
workers via run_wave.py get isolated worktrees on different branches;
file edits don't bleed between them" — is proven by
`test_file_edits_do_not_bleed_between_worktrees`.

## Risks + follow-ups

- The legacy `--worktree <path>` arg still exists in argparse for
  manual overrides. After M-2 ships, callers passing only `--worktree`
  will get the default `worktree` workspace and provision a brand-new
  one ignoring their path. This is technically a behavior change;
  no call site in repo or wave-test uses this legacy combo, so the
  silent default-takes-over is acceptable. Could be tightened in M-3
  to refuse the conflict with a clear error.
- The integration test depends on `git` being on PATH in the test
  environment. If absent, the four isolation tests fail. CI has git;
  hosts without it would be a setup issue, not a regression. No
  env-gating added (mirrors how M-1 didn't gate `git rev-parse`
  usage in the dashboard detector tests).
- M-3 (process supervision) is now unblocked. `worker_ctl.py` will
  need to know which worker is in a worktree vs a self-execute (so
  --kill can clean up worktrees from killed runs). The session record
  in runtime.json already carries `worktree` field; M-3 reads it.

## Blockers / questions

None. Ready for verifier handoff.

## Suggested next task

Open PR. Verifier walks acceptance + reruns make verify + skill suite
+ dashboard suite. Integrator (human) reviews + merges.

## Do-not-merge conditions

- `make verify` fails on a fresh clone.
- Two-parallel-worker isolation test regresses.
- A test inadvertently triggers worktree provisioning against a
  non-git tmp_path (would show up as 8 errors in test_runtime_json_schema
  again — same as the regression caught during this work).
