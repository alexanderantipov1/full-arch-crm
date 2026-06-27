# Contract — ENG-224 (M-1)

## Path resolution

```python
# .agents/skills/agent-orchestrator/scripts/paths.py

REPO_ROOT = <git repo root>   # resolved once via Path(__file__).resolve().parents[N]

def runtime_root() -> Path:
    """Where session telemetry lives. Env overrides default."""
    explicit = os.environ.get("FUSION_AGENT_RUNTIME_HOME")
    if explicit:
        return Path(explicit).resolve()
    repo_hash = hashlib.sha1(str(REPO_ROOT.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path.home() / ".fusion-agent-orchestrator" / repo_hash

def mission_runtime_dir(mission_id: str) -> Path:
    """Live telemetry: runtime.json, runlog.md, board.md, linear-sync.md, prompts/, logs/."""
    return runtime_root() / mission_id

def mission_spec_dir(mission_id: str) -> Path:
    """Durable mission record: goal/acceptance/verification/contract/ownership/decision-log/lessons/incidents/reports."""
    return REPO_ROOT / ".agents" / "orchestration" / mission_id

def worktree_dir(mission_id: str, task_id: str) -> Path:
    """Future M-2 use: per-task git worktrees under the local runtime root."""
    return runtime_root() / mission_id / "worktrees" / task_id
```

## File ownership matrix

| File / dir                                       | Where it lives              |
|--------------------------------------------------|-----------------------------|
| `goal.md`, `acceptance.md`, `verification.md`    | `mission_spec_dir` (repo)   |
| `contract.md`, `ownership.yaml`                  | `mission_spec_dir` (repo)   |
| `decision-log.md`, `lessons.md`, `incidents.md`  | `mission_spec_dir` (repo)   |
| `reports/<task-id>-worker-report.md`             | `mission_spec_dir` (repo)   |
| `runtime.json`                                   | `mission_runtime_dir` (local) |
| `runlog.md`, `board.md`, `linear-sync.md`        | `mission_runtime_dir` (local) |
| `prompts/<task-id>-<sid>.md`                     | `mission_runtime_dir` (local) |
| `logs/<task-id>-<sid>.log`                       | `mission_runtime_dir` (local) |
| `worktrees/<task-id>/`                           | `mission_runtime_dir` (local, M-2 placeholder) |

## Backward compatibility

- `launch_worker.py --mission <path>` callers continue to work: the
  launcher derives `mission_id = Path(args.mission).name` and uses that
  as the lookup key for `mission_runtime_dir`. The decision-artifact
  side reads from `args.mission` directly so worker prompts stay valid.
- Dashboard `--mission <path>` keeps the explicit-flag pinning behavior
  (ENG-223 contract).
- Existing tests should pass after the `mission_dir` fixture splits
  into `mission_spec_dir` + `runtime_dir`. Tests that previously took
  a single `mission_dir` argument and assumed both decision and runtime
  files coexist must be updated to use both fixtures.

## Hash precedence (FUSION_AGENT_RUNTIME_HOME)

```
1. env FUSION_AGENT_RUNTIME_HOME → use as-is, no <repo-hash> appended.
2. (Future) --runtime-root <path> CLI flag → use as-is.
3. Default ~/.fusion-agent-orchestrator/<repo-hash>/ where
   <repo-hash> = sha1(Path(repo_root).resolve())[:12].
```

When the env override is set, callers are explicit about isolation;
the launcher does NOT append `<repo-hash>` underneath. This matters
for tests that monkeypatch the env to `tmp_path` — they want exact
control of the directory layout.

## .gitignore semantics

The intent of `.gitignore` is defense-in-depth, not the primary
enforcement layer. The primary layer is that `paths.py` returns
local paths so writes never go through the repo path. `.gitignore`
catches accidental future writes that bypass `paths.py`.

Suggested rules (target only non-archived missions to preserve
historical commits):

```
# .agents/orchestration runtime telemetry — should live under
# ~/.fusion-agent-orchestrator/<repo-hash>/<mission-id>/, not in repo.
.agents/orchestration/*/runtime.json
.agents/orchestration/*/runlog.md
.agents/orchestration/*/board.md
.agents/orchestration/*/linear-sync.md
.agents/orchestration/*/prompts/
.agents/orchestration/*/logs/

# But: do not ignore the same files inside archived/ — those are
# historical snapshots we keep on purpose.
!.agents/orchestration/archived/**/runtime.json
!.agents/orchestration/archived/**/runlog.md
!.agents/orchestration/archived/**/board.md
!.agents/orchestration/archived/**/linear-sync.md
!.agents/orchestration/archived/**/prompts/
!.agents/orchestration/archived/**/logs/
```

The worker should test both inclusion and re-inclusion paths before
shipping the .gitignore.
