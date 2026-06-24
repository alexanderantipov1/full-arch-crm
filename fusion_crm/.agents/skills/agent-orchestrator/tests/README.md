# Orchestrator launcher test suite

Tests covering `launch_worker.py`, `run_wave.py`, and `status_wave.py`. Lives
alongside the skill so the contract is enforced wherever the skill ships.

## Why this exists

The 2026-05-20 incident produced 0-byte logs for both `codex` and `claude-code`
background workers. Root causes:

1. `subprocess.Popen` lacked `start_new_session=True` and `stdin=DEVNULL`, so
   the child inherited the launcher's controlling terminal and died from
   SIGHUP when the parent shell closed.
2. The codex command builder emitted the deprecated `--ask-for-approval`
   flag, which the current `codex exec` CLI rejects.

This suite guards against regressions on both axes plus the surrounding
contract.

## Run locally

```bash
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
```

Tests are hermetic — the `_runtime_home` autouse fixture monkeypatches
`FUSION_AGENT_RUNTIME_HOME` to `tmp_path` for every test, so the
launcher writes runtime files inside `tmp_path` instead of the real
`~/.fusion-agent-orchestrator/`. The `mission_dir` fixture lives at
`tmp_path/mission` and is both the spec dir (decision artifacts) and
the runtime dir (telemetry) for legacy single-arg tests; new tests can
use `mission_spec_dir` + `runtime_dir` fixtures for an explicit split.

### M-2 / ENG-225 — workspace isolation tests

`test_workspace_guardrail.py` exercises `--workspace self` rejection
rules and the `Scope:` decision-log writer.

`test_workspace_isolation.py` provisions two real `git worktree`s on
a tmp git repo to prove worker-A's filesystem changes do NOT bleed
into worker-B's checkout (or the canonical checkout). It depends on
`git worktree` being available on PATH; the suite skips cleanly on
hosts without it.

`test_cleanup_worktrees.py` covers the prune helper's dry-run / apply
/ force flows with monkeypatched `classify` and `remove_worktree`
hooks, so no real filesystem mutation occurs during unit tests.

### M-3 / ENG-226 — process supervision tests

`test_pid_check.py` exercises `runtime_status(pid)` across the
None / negative / non-int / live-subprocess / exited matrix.

`test_activity_heuristic.py` proves marker-based detection
(`Needs decision:`, `Blocked:`) wins over mtime, and that markers
beyond the 50-line tail window do NOT bleed into the result.

`test_worker_ctl.py` builds a fake mission folder + runtime.json,
spawns a real subprocess to test the `--kill` SIGTERM-then-SIGKILL
flow within `--grace`, and verifies `--list` / `--status` enrichment
picks up `runtime_status` + `agent_activity`.

`test_start_control_plane.py` is a smoke that brings the dashboard
up on a free port with `--no-open`, polls `/api/snapshot` for
liveness, and shuts down cleanly.

**Activity heuristic is a heuristic, not a contract.** The
`agent_activity` field reflects log mtime + tail marker scan. When
a session is critical (e.g. waiting on human input), trust the
worker's own `Needs decision:` / `Blocked:` runlog markers over the
heuristic. The heuristic exists to provide "is this still moving?"
context, not authoritative status.

To exercise contract drift against the real CLIs:

```bash
CODEX_CONTRACT_TESTS=1 CLAUDE_CONTRACT_TESTS=1 \
  .venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
```

The contract tests skip cleanly when the env vars are absent, so CI without
the binaries does not fail.

## Files

| File | Scope | Linear task |
|---|---|---|
| `conftest.py` | Shared fixtures: tmp mission folder, PATH-shim factory, argparse Namespace builder, custom marks, env-gated skip logic | infrastructure |
| `test_build_command.py` | `build_command()` flag surface for codex (default, full-auto alias, bypass) and claude-code | TASK-B |
| `test_build_worker_prompt.py` | `build_worker_prompt()` includes Linear, mission, role, prompt body | TASK-B |
| `test_update_runtime.py` | `update_runtime()` writes required keys, dedupes by session id, appends handoffs; `refresh_tables()` renders `board.md` and `linear-sync.md` | TASK-B |
| `test_linear_gate.py` | Launcher exits non-zero when `--linear-id` or `--linear-url` is empty | TASK-B |
| `test_background_survival.py` | Background-mode workers survive launcher exit; ppid=1 confirms session detach; runtime.json records pid+status | TASK-C |
| `test_sighup_resilience.py` | Worker spawned via a subshell that exits keeps writing — direct regression guard for the 2026-05-20 incident | TASK-D |
| `test_contract_drift.py` | Env-gated checks against real `codex` / `claude` CLIs (`--cd`, `--sandbox`, bypass flag present; `--ask-for-approval` absent) | TASK-E |
| `test_runtime_json_schema.py` | `runtime.json` produced by the launcher matches the contract in `.agents/orchestration/CLAUDE.md` (top-level keys, status enums, required keys) | TASK-F |
| `test_wave_wrappers.py` | `run_wave.py` invokes the launcher per task; `status_wave.py` surfaces sessions | TASK-G |

## Hermetic fixtures

The PATH-shim fixtures (`fake_runtime_dir`, `fake_runtime_path`) drop a tiny
bash script named `codex` and `claude` ahead of the system binaries via
`PATH`. The shim prints `SHIM_START` / `SHIM_END` markers around a 2-second
sleep so integration tests can assert that the worker continued writing
after the launcher exited.

Mission folders live under `tmp_path`. No test touches a live
`.agents/orchestration/<mission>/` folder.

## Adding new tests

- Use `mission_dir` for a fresh mission folder per test.
- Use `make_args(**overrides)` to build an `argparse.Namespace` for unit tests
  on internal helpers.
- Use `fake_runtime_path` whenever the launcher needs to find a `codex` or
  `claude` binary.
- Subprocess invocations should pass `env=os.environ.copy()` so the monkey-
  patched `PATH` propagates.
- New custom marks must be registered in `conftest.py:pytest_configure`.
