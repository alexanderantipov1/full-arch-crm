# Worker Prompt — ENG-225 (M-2) Worktree-As-Default + Self-Execute Guardrail

## Linear

- Issue: **ENG-225** — Worktree-as-default for workers + self-execute guardrail (M-2)
- URL: https://linear.app/fusion-dental-implants/issue/ENG-225/worktree-as-default-for-workers-self-execute-guardrail-m-2
- Branch (create from `main`): `eduardk/eng-225-worktree-as-default`

## Mission folder

```
.agents/orchestration/worktree-as-default/
├── goal.md
├── acceptance.md
├── verification.md
├── contract.md            ← read this first; specifies argparse + cleanup CLI + scope marker shape
├── ownership.yaml
├── board.md
├── linear-sync.md
├── runtime.json           ← lives under runtime path now (M-1)
├── runlog.md              ← lives under runtime path now (M-1)
└── reports/  (write your report here when done)
```

## Required pre-flight (mandatory)

1. `git rev-parse --verify eduardk/eng-225-worktree-as-default` — if
   exists, inspect commits before touching code (M-1 lesson).
2. Read `contract.md` end to end; it specifies the argparse surface,
   worktree provisioning flow, self-execute guardrail flow, scope
   marker shape, and `cleanup_worktrees.py` CLI.
3. Re-read the "Mission Open Order" section in
   `.agents/orchestration/CLAUDE.md` — applies to any new mission you
   might need to open during this work.

## Tasks A → F (sequential)

### Task A — `paths.worktree_dir()` confirmation

- The helper exists from M-1. Confirm signature: `worktree_dir(mission_id, task_id, repo_root=None) -> Path`.
- Add one positive case to `test_paths.py` — already covered, but
  extend to assert the worktree path is under `mission_runtime_dir`
  (i.e. honors `FUSION_AGENT_RUNTIME_HOME`).

### Task B — Launcher argparse additions

- `--workspace worktree|self`
- `--allow-self-execute` (store_true)
- `--scope tiny|bugfix|docs|none` (no implicit default for self mode)
- `--branch-base` (default `main`)
- Default workspace resolution in `main()`: `worker` → `worktree`,
  `verifier`/`integrator` → `self`.

### Task C — Worktree provisioning

- Pre-flight: `--branch-base` working tree clean check. Use
  `git diff --quiet` + `git diff --cached --quiet` against the base
  branch; on dirty exit SystemExit with paths from `git status --short`.
- Branch name: `<linear-id-lower>-<task-id-lower>`. If exists, append
  `-<session_id[:6]>`.
- `git worktree add <wt_path> -b <branch> <branch-base>`.
- Set worker subprocess's `cwd` to the new worktree path.

### Task D — Self-execute guardrail

- Refuse `--workspace self` without `--allow-self-execute`.
- Refuse with prompt > 5000 chars even when `--allow-self-execute`.
- Refuse without `--scope tiny|bugfix|docs` (also reject
  `--scope none`).
- On success: append `Scope: <value>` marker to runlog AND a
  multi-line entry to `decision-log.md` (see contract.md for exact
  format).

### Task E — `cleanup_worktrees.py`

- New script at
  `.agents/skills/agent-orchestrator/scripts/cleanup_worktrees.py`.
- See `contract.md` §"`cleanup_worktrees.py` semantics" for the full
  CLI surface.
- Default mode: dry-run. `--apply` requires per-item `y/N`. `--force`
  permits unmerged deletion with a second confirmation, still gated
  behind `--apply`.

### Task F — Tests + docs

- Unit tests for the new argparse rules: workspace × allow-self-execute
  truth table; 5 explicit rejection cases for guardrail.
- Integration test in `test_workspace_isolation.py`:
  - Build two fake-shim workers via `run_wave.py` with `--workspace
    worktree`.
  - After both finish, assert that Worker 1's worktree contains a
    sentinel file that Worker 2's worktree does not (and vice versa).
  - Assert the canonical repo working tree was not modified.
- `cleanup_worktrees.py` unit + integration tests covering:
  - Dry-run finds eligible candidates (mission archived + branch
    merged).
  - Apply removes them when confirmation is `y`.
  - Skips when confirmation is `N`.
  - Refuses unmerged candidates without `--force`.
- Doc updates in `.agents/orchestration/CLAUDE.md`, `SKILL.md`,
  `tests/README.md`.

## Allowed scope (do not exceed)

See `ownership.yaml` `scope_allow`. Forbidden: any product code,
`.env*`, `.claude/`, `docs/`, `.agents/orchestration/archived/`, AND
`.agents/dashboard/` (M-2 should not need dashboard changes).

## Verification you must run BEFORE push (M-1 lesson)

```bash
make verify   # ruff + mypy + pytest — DO NOT SKIP
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
.venv/bin/python -m pytest .agents/dashboard/tests/ -v
```

Plus the manual smoke flow in `verification.md` §"Smoke test (manual)"
(6 cases).

## Process rules

1. **Never commit unless the human partner explicitly approves.**
2. Update `runlog.md` when you: start work, change phase, hit a
   blocker, finish, or hand off.
3. When done (or blocked), write
   `reports/ENG-225-worker-report.md` per
   `.agents/orchestration/CLAUDE.md` §"Worker Report Contract".
4. If anything in `acceptance.md` is unclear, write `Needs decision:`
   to `runlog.md` and pause — do not guess.
5. Conversation with the human partner is in Russian; everything in
   the repo stays English.
6. **Pre-push gate:** run `make verify`. If it fails locally, fix
   before push. Saving the CI cycle is faster than failing in CI.

## Definition of done

- Every box in `acceptance.md` is checked with evidence.
- Worker report exists at `reports/ENG-225-worker-report.md`.
- `runlog.md` shows start + finish entries.
- No file outside the allowed scope was touched.
- `make verify` is green locally.
- Integration test demonstrably proves two parallel workers do NOT
  stomp each other.
