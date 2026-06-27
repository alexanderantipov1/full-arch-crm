# Worker Prompt — ENG-224 (M-1) Move Runtime State Out Of The Repository

## Linear

- Issue: **ENG-224** — Move orchestrator session runtime state out of the repository (M-1)
- URL: https://linear.app/fusion-dental-implants/issue/ENG-224/move-orchestrator-session-runtime-state-out-of-the-repository-m-1
- Branch (create from `main`): `eduardk/eng-224-runtime-state-out-of-repo`

## Mission folder

```
.agents/orchestration/runtime-state-out-of-repo/
├── goal.md
├── acceptance.md
├── verification.md
├── contract.md            ← read this first; it specifies paths.py + ownership matrix
├── ownership.yaml
├── board.md
├── linear-sync.md
├── runtime.json
├── runlog.md
└── reports/  (write your report here when done)
```

## Required pre-flight (mandatory)

1. `git rev-parse --verify eduardk/eng-224-runtime-state-out-of-repo` —
   if the branch already exists, inspect commits before touching code
   (lesson from ENG-223).
2. Read `contract.md` end to end; it specifies the `paths.py` API and
   the file-ownership matrix that the rest of the work hangs off.
3. Re-read `.agents/orchestration/CLAUDE.md` — the "Mission Open Order"
   section landed in main `36968f9` and applies to your own runtime
   writes from now on.

## Tasks A → G (sequential)

### Task A — `paths.py` helper

- Add `.agents/skills/agent-orchestrator/scripts/paths.py`.
- Implement `runtime_root()`, `mission_runtime_dir(mission_id)`,
  `mission_spec_dir(mission_id)`, `worktree_dir(mission_id, task_id)`
  per `contract.md`.
- Env override: `FUSION_AGENT_RUNTIME_HOME` wins over default. When
  the env var is set, do NOT append `<repo-hash>` — caller is explicit.
- Default root: `~/.fusion-agent-orchestrator/<repo-hash>/` where
  `<repo-hash> = sha1(Path(repo_root).resolve())[:12]`.
- Pure stdlib. No new third-party deps.
- Add a unit test in `.agents/skills/agent-orchestrator/tests/test_paths.py`
  covering: env override exact-path, default-root construction, hash
  stability under a symlinked `repo_root`, and the four sub-dir helpers.

### Task B — `launch_worker.py` writes telemetry to local path

- Import `paths.py`; derive `mission_id` from `args.mission` basename.
- Move writes for `runtime.json`, `runlog.md`, `board.md`,
  `linear-sync.md`, `prompts/<task-id>-<sid>.md`,
  `logs/<task-id>-<sid>.log` to `mission_runtime_dir(mission_id)`.
- Keep `reports/` and the decision-artifact lookup paths under
  `mission_spec_dir(mission_id)` (which equals `args.mission`).
- Make sure `mkdir(parents=True, exist_ok=True)` covers the local
  runtime directory and `prompts/`, `logs/` subdirs.
- Update the launcher's printed paths in `--mode print` so the human
  partner sees the actual on-disk locations.

### Task C — `run_wave.py` + `status_wave.py`

- Both scripts: read/write runtime files via `paths.py` helpers.
- `status_wave.py` output should clearly show the spec path AND the
  runtime path per mission so the human partner can find both.

### Task D — Dashboard

- `.agents/dashboard/server.py` — `collect_mission()`:
  - read decision-artifact files from the repo path (current code path);
  - read `runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`,
    `prompts/`, `logs/` from `mission_runtime_dir(mission_id)`;
  - if local runtime is absent, return `runtime: null` and a clear
    `empty_state` message — don't crash.
- ENG-223 detector (`resolve_active_mission`, `find_mission_by_linear_id`):
  - keep matching by branch `ENG-\d+` → `runtime.json.sessions[]` and
    `handoffs[]`;
  - but now read each candidate mission's `runtime.json` from
    `mission_runtime_dir(<folder.name>)` instead of `<folder> / "runtime.json"`.
- Ensure existing `.agents/dashboard/tests/test_resolve_active_mission.py`
  passes (update fixture paths if needed).

### Task E — Test-suite fixture split

- `.agents/skills/agent-orchestrator/tests/conftest.py`:
  - `mission_dir` fixture splits into `mission_spec_dir` (under
    `tmp_path / "spec"`) and `runtime_dir` (under `tmp_path / "runtime"`).
  - `monkeypatch.setenv("FUSION_AGENT_RUNTIME_HOME", str(runtime_dir))`
    in each fixture that needs runtime isolation.
- Update every existing test that used `mission_dir` to take both new
  fixtures where appropriate. Existing tests must still pass.

### Task F — First-mission migration

- No active mission folder exists right now in repo (ENG-223 archived;
  this mission's runtime files are already in repo and need to be
  treated as "the migration").
- During this PR: do NOT manually move
  `.agents/orchestration/runtime-state-out-of-repo/runtime.json` etc.
  to the local path. The .gitignore rules from Task G will catch
  future writes; this mission's runtime files stay in repo for the
  duration of the PR (they were created before the rule existed).
- Document this in the worker report so the verifier doesn't flag the
  in-repo runtime files as a violation.

### Task G — `.gitignore` + docs

- `.gitignore` rules per `contract.md` §".gitignore semantics".
- Documentation updates in: `.agents/CLAUDE.md`,
  `.agents/orchestration/CLAUDE.md`,
  `.agents/skills/agent-orchestrator/SKILL.md`,
  `.agents/skills/agent-orchestrator/tests/README.md`.
- Each doc should mention the new layout (`mission_spec_dir` in repo
  vs `mission_runtime_dir` under `FUSION_AGENT_RUNTIME_HOME` /
  `~/.fusion-agent-orchestrator/<repo-hash>/`).

## Verification you must run before marking done

```bash
python3 -m py_compile .agents/dashboard/server.py
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/paths.py
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/launch_worker.py
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/run_wave.py
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/status_wave.py

.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
.venv/bin/python -m pytest .agents/dashboard/tests/ -v
```

Plus the manual smoke flow in `verification.md` §"Smoke test (manual)".

## Allowed scope (do not exceed)

See `ownership.yaml` `scope_allow` list. Forbidden: any change under
`apps/`, `packages/`, `infra/`, `.env*`, `.claude/`, `docs/`,
`.agents/orchestration/archived/`. Forbidden: new third-party deps.

## Process rules

1. **Never commit unless the human partner explicitly approves.**
2. Update `runlog.md` when you: start work, change phase, hit a
   blocker, finish, or hand off.
3. When done (or blocked), write
   `reports/ENG-224-worker-report.md` per
   `.agents/orchestration/CLAUDE.md` §"Worker Report Contract".
4. If anything in `acceptance.md` is unclear, write `Needs decision:`
   to `runlog.md` and pause — do not guess.
5. Conversation with the human partner is in Russian; everything in
   the repo stays English.
6. Honor the "Mission Open Order" rule from CLAUDE.md for any new
   mission folder you might need to spin up.

## Definition of done

- Every box in `acceptance.md` is checked with evidence.
- Worker report exists at `reports/ENG-224-worker-report.md`.
- `runlog.md` shows start + finish entries (under the new local-path
  rules from this very mission — so update via launcher, not by hand
  via repo-write).
- No file outside the allowed scope was touched.
- Tests are green locally.
- Smoke test transcript captures actual runtime files appearing under
  `FUSION_AGENT_RUNTIME_HOME` and decision artifacts staying in repo.
