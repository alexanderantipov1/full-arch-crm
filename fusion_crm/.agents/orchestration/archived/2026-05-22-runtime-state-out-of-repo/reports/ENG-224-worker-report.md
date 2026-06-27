# Worker Report — ENG-224 (M-1) Runtime State Out Of The Repository

- **Task:** ENG-224 — Move orchestrator session runtime state out of the repository (M-1)
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-224/move-orchestrator-session-runtime-state-out-of-the-repository-m-1
- **Linear status at handoff:** In Progress
- **Role / Agent:** worker / claude-code (self-execute via /orchestrator)
- **Branch:** `eduardk/eng-224-runtime-state-out-of-repo`
- **Worktree:** `.` (current checkout — worktree-as-default not yet shipped, M-2)
- **Allowed scope:** see `ownership.yaml`. Confirmed no file outside that
  scope was touched.

## Touched files

```
.agents/skills/agent-orchestrator/scripts/paths.py            (new)
.agents/skills/agent-orchestrator/scripts/launch_worker.py    (rewrite — spec/runtime split)
.agents/skills/agent-orchestrator/scripts/status_wave.py      (read runtime via paths.py)
.agents/skills/agent-orchestrator/scripts/run_wave.py         (no changes; pure wrapper)
.agents/skills/agent-orchestrator/tests/test_paths.py         (new, 10 unit tests)
.agents/skills/agent-orchestrator/tests/conftest.py           (autouse FUSION_AGENT_RUNTIME_HOME + spec/runtime alias fixtures)
.agents/skills/agent-orchestrator/tests/test_update_runtime.py (call signatures updated)
.agents/skills/agent-orchestrator/tests/README.md             (new fixture docs)
.agents/skills/agent-orchestrator/SKILL.md                    (file ownership matrix)
.agents/dashboard/server.py                                   (spec/runtime split in collect_mission, send_logs, find_mission_by_linear_id)
.agents/CLAUDE.md                                             (scope note about runtime split)
.agents/orchestration/CLAUDE.md                               (Required Mission Files updated to spec/runtime split)
.gitignore                                                    (defense-in-depth rules for runtime files)
.agents/orchestration/runtime-state-out-of-repo/*             (mission folder, this report)
```

No product code (`apps/`, `packages/`, `infra/`) touched. No `.env*`,
no PHI, no secrets, no new third-party dependencies.

## Task-by-task summary

### Task A — `paths.py` helper + unit tests ✅

- New module under `.agents/skills/agent-orchestrator/scripts/paths.py`.
- Functions: `repo_hash`, `runtime_root`, `mission_runtime_dir`,
  `mission_spec_dir`, `worktree_dir`, `mission_id_from_spec_path`.
- `FUSION_AGENT_RUNTIME_HOME` env wins; default is
  `~/.fusion-agent-orchestrator/<repo-hash>/`. When env is set, no
  `<repo-hash>` sub-dir is appended (caller is explicit).
- `<repo-hash>` = first 12 hex chars of SHA-1 over
  `Path(repo_root).resolve()` — stable under symlinks.
- 10 unit tests, all green.

### Task B — `launch_worker.py` local-path rewire ✅

- Refactored to take both `spec_dir` (from `args.mission`) and
  `runtime_dir` (derived via `paths.mission_runtime_dir`).
- `ensure_mission(spec_dir, runtime_dir)` creates both halves; decision
  artifacts go to spec, prompts/logs/reports placeholder + runtime
  files to runtime path.
- `update_runtime`, `refresh_tables` accept the two-dir split.
- `build_worker_prompt` mentions both paths so workers know where to
  look for what.
- `main()` derives `mission_id` from `args.mission.name` and uses
  `_paths.mission_runtime_dir` for runtime files.

### Task C — `run_wave.py` + `status_wave.py` ✅

- `run_wave.py` is a pure subprocess wrapper around the launcher; no
  changes required (it does not read or write runtime files directly).
- `status_wave.py` updated to read `runtime.json` from
  `mission_runtime_dir(mission_id)`; output now prints both
  `Mission spec:` and `Mission runtime:` paths so the operator can find
  both.

### Task D — Dashboard ✅

- `collect_mission()` splits file lookup: decision artifacts from
  spec, runtime files from local path. Falls back to repo path when
  local file is missing (pre-M-1 backward compat).
- `find_mission_by_linear_id()` reads `runtime.json` from
  `mission_runtime_dir(folder.name)` with the same fallback.
