# TASK-A Worker Prompt — Fix launcher detachment and codex flag drift

You are a Fusion CRM worker agent.

Task:
- Task id: TASK-A
- Linear issue: ENG-213
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-213/orchestrator-launcher-reliability-and-test-harness
- Linear title: Orchestrator launcher reliability and test harness
- Mission folder: .agents/orchestration/orchestrator-launcher-reliability/
- Branch (suggested): eduardk/eng-213-orchestrator-launcher-reliability-and-test-harness

## Required reading before any code change

- `CLAUDE.md`
- `AGENTS.md`
- `.agents/CLAUDE.md`
- `.agents/AGENTS.md`
- `.agents/orchestration/CLAUDE.md`
- `.agents/orchestration/orchestrator-launcher-reliability/goal.md`
- `.agents/orchestration/orchestrator-launcher-reliability/acceptance.md`
- `.agents/orchestration/orchestrator-launcher-reliability/verification.md`
- `.agents/orchestration/orchestrator-launcher-reliability/contract.md`

## Scope (allowed files)

- `.agents/skills/agent-orchestrator/scripts/launch_worker.py`
- `.agents/skills/agent-orchestrator/scripts/launch_commands.py` (only if needed; default expectation: no change)
- `.agents/skills/agent-orchestrator/SKILL.md`
- `.claude/commands/orchestrator.md`
- `.agents/orchestration/orchestrator-launcher-reliability/incidents.md`

You may not touch any other files.

## Required changes

### 1. Detach background-mode subprocess

In `launch_worker.py`, locate the `launch()` function, `args.mode == "background"` branch. Modify the `subprocess.Popen` call to add two arguments:

```python
process = subprocess.Popen(
    command,
    cwd=args.worktree,
    stdout=log_handle,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,        # do not inherit parent's stdin / controlling pty
    start_new_session=True,          # setsid: new session and process group; no controlling TTY
)
```

Do not change any other Popen call. Do not change tmux-mode behavior.

### 2. Drop deprecated codex flag and add opt-in bypass

In `build_command()`, the `args.runtime == "codex"` branch currently emits:

```python
return [
    "codex",
    "exec",
    "--cd",
    str(Path(args.worktree).resolve()),
    "--sandbox",
    args.codex_sandbox,
    "--ask-for-approval",
    args.codex_approval,
    prompt_text,
]
```

Replace with logic that:

- Always emits `codex exec --cd <worktree> --sandbox <sandbox> <prompt_text>` as the base.
- If `args.codex_bypass_approvals` is truthy, inserts `--dangerously-bypass-approvals-and-sandbox` before the prompt argument.

If `codex exec --help` on the currently installed CLI does not list `--cd`, drop `--cd <worktree>` from the emitted command and rely on `cwd=args.worktree` already passed to `Popen` / `Popen(cwd=...)`. Verify this once before deciding; do not guess.

In `parse_args()`:

- Remove the `--codex-approval` argument.
- Add a new boolean flag:

```python
parser.add_argument(
    "--codex-bypass-approvals",
    action="store_true",
    help=(
        "Append --dangerously-bypass-approvals-and-sandbox to the codex exec "
        "command. Default off. Only enable when the worker explicitly needs "
        "to bypass approvals; this is unsafe by design."
    ),
)
```

### 3. Update SKILL.md examples

In `.agents/skills/agent-orchestrator/SKILL.md`, the example launch snippet currently shows the old flag set. Replace it with the current accepted flags. Do not show `--codex-bypass-approvals` in the default example — keep the safe default.

### 4. Update slash-command example

In `.claude/commands/orchestrator.md`, the snippet currently includes the old flag set. Update to match the new flag set. Keep the example minimal.

### 5. Add resolution entry to mission incidents.md

Append to `.agents/orchestration/orchestrator-launcher-reliability/incidents.md` (do NOT touch the archived mission):

```text
## Resolution

- <UTC timestamp> | TASK-A | Resolved: launcher detach + codex flag drift fixed in <commit-sha>. Background mode now sets start_new_session=True and stdin=DEVNULL. `--ask-for-approval` removed; `--codex-bypass-approvals` opt-in added. Verified by running `python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py --runtime <codex|claude-code> --mode background ...` with a sentinel prompt; worker survives launcher exit and log is non-empty.
```

## Verification you must run before writing the report

1. `python3 -m py_compile .agents/skills/agent-orchestrator/scripts/launch_worker.py`
2. `python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py --runtime codex --mode print --task-id TASK-A-smoke --linear-id ENG-213 --linear-url https://linear.app/fusion-dental-implants/issue/ENG-213/orchestrator-launcher-reliability-and-test-harness --linear-title smoke --prompt "echo ok"` — assert the printed command contains `codex exec`, `--sandbox`, the prompt, and does NOT contain `--ask-for-approval`.
3. Same with `--codex-bypass-approvals` added — assert the printed command DOES contain `--dangerously-bypass-approvals-and-sandbox`.
4. Same with `--runtime claude-code` — assert printed command contains `claude -p --permission-mode`.
5. Real background smoke (only if `codex` and/or `claude` binaries are available locally): use a fresh tmp mission folder, run the launcher with `--mode background --prompt "echo TASK-A-smoke && sleep 5"`. After the launcher exits, check that the log file is non-empty within 3 seconds.
6. `grep -R "ask-for-approval" .agents .claude` returns nothing.

## Worker report — write to mission folder

Write the final report to:

`.agents/orchestration/orchestrator-launcher-reliability/reports/TASK-A-worker-report.md`

It must include:

- task id and Linear id;
- branch (whether you created it or worked on existing);
- changed files (full list with brief description per file);
- diff summary (key snippets, not full diff);
- verification commands run with their actual output (or a faithful summary);
- risks and follow-ups;
- do-not-merge conditions if any;
- handoff request to verifier (write `Handoff: worker/<runtime> -> verifier/<runtime> for ENG-213. TASK-A complete pending verifier sweep.`).

## Hard rules

- Repository files in English. Conversation may be in Russian.
- No commits, pushes, force-pushes, branch deletes, or destructive operations.
- No worktree creation (work on the existing checkout).
- No edits to files outside the scope list above.
- No PHI, no secrets, no `.env*` reads.
- No `--no-verify`, no skipping of hooks.
- If a verification step fails, STOP. Write `Verification failed:` in the report and request human attention via `Needs decision:`. Do not silently retry.
- If you encounter a tool error, log it in mission `incidents.md` under a new `## Tool errors` section before continuing.
