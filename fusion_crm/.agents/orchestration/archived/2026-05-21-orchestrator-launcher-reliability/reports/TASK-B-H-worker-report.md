# TASK-B–H Worker Report — Test harness + docs pass

- **Tasks:** TASK-B, TASK-C, TASK-D, TASK-E, TASK-F, TASK-G, TASK-H
- **Linear:** ENG-213
- **Role / agent:** worker / claude-code
- **Worker session id:** fded8732ee93
- **Branch:** main
- **Mode:** in-session sequential per human decision Y

## Files created

### Tests skeleton

- `.agents/skills/agent-orchestrator/tests/__init__.py`
- `.agents/skills/agent-orchestrator/tests/conftest.py` — fixtures: `launcher_module`,
  `mission_dir`, `make_args`, `fake_runtime_dir`, `fake_runtime_path`,
  `launcher_subprocess_env`; custom-mark registration; env-gated skip logic for
  contract-drift tests.

### TASK-B — unit tests (16 cases)

- `test_build_command.py` — 6 tests covering codex flag surface (no
  `--ask-for-approval`, opt-in bypass), `--sandbox` pass-through, claude-code
  shape, unknown runtime rejection, resolved-worktree `--cd`.
- `test_build_worker_prompt.py` — 3 tests covering required fields, mission
  runtime file mentions, role substitution.
- `test_update_runtime.py` — 4 tests covering required session keys, session
  dedup by id, handoff append shape, `refresh_tables()` board/linear-sync
  rendering.
- `test_linear_gate.py` — 3 subprocess tests asserting non-zero exit on
  empty `--linear-id` / `--linear-url`, zero exit on valid invocation.

### TASK-C — background-launch survival (5 cases)

- `test_background_survival.py`:
  - parametrized survival check for codex + claude-code: launcher exit then
    `SHIM_END` appears in log.
  - parametrized `ppid=1` check confirming `start_new_session` worked.
  - `runtime.json` post-launch contains `pid`, `status=running`,
    `launch_mode=background`.

### TASK-D — SIGHUP regression guard (2 cases)

- `test_sighup_resilience.py`:
  - launcher run inside a `bash -c` subshell; subshell exits; worker
    continues to write `SHIM_END`; log contains `ppid=1`.
  - log size grows between launcher exit and worker shim completion.

### TASK-E — contract drift (4 cases, env-gated)

- `test_contract_drift.py` (marks `codex_contract`, `claude_contract`):
  - codex `exec` keeps `--cd`, `--sandbox`.
  - codex `exec` does NOT have `--ask-for-approval`.
  - codex `exec` has `--dangerously-bypass-approvals-and-sandbox`.
  - claude has `-p` / `--permission-mode`.
  - Skipped cleanly when env vars absent; passes when set.

### TASK-F — runtime.json schema (8 cases)

- `test_runtime_json_schema.py`:
  - top-level keys (`mission_id`, `updated_at`, `handoffs`, `sessions`).
  - `mission_id` non-empty string.
  - `updated_at` Zulu-suffixed.
  - sessions and handoffs required keys (per `.agents/orchestration/CLAUDE.md`).
  - session `status` and handoff `status` enum membership.
  - `needs_human` is bool.

### TASK-G — wave wrappers (3 cases)

- `test_wave_wrappers.py`:
  - `run_wave.py` with two tasks in print mode invokes the launcher per task
    (codex and claude-code launch commands appear in stdout).
  - both sessions recorded in `runtime.json`.
  - `status_wave.py` surfaces both task ids in its output.

### TASK-H — docs

- `.agents/skills/agent-orchestrator/tests/README.md` — explains motivation,
  how to run, file map, hermetic fixtures, contribution guidance.
- `.agents/CLAUDE.md` — added a "For orchestrator launcher / skill changes"
  block linking to the pytest command and tests README.

## Total test count

- 34 tests pass by default (no env flags).
- +4 contract-drift tests pass when `CODEX_CONTRACT_TESTS=1` and
  `CLAUDE_CONTRACT_TESTS=1` are set.
- Total when fully gated: **38 passed, 0 failed, 0 skipped.**

## Verification commands run

```
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
   → 34 passed, 4 skipped in 20.31s

CODEX_CONTRACT_TESTS=1 CLAUDE_CONTRACT_TESTS=1 \
  .venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/
   → 38 passed in 21.08s

grep -RIn "ask-for-approval" \
  .agents/skills/agent-orchestrator/scripts \
  .agents/skills/agent-orchestrator/SKILL.md \
  .claude/commands
   → (empty)
```

## Acceptance criteria status (final)

| # | Criterion | Status |
|---|---|---|
| 1 | codex `--mode background` survives launcher exit | ✅ tests `test_background_worker_survives_launcher_exit[codex]` + `test_worker_survives_subshell_exit` |
| 2 | claude-code `--mode background` survives | ✅ `[claude-code]` variant |
| 3 | `pytest .agents/skills/agent-orchestrator/tests/` green | ✅ 34 passed, 4 skipped (env-gated) |
| 4 | active code clean of deprecated flag | ✅ scoped grep returns nothing |
| 5 | incidents.md resolution entry | ✅ present at line 15 |
| 6 | SKILL.md + orchestrator.md show only valid flags | ✅ both contain `start_new_session` + `--codex-bypass-approvals` |
| 7 | `--codex-bypass-approvals` default off + opt-in works | ✅ unit tests `test_codex_command_default_omits_deprecated_flag` + `test_codex_command_with_bypass_appends_dangerous_flag` |

## Risks / follow-ups

- The PATH-shim fake binaries are bash scripts. On a CI without bash this
  would skip; not an issue locally.
- Background-survival tests use `time.sleep(3)`. If the shim is changed to
  sleep longer, the sleep budget must follow. Mitigation: the value is in
  one place (the fixture) and one test constant.
- `status_wave.py` test currently only checks task ids appear in output. A
  stricter assertion on stale-heartbeat detection would need to construct
  a hand-crafted `runtime.json` with a backdated `last_activity`; left as
  a future enhancement.
- Tests run in ~20s for the full suite (background-survival waits 3s per
  parametrized case + SIGHUP guard waits 3s). Acceptable for a skill-local
  suite; if we add it to the main `make test` target, we may want to mark
  these as `slow` and gate behind another env var.

## Blockers

None.

## Do-not-merge conditions

None — all acceptance items now pass.

## Suggested next task

Hand the mission to Verifier for a final independent sweep. After
verification, Integrator should:

1. Run the full project test suite (`make test`) to ensure no regression
   outside this skill.
2. Confirm `grep -RIn "ask-for-approval"` in the scoped paths is clean.
3. Stage the changes on branch
   `eduardk/eng-213-orchestrator-launcher-reliability-and-test-harness`
   (Linear-suggested name) and open the PR — wait for human approval before
   commit/push per CLAUDE.md.

## Handoff

Handoff: worker/claude-code -> verifier/claude-code for ENG-213. TASK-B-H
implementation and TASK-A regression guard complete. Full test suite green.
Mission ready for final verifier sweep and integration.
