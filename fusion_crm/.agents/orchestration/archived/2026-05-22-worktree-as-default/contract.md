# Contract — ENG-225 (M-2)

## Argparse surface additions

```python
parser.add_argument(
    "--workspace",
    choices=["worktree", "self"],
    default=None,  # filled in main() based on --role
    help="Where the worker runs. 'worktree' creates an isolated git "
         "worktree (recommended for parallel safety); 'self' runs in "
         "the current checkout (requires --allow-self-execute).",
)
parser.add_argument(
    "--allow-self-execute",
    action="store_true",
    help="Acknowledge that the worker will run in the current checkout "
         "rather than an isolated worktree. Required with --workspace self.",
)
parser.add_argument(
    "--scope",
    choices=["tiny", "bugfix", "docs", "none"],
    default=None,  # required when --workspace self; refused otherwise
    help="Self-execute blast-radius marker. Required (non-'none') when "
         "the orchestrator chooses --workspace self.",
)
parser.add_argument(
    "--branch-base",
    default="main",
    help="Base branch for worktree creation. Default 'main'.",
)
```

## Default workspace resolution

In `main()` after `parse_args()`:

```python
if args.workspace is None:
    args.workspace = "worktree" if args.role == "worker" else "self"
```

## Worktree provisioning flow

```python
if args.workspace == "worktree":
    _preflight_clean_base(args.branch_base)          # SystemExit if dirty
    branch = f"{args.linear_id.lower()}-{args.task_id.lower()}"
    if _branch_exists(branch):
        branch = f"{branch}-{session_id[:6]}"
    wt_path = _paths.worktree_dir(mission_id, args.task_id)
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", str(wt_path), "-b", branch, args.branch_base],
        check=True,
    )
    args.worktree = str(wt_path)
    args.branch = branch
```

## Self-execute guardrail flow

```python
elif args.workspace == "self":
    if not args.allow_self_execute:
        raise SystemExit(
            "Self-execute requires --allow-self-execute. Pass --workspace "
            "worktree (default for workers) for safe parallel execution."
        )
    prompt_size = len(prompt_text)
    if prompt_size > 5000:
        raise SystemExit(
            f"Self-execute refused: prompt is {prompt_size} chars (>5000). "
            "Either trim the prompt or use --workspace worktree."
        )
    if args.scope is None or args.scope == "none":
        raise SystemExit(
            "Self-execute requires --scope tiny|bugfix|docs (none not allowed). "
            "This records the orchestrator's blast-radius decision in "
            "decision-log.md for audit."
        )
    _record_scope_marker(spec_dir, args)             # writes Scope: ... to decision-log.md
```

## Scope marker format (decision-log.md entry)

```markdown
## 2026-05-22T04:30:00Z — Scope: bugfix

Self-execute approved for {task_id} via --workspace self.

- Linear: {linear_id} — {linear_url}
- Prompt size: {prompt_size} chars (under 5000-char threshold)
- Reason: {args.reason or args.note}
- Allowed scope marker: bugfix

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.
```

## Branch naming policy

- Default branch name: `<linear-id-lower>-<task-id-lower>`. Example:
  `eng-225-task-a`.
- If branch already exists: append `-<session_id[:6]>`. Example:
  `eng-225-task-a-4b206c`.

## `cleanup_worktrees.py` semantics

CLI:
```
python3 cleanup_worktrees.py [--apply] [--force] [--quiet]
```

Defaults:
- `--dry-run` (implicit when neither `--apply` nor `--force`).
- Walks `_paths.runtime_root()` looking for `worktrees/<task-id>/`
  directories.
- For each candidate, computes prune-eligibility:
  - **Eligible if:** mission folder is under
    `.agents/orchestration/archived/` AND the worktree's branch is
    merged into `main`.
  - **Ineligible if:** either condition fails. Skip silently in
    dry-run; print "skipped: <reason>" in apply mode.
- `--apply` requires `y/N` per worktree before `git worktree remove
  <path>`.
- `--force` permits removal even with unmerged commits; still requires
  per-item confirmation. Refuses to operate without `--apply`.

## Exit codes

- `0` — success (including dry-run no-op).
- `2` — guardrail violation, dirty preflight, missing flag, etc.
- `3` — git operation failed (worktree add/remove).
- `4` — user declined confirmation in cleanup.

## Backward compatibility

- Existing `launch_worker.py --worktree <path>` continues to work for
  manual overrides. When `--workspace` is explicitly set, the new flow
  takes precedence; when only `--worktree` is passed (legacy), the
  launcher infers `--workspace self --allow-self-execute --scope
  tiny` with a deprecation warning. (No call site in repo uses this
  legacy path; the inference is for human partners who muscle-memory
  the old flag.)
- Wave files (`run_wave.py` task JSON) gain optional `workspace`,
  `allow_self_execute`, `scope`, `branch_base` keys with the same
  semantics. Task files that omit them fall through to defaults.
