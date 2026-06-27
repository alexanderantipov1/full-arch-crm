# Mission Goal — Move Orchestrator Session Runtime State Out Of The Repository

## Linear

- Issue: ENG-224 — Move orchestrator session runtime state out of the repository (M-1)
- URL: https://linear.app/fusion-dental-implants/issue/ENG-224/move-orchestrator-session-runtime-state-out-of-the-repository-m-1
- Status: In Progress
- Branch (suggested): `eduardk/eng-224-runtime-state-out-of-repo`

## Business goal

Repository keeps only durable mission records — goal/acceptance/contract/
ownership/decision-log/lessons/incidents/reports. Session ephemera
(`runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`, `prompts/`,
`logs/`) live in `~/.fusion-agent-orchestrator/<repo-hash>/<mission-id>/`.

PR #78 added 30+ mission session files to git history; this PR ENG-224
stops the bleed before it grows quadratically with future
mission × worker counts.

## Why now

- ENG-223 archive commit (`237151f`) demonstrated that mission-folder
  churn already pollutes `git log`.
- Two follow-on missions in the strategy queue (M-2 worktree-as-default,
  M-3 process supervision) are explicitly blocked on this layout.
- Cheap retrofit at one mission of churn vs five.

## Expected outcome

1. `launch_worker.py` writes runtime telemetry to local path
   (`~/.fusion-agent-orchestrator/<repo-hash>/<mission-id>/`).
2. `run_wave.py` and `status_wave.py` follow the new layout.
3. Dashboard `/api/snapshot` merges repo decision artifacts with local
   runtime state (and the ENG-223 detector keeps working).
4. `paths.py` centralises path resolution.
5. Test suite splits `mission_dir` → `mission_spec_dir` (repo, tmp)
   + `runtime_dir` (tmp, monkeypatched `FUSION_AGENT_RUNTIME_HOME`).
6. `.gitignore` adds defense-in-depth rules so stray local writes do
   not leak into git history.
7. Documentation updated.

## Out of scope

- Worktree-as-default (M-2 mission).
- Process supervision / `worker_ctl.py` (M-3 mission).
- Retroactive migration of archived missions — they stay as historical
  snapshots in repo.

## Constraints

- No PHI, no secrets, no `.env*` reads under the new local path.
- Dashboard remains read-only.
- Linear gate stays.
- Tests use `tmp_path` for both `mission_spec_dir` and `runtime_dir`;
  never touch real `$HOME`.
- No new third-party dependencies.
- Repository files in English.
