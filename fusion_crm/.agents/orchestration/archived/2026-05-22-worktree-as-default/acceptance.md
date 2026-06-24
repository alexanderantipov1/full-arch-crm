# Acceptance Criteria — ENG-225 (M-2)

A — `paths.worktree_dir()` confirmed
- [ ] Existing helper returns `<runtime_root>/<mission_id>/worktrees/<task_id>/`.
- [ ] New unit test in `test_paths.py` exercises this layout under
      `FUSION_AGENT_RUNTIME_HOME=tmp_path`.

B — Launcher argparse additions
- [ ] `--workspace worktree|self` — choices enforced.
- [ ] `--allow-self-execute` — store_true, default False.
- [ ] `--scope tiny|bugfix|docs|none` — choices enforced; no implicit
      default (orchestrator must pass it when self-executing).
- [ ] `--branch-base <branch>` — default `main`.
- [ ] Default for `--workspace`:
      - `--role worker` → `worktree`
      - `--role verifier` / `--role integrator` → `self`

C — Worktree provisioning
- [ ] When `--workspace worktree`, the launcher pre-flights the working
      tree on `--branch-base`:
      - If dirty → SystemExit with a clear error message naming dirty
        paths (e.g. "main has uncommitted changes in apps/web/page.tsx;
        stash or commit first").
- [ ] Creates a fresh branch `<linear-id>-<task-id>` from
      `--branch-base` via `git worktree add`.
- [ ] If that branch already exists, appends `-<session_id>` suffix
      and re-tries.
- [ ] Sets the worker subprocess's `cwd` to the new worktree path.

D — Self-execute guardrail
- [ ] `--workspace self` without `--allow-self-execute` → SystemExit
      with explicit message naming what's missing.
- [ ] `--workspace self --allow-self-execute` with prompt > 5000 chars
      → SystemExit explaining the threshold and why.
- [ ] `--workspace self --allow-self-execute` without `--scope` (or
      `--scope none` without justification) → SystemExit.
- [ ] On successful self-execute: orchestrator's `runlog.md` gets a
      `Scope: <value>` marker line; `decision-log.md` gets an entry
      naming the chosen scope + reason + Linear id + timestamp.

E — `cleanup_worktrees.py` helper
- [ ] New script at `.agents/skills/agent-orchestrator/scripts/cleanup_worktrees.py`.
- [ ] Walks `runtime_root()` recursively to find `worktrees/<task-id>/`.
- [ ] For each candidate, determines:
      - Is the linked branch merged into `main`? (via
        `git branch --merged main` or `git merge-base --is-ancestor`)
      - Is the mission archived? (folder under
        `.agents/orchestration/archived/`)
- [ ] `--dry-run` default — prints prune candidates and reasons; no
      filesystem changes.
- [ ] `--apply` mode requires per-item confirmation (`y/N`) before
      `git worktree remove <path>`.
- [ ] Will not remove a worktree whose branch has unmerged commits
      unless `--force` is also passed (which prompts a second
      confirmation).

F — Tests + docs
- [ ] Argparse unit tests (workspace × allow-self-execute matrix; the
      five rejection cases for self-execute guardrail).
- [ ] Integration test: spin two parallel workers via `run_wave.py`
      with `--workspace worktree` against fake `codex` shim.
      - Each worker's worktree must be on a distinct branch.
      - A file edit made by Worker 1 must NOT appear in Worker 2's
        checkout.
      - The canonical repo's working tree must NOT be touched by
        either worker.
- [ ] `cleanup_worktrees.py` unit + integration tests covering:
      `--dry-run` lists merged candidates; `--apply` removes them with
      mocked confirmation input; unmerged candidates are skipped
      without `--force`.
- [ ] Doc updates land:
      - `.agents/orchestration/CLAUDE.md` — new workspace + scope flags
      - `.agents/skills/agent-orchestrator/SKILL.md` — launcher flag
        surface and cleanup script
      - `.agents/skills/agent-orchestrator/tests/README.md` — new
        fixtures

Hygiene
- [ ] Repository files in English.
- [ ] No PHI, no secrets, no `.env*` reads.
- [ ] No new third-party dependencies.
- [ ] No product-code changes.
- [ ] `make verify` is green locally BEFORE push (M-1 lesson).
