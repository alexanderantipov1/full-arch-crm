# Mission Goal — Worktree-As-Default For Workers + Self-Execute Guardrail (M-2)

## Linear

- Issue: ENG-225 — Worktree-as-default for workers + self-execute guardrail (M-2)
- URL: https://linear.app/fusion-dental-implants/issue/ENG-225/worktree-as-default-for-workers-self-execute-guardrail-m-2
- Status: In Progress
- Branch (suggested): `eduardk/eng-225-worktree-as-default`

## Business goal

Make parallel worker waves safe by default. Each worker gets a git
worktree under the local runtime root on its own branch, so concurrent
workers cannot stomp each other's file changes.

Constrain the orchestrator's ability to self-execute in the current
checkout. Self-execute is fine for tiny bugfixes and docs, but for
anything larger the orchestrator must explicitly justify scope so the
decision is auditable.

## Why now

Today `launch_worker.py --worktree` defaults to the repository root.
We have been running sequentially, so the failure mode has not
materialized. Once parallel waves are used seriously (the entire point
of orchestrator), it's a guaranteed stomp. M-1 (ENG-224) landed the
`paths.worktree_dir()` placeholder; this mission wires it in.

## Expected outcome

1. New flag `--workspace worktree|self`; default for `--role worker`
   is `worktree`, for verifier/integrator is `self`.
2. With `worktree`, the launcher creates `git worktree add
   <worktree_dir(mission_id, task_id)> -b <linear-id>-<task-id>
   <branch-base>` and runs the worker there.
3. `--workspace self` requires `--allow-self-execute`, otherwise the
   launcher refuses.
4. Even with `--allow-self-execute`, the launcher refuses when
   prompt > 5000 chars OR `--scope` is missing/`none`. Forces the
   orchestrator to make a blast-radius decision per launch.
5. `cleanup_worktrees.py` prunes worktree directories whose linked
   branch is merged or whose mission is archived (default `--dry-run`,
   explicit `--apply` to act).

## Out of scope

- Process supervision / `worker_ctl.py` (M-3 mission).
- Cross-platform PID semantics (M-3 mission).
- Retroactive worktree migration of archived missions.

## Constraints

- Worktree paths live outside the repo (under `runtime_root()` from
  M-1). They do not appear in `git status` of the canonical checkout.
- The launcher must not delete a worktree it did not create.
  `cleanup_worktrees.py` is the only path to deletion; it requires
  explicit confirmation per item.
- Linear gate stays.
- Repository files in English. No PHI. No secrets. No `.env*`.
- No new third-party dependencies.
- No product code changes.
