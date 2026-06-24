# Acceptance Criteria — ENG-224 (M-1)

A — `paths.py` helper exists
- [ ] New module `.agents/skills/agent-orchestrator/scripts/paths.py`.
- [ ] Functions: `runtime_root()`, `mission_runtime_dir(mission_id)`,
      `mission_spec_dir(mission_id)`, `worktree_dir(mission_id, task_id)`.
- [ ] `runtime_root()` honors env `FUSION_AGENT_RUNTIME_HOME` (highest
      priority), then `~/.fusion-agent-orchestrator/<repo-hash>/`.
- [ ] `<repo-hash>` is a stable SHA over `Path(repo_root).resolve()`
      (not the raw symlink path).
- [ ] Module is pure stdlib; no new dependencies.

B — `launch_worker.py` writes runtime telemetry to the local path
- [ ] `runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`,
      `prompts/<task-id>-<sid>.md`, `logs/<task-id>-<sid>.log` are
      written under `mission_runtime_dir(mission_id)`.
- [ ] Decision-artifact paths (`goal.md`, `acceptance.md`, etc.) and
      `reports/<task-id>-worker-report.md` continue to use the repo
      mission folder (`mission_spec_dir(mission_id)`).
- [ ] CLI flag `--mission` still accepts a path; the launcher derives
      `mission_id` from that path's basename so existing call sites
      keep working.

C — `run_wave.py` + `status_wave.py` follow the new layout
- [ ] Both scripts read/write runtime files via `paths.py` helpers.
- [ ] `status_wave.py` prints both the repo decision-artifact path
      and the local-runtime path for each mission.

D — Dashboard updated
- [ ] `.agents/dashboard/server.py` snapshot endpoint merges repo
      decision artifacts (`collect_mission`) with local-path runtime
      state (`runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`).
- [ ] ENG-223 detector keeps working: still resolves the active
      mission folder by `ENG-\d+` from branch matched against the
      Linear ids in `runtime.json.sessions[]` and `handoffs[]` — but
      now reads `runtime.json` from the local path.
- [ ] If a mission has decision artifacts in repo but no local
      runtime yet, snapshot returns the spec view with
      `runtime: null` and a clear empty-state message instead of
      crashing.

E — Tests
- [ ] `conftest.py` `mission_dir` fixture splits into
      `mission_spec_dir` (under `tmp_path`) and
      `runtime_dir` (under `tmp_path`, with
      `monkeypatch.setenv("FUSION_AGENT_RUNTIME_HOME", str(tmp_path))`).
- [ ] All existing tests pass against the new layout (no test touches
      a real `$HOME`).
- [ ] New unit test for `paths.py` covering: env override, default
      root, hash stability under symlinks, mission/runtime/worktree
      sub-dir construction.

F — First-mission migration
- [ ] No active mission folder is sitting in repo at PR open time
      (ENG-223's `dashboard-auto-track` already archived). The next
      mission opened after this PR lands MUST use the new local-path
      layout from the very first runtime write.
- [ ] No retroactive migration of archived missions.

G — Docs + .gitignore
- [ ] `.gitignore` adds belt-and-braces rules so accidental local
      writes do not leak: `.agents/orchestration/*/runtime.json`,
      `.agents/orchestration/*/runlog.md`,
      `.agents/orchestration/*/board.md`,
      `.agents/orchestration/*/linear-sync.md`,
      `.agents/orchestration/*/prompts/`,
      `.agents/orchestration/*/logs/`.
      Exception: keep archived/ paths matchable so historical state
      stays committed (use `!archived/` re-include patterns or scope
      ignores to non-archived siblings).
- [ ] `.agents/CLAUDE.md`, `.agents/orchestration/CLAUDE.md`,
      `.agents/orchestration/AGENTS.md`,
      `.agents/skills/agent-orchestrator/SKILL.md`, and
      `.agents/skills/agent-orchestrator/tests/README.md` reference
      the new layout.

Hygiene
- [ ] Repository files in English.
- [ ] No PHI, no secrets, no `.env*` reads under the new local path.
- [ ] No new third-party dependencies.
- [ ] No product-code changes (`apps/`, `packages/`, `infra/`).