- `send_logs()` resolves runlog from local path with fallback.
- New snapshot field: `mission.runtime_path` (string), so UI can
  surface where the runtime data lives.
- ENG-223 detector still works: 19/19 dashboard tests green.

### Task E — Test fixture split ✅

- `_runtime_home` autouse fixture monkeypatches
  `FUSION_AGENT_RUNTIME_HOME=tmp_path` for every test, so the launcher
  writes runtime files inside `tmp_path` instead of real `$HOME`.
- `mission_dir` fixture creates `tmp_path/mission` and serves as both
  spec dir and runtime dir for the default mission. Legacy single-arg
  tests keep working.
- New `mission_spec_dir` + `runtime_dir` aliases for explicit-split
  tests.
- `test_update_runtime.py` updated to use the new 2-dir signatures
  for `update_runtime()` and `refresh_tables()`.
- All 44 + 4 skipped orchestrator tests pass.

### Task F — First-mission migration ✅ (no-op)

- ENG-223 already archived; no active mission to migrate.
- This mission's runtime files (this very folder's
  runtime.json/runlog.md/board.md/linear-sync.md) were created BEFORE
  the rule existed. Per worker prompt instructions, they stay in repo
  for this PR; they will be the last in-repo runtime files.
- After this PR merges, the next mission opened will use the new
  layout from the first runtime write.

### Task G — `.gitignore` + docs ✅

- `.gitignore` rules added (with archived/ re-includes preserved).
- `check-ignore` smoke: new accidental write to a non-archived
  mission's `runtime.json` is blocked; archived/ paths stay tracked.
- Docs updated: `.agents/CLAUDE.md`,
  `.agents/orchestration/CLAUDE.md`,
  `.agents/skills/agent-orchestrator/SKILL.md`,
  `.agents/skills/agent-orchestrator/tests/README.md`.

## Tests run

```
python3 -m py_compile .agents/dashboard/server.py                              → OK
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/paths.py      → OK
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/launch_worker.py  → OK
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/run_wave.py   → OK
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/status_wave.py → OK

.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/  → 44 passed, 4 skipped
.venv/bin/python -m pytest .agents/dashboard/tests/                  → 19 passed
```

End-to-end smoke:

```
FUSION_AGENT_RUNTIME_HOME=$(mktemp -d) \
  .venv/bin/python launch_worker.py \
    --mission $SPEC --runtime claude-code --role worker \
    --task-id SMOKE-1 --linear-id ENG-224 \
    --linear-url ... --linear-title Smoke --prompt "echo smoke" \
    --mode print

→ Spec dir got:    goal/acceptance/verification/contract/ownership/decision-log/lessons/incidents
→ Runtime dir got: runtime.json, runlog.md, board.md, linear-sync.md, prompts/SMOKE-1-*.md
```

Two dirs physically separated. ✅

## Acceptance recheck

All boxes in `acceptance.md` checked with evidence. See task-by-task
summary above.

## Risks + follow-ups

- This mission's own runtime files (runtime.json, runlog.md, board.md,
  linear-sync.md, prompts/) are committed in repo because they were
  created before this PR existed. The PR includes them so the
  decision-and-handoff trail is preserved. After this PR merges, the
  next mission will use the local-path layout from its first runtime
  write. The verifier should not flag the in-repo runtime files of
  THIS mission as a violation; the rule applies to future writes.
- Worker prompts and launcher messages now reference both paths.
  Existing workers reading their prompts will see the layout
  explanation inline.
- M-2 (worktree-as-default) is unblocked. `worktree_dir()` already
  exists in paths.py as a placeholder; M-2 will wire it into the
  launcher with the new `--workspace` flag.
- M-3 (process supervision) remains unblocked too.
- The dashboard server process the doctor is running (pid 11855 on
  port 8787 at the time of writing) is still on the OLD code. After
  this PR merges, restart the dashboard to pick up the new
  spec/runtime split rendering. The currently running dashboard will
  continue to read runtime.json from `mission_spec_dir` (in-repo);
  for this mission that still works because the runtime files were
  written in repo before the rule landed.

## Blockers / questions

None. Ready for verifier handoff.

## Suggested next task

Push branch + open PR. Verifier walks acceptance + reruns the verify
suite + smoke. Integrator (doctor) reviews + merges.

## Do-not-merge conditions

- Either test suite fails after a fresh clone + venv setup.
- E2E smoke on a fresh checkout shows runtime files landing inside
  the repo path.
- `.gitignore` rule accidentally untracks already-committed archived
  runtime files.
