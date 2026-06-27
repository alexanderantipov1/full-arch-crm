#!/usr/bin/env python3
"""Launch dashboard-visible Codex or Claude Code workers."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Local import — paths.py lives next to this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

REPO_ROOT = _paths.REPO_ROOT
DEFAULT_MISSION = REPO_ROOT / ".agents" / "orchestration" / "current"
ACTIVE_STATUSES = {"assigned", "running", "waiting", "blocked", "verification-failed"}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip() + "\n")


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    raise SystemExit("Provide --prompt or --prompt-file.")


def ensure_mission(spec_dir: Path, runtime_dir: Path) -> None:
    """Create both halves of the mission layout.

    Spec dir (in repo) holds decision artifacts + reports.
    Runtime dir (under FUSION_AGENT_RUNTIME_HOME / default) holds live
    telemetry (runtime.json, runlog.md, board.md, linear-sync.md,
    prompts/, logs/).
    """
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "reports").mkdir(parents=True, exist_ok=True)
    spec_defaults = {
        "goal.md": "# Mission Goal\n\nTBD\n",
        "acceptance.md": "# Acceptance Criteria\n\nTBD\n",
        "verification.md": "# Verification\n\nTBD\n",
        "contract.md": "# Contract\n\nTBD\n",
        "ownership.yaml": "tasks: {}\n",
        "incidents.md": "# Incidents\n\n",
        "lessons.md": "# Lessons\n\n",
        "decision-log.md": "# Decision Log\n\n",
    }
    for filename, content in spec_defaults.items():
        path = spec_dir / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "prompts").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)


def build_worker_prompt(args: argparse.Namespace, session_id: str, prompt: str) -> str:
    spec_rel = relative(args.mission.resolve())
    return f"""You are a Fusion CRM {args.role} agent.

Task:
- Task id: {args.task_id}
- Linear issue: {args.linear_id}
- Linear URL: {args.linear_url}
- Linear title: {args.linear_title}
- Runtime: {args.runtime}
- Session id: {session_id}

Rules:
- Read CLAUDE.md, AGENTS.md, .agents/CLAUDE.md, .agents/AGENTS.md, and .agents/orchestration/CLAUDE.md.
- Keep repository files in English.
- Do not edit .env* or shipped Alembic revisions.
- Do not commit, push, or run destructive commands.
- Keep work inside the task scope.
- Mission layout: decision artifacts and reports live in {spec_rel} (repo); live runtime telemetry (runtime.json, runlog.md, board.md, linear-sync.md, prompts/, logs/) lives under FUSION_AGENT_RUNTIME_HOME or ~/.fusion-agent-orchestrator/<repo-hash>/{Path(spec_rel).name}/.
- Keep dashboard state current: update runtime.json + runlog.md in the runtime path during long work.
- Write the final or paused report to {spec_rel}/reports/{args.task_id}-worker-report.md (repo, not runtime path).
- Include changed files, tests run, verification result, risks, blockers, and do-not-merge conditions in the report.

Assigned work:
{prompt.rstrip()}
"""


def build_command(args: argparse.Namespace, prompt_path: Path) -> list[str]:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    if args.runtime == "codex":
        codex_full_auto = bool(
            getattr(args, "codex_full_auto", False)
            or getattr(args, "codex_bypass_approvals", False)
        )
        command = [
            "codex",
            "exec",
            "--cd",
            str(Path(args.worktree).resolve()),
            "--sandbox",
            args.codex_sandbox,
        ]
        if codex_full_auto:
            command.append("--dangerously-bypass-approvals-and-sandbox")
        command.append(prompt_text)
        return command
    if args.runtime == "claude-code":
        return [
            "claude",
            "-p",
            "--permission-mode",
            args.claude_permission_mode,
            prompt_text,
        ]
    raise SystemExit(f"Unsupported runtime: {args.runtime}")


def shell_quote(parts: list[str]) -> str:
    return " ".join(shlex_quote(part) for part in parts)


def shlex_quote(value: str) -> str:
    if not value:
        return "''"
    safe = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@%+=:,./-"
    if all(char in safe for char in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def update_runtime(
    args: argparse.Namespace,
    spec_dir: Path,
    runtime_dir: Path,
    session_id: str,
    prompt_path: Path,
    log_path: Path,
) -> None:
    now = utc_now()
    runtime_path = runtime_dir / "runtime.json"
    runtime = read_json(runtime_path)
    runtime.setdefault("mission_id", spec_dir.name)
    runtime["updated_at"] = now
    sessions = [item for item in runtime.get("sessions", []) if isinstance(item, dict)]
    sessions = [item for item in sessions if item.get("id") != session_id]
    sessions.append(
        {
            "id": session_id,
            "role": args.role,
            "agent": args.runtime if not args.worker_name else f"{args.runtime}/{args.worker_name}",
            "task_id": args.task_id,
            "linear_issue_id": args.linear_id,
            "linear_issue_url": args.linear_url,
            "linear_status": args.linear_status,
            "linear_title": args.linear_title,
            "status": "running" if args.mode in {"background", "tmux"} else "assigned",
            "phase": args.phase,
            "worktree": args.worktree,
            "branch": args.branch,
            "last_activity": now,
            "needs_human": False,
            "risk": args.risk,
            "current_note": args.note,
            "prompt_path": str(prompt_path),
            "log_path": str(log_path),
            "launch_mode": args.mode,
        }
    )
    runtime["sessions"] = sessions
    handoffs = [item for item in runtime.get("handoffs", []) if isinstance(item, dict)]
    handoffs.append(
        {
            "id": f"handoff-{session_id}",
            "created_at": now,
            "task_id": args.task_id,
            "linear_issue_id": args.linear_id,
            "from_role": "orchestrator",
            "from_agent": "codex",
            "to_role": args.role,
            "to_agent": args.runtime if not args.worker_name else f"{args.runtime}/{args.worker_name}",
            "reason": args.reason,
            "status": "accepted",
        }
    )
    runtime["handoffs"] = handoffs[-100:]
    write_json(runtime_path, runtime)


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def refresh_tables(spec_dir: Path, runtime_dir: Path) -> None:
    """Render board.md and linear-sync.md from runtime.json.

    board.md and linear-sync.md live next to runtime.json under the
    local runtime dir. Report-presence is checked against the repo's
    spec_dir/reports/.
    """
    runtime = read_json(runtime_dir / "runtime.json")
    sessions = [item for item in runtime.get("sessions", []) if isinstance(item, dict)]
    board_lines = [
        "| Task | Linear | Owner | Agent | Status | Worktree | Branch | Report | Needs human | Updated |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    sync_lines = [
        "| Task | Linear issue | Linear URL | Linear status | Execution status | Owner | Updated |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in sessions:
        task_id = str(item.get("task_id", ""))
        report = f"reports/{task_id}-worker-report.md"
        report_status = "yes" if (spec_dir / report).is_file() else "no"
        needs_human = "yes" if item.get("needs_human") else "no"
        updated = str(item.get("last_activity") or runtime.get("updated_at") or "")
        board_lines.append(
            "| {task} | {linear} | {owner} | {agent} | {status} | {worktree} | {branch} | {report} | {needs} | {updated} |".format(
                task=md(task_id),
                linear=md(str(item.get("linear_issue_id", ""))),
                owner=md(str(item.get("role", ""))),
                agent=md(str(item.get("agent", ""))),
                status=md(str(item.get("status", ""))),
                worktree=md(str(item.get("worktree", ""))),
                branch=md(str(item.get("branch", ""))),
                report=md(report_status),
                needs=md(needs_human),
                updated=md(updated),
            )
        )
        sync_lines.append(
            "| {task} | {linear} | {url} | {linear_status} | {status} | {owner} | {updated} |".format(
                task=md(task_id),
                linear=md(str(item.get("linear_issue_id", ""))),
                url=md(str(item.get("linear_issue_url", ""))),
                linear_status=md(str(item.get("linear_status", ""))),
                status=md(str(item.get("status", ""))),
                owner=md(str(item.get("role", ""))),
                updated=md(updated),
            )
        )
    (runtime_dir / "board.md").write_text("\n".join(board_lines) + "\n", encoding="utf-8")
    (runtime_dir / "linear-sync.md").write_text("\n".join(sync_lines) + "\n", encoding="utf-8")


def md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def launch(args: argparse.Namespace, command: list[str], log_path: Path) -> int | None:
    if args.mode == "print":
        print(shell_quote(command))
        return None
    if args.mode == "background":
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a", encoding="utf-8")
        # Intentional local orchestrator launch; command is assembled from fixed runtime templates.
        # start_new_session=True detaches the child from the launcher's controlling terminal so
        # the worker survives launcher exit. stdin=DEVNULL prevents inheriting a pty/pipe that
        # would deliver SIGHUP when the parent shell closes.
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=args.worktree,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        print(f"Started {args.runtime} worker pid={process.pid} log={log_path}")
        return process.pid
    if args.mode == "tmux":
        tmux_path = shutil.which("tmux")
        if tmux_path is None:
            raise SystemExit("tmux is not available. Use --mode background or --mode print.")
        session_name = args.tmux_name or f"agent-{args.task_id.lower()}-{uuid.uuid4().hex[:6]}"
        tmux_command = [
            tmux_path,
            "new-session",
            "-d",
            "-s",
            session_name,
            "-c",
            str(Path(args.worktree).resolve()),
            shell_quote(command) + f" 2>&1 | tee -a {shlex_quote(str(log_path.resolve()))}",
        ]
        # Intentional local orchestrator launch; tmux path is resolved with shutil.which above.
        subprocess.run(tmux_command, check=True)  # noqa: S603
        print(f"Started tmux session {session_name} log={log_path}")
        return None
    raise SystemExit(f"Unsupported launch mode: {args.mode}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch a dashboard-visible Codex or Claude Code worker.")
    parser.add_argument("--mission", type=Path, default=DEFAULT_MISSION)
    parser.add_argument("--runtime", choices=["codex", "claude-code"], required=True)
    parser.add_argument("--role", choices=["worker", "verifier", "integrator", "reviewer"], default="worker")
    parser.add_argument("--mode", choices=["print", "background", "tmux"], default="print")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--linear-id", required=True)
    parser.add_argument("--linear-url", required=True)
    parser.add_argument("--linear-title", required=True)
    parser.add_argument("--linear-status", default="In Progress")
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--worktree", default=str(REPO_ROOT))
    parser.add_argument("--branch", default="current")
    parser.add_argument("--worker-name", default="")
    parser.add_argument("--phase", default="assigned")
    parser.add_argument("--reason", default="Worker assignment accepted by Orchestrator.")
    parser.add_argument("--risk", default="medium")
    parser.add_argument("--note", default="Worker launched by Orchestrator.")
    parser.add_argument("--codex-sandbox", default="workspace-write")
    parser.add_argument(
        "--codex-bypass-approvals",
        action="store_true",
        help=(
            "Append --dangerously-bypass-approvals-and-sandbox to the codex exec "
            "command. Default off. Only enable when the worker explicitly needs "
            "to bypass approvals; this is unsafe by design."
        ),
    )
    parser.add_argument(
        "--codex-full-auto",
        action="store_true",
        help=(
            "Orchestrator convenience profile for non-interactive Codex workers. "
            "Maps to the current Codex CLI flag "
            "--dangerously-bypass-approvals-and-sandbox because this installed "
            "Codex version does not expose `codex exec --full-auto`."
        ),
    )
    parser.add_argument("--claude-permission-mode", default="default")
    parser.add_argument("--tmux-name")
    # M-2 / ENG-225 — workspace isolation + self-execute guardrail.
    parser.add_argument(
        "--workspace",
        choices=["worktree", "self"],
        default=None,
        help=(
            "Where the worker runs. 'worktree' creates an isolated git "
            "worktree (recommended for parallel safety); 'self' runs in "
            "the current checkout (requires --allow-self-execute). "
            "Defaults to 'worktree' for --role worker, 'self' for verifier/integrator/reviewer."
        ),
    )
    parser.add_argument(
        "--allow-self-execute",
        action="store_true",
        help=(
            "Acknowledge that the worker will run in the current checkout "
            "rather than an isolated worktree. Required with --workspace self."
        ),
    )
    parser.add_argument(
        "--scope",
        choices=["tiny", "bugfix", "docs", "none"],
        default=None,
        help=(
            "Self-execute blast-radius marker. Required (non-'none') when "
            "--workspace self is chosen. Recorded in decision-log.md."
        ),
    )
    parser.add_argument(
        "--branch-base",
        default="main",
        help="Base branch for worktree creation. Default 'main'.",
    )
    parser.add_argument(
        "--require-clean-base",
        action="store_true",
        help=(
            "Refuse to create a worktree when the canonical checkout has "
            "uncommitted/untracked changes. Default OFF: worktrees are created "
            "from the committed base ref and are isolated from the canonical "
            "working tree, so a dirty canonical checkout is the expected "
            "parallel-work state and only triggers a warning."
        ),
    )
    return parser.parse_args()


# --- M-2 worktree + guardrail helpers ----------------------------------------

SELF_EXECUTE_PROMPT_THRESHOLD = 5000


def _resolve_default_workspace(role: str) -> str:
    return "worktree" if role == "worker" else "self"


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    # Local orchestrator-side git invocations against a known checkout.
    git_bin = shutil.which("git")
    if git_bin is None:
        raise SystemExit("git is not on PATH; cannot manage worktrees.")
    return subprocess.run(  # noqa: S603
        [git_bin, *args],
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )


def _preflight_base(repo: Path, base: str, require_clean: bool = False) -> None:
    """Inspect the canonical checkout before creating a worktree.

    A ``git worktree add <path> -b <branch> <base>`` checks the new worktree
    out from the *committed* ``<base>`` ref into a separate directory.
    Uncommitted and untracked files in the canonical checkout do NOT propagate
    into the new worktree — isolation from a dirty canonical tree is exactly
    why ``PARALLEL_WORK_POLICY.md`` mandates worktrees and reserves the
    canonical checkout for integration/read-only. So a dirty canonical
    checkout is the normal, expected state and MUST NOT block autonomous
    launch.

    Default behaviour therefore only WARNS about dirty state (so the operator
    knows another session may hold uncommitted work in the canonical tree) and
    proceeds. Pass ``require_clean=True`` (CLI ``--require-clean-base``) to
    restore the strict gate that refuses to launch off a dirty base.
    """
    status = _git(["status", "--porcelain"], cwd=repo)
    if status.returncode != 0:
        raise SystemExit(
            f"git status failed in {repo}: rc={status.returncode} stderr={status.stderr.strip()}"
        )
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    if not dirty:
        return
    # Show up to first 5 entries to keep the message readable.
    head = "\n".join("  " + line for line in dirty[:5])
    more = "" if len(dirty) <= 5 else f"\n  ... ({len(dirty) - 5} more)"
    if require_clean:
        raise SystemExit(
            f"--require-clean-base set and base '{base}' has uncommitted changes "
            f"in the canonical checkout ({repo}):\n{head}{more}\n\n"
            "Commit or stash these, or drop --require-clean-base — worktrees are "
            "isolated from the canonical working tree."
        )
    print(
        f"[launch_worker] note: canonical checkout ({repo}) has {len(dirty)} "
        f"uncommitted/untracked path(s); the new worktree is created from the "
        f"committed '{base}' ref and is unaffected:\n{head}{more}",
        file=sys.stderr,
    )


def _branch_exists(repo: Path, branch: str) -> bool:
    rc = _git(["rev-parse", "--verify", branch], cwd=repo).returncode
    return rc == 0


def _provision_worktree(
    repo: Path,
    mission_id: str,
    task_id: str,
    linear_id: str,
    branch_base: str,
    session_id: str,
    require_clean_base: bool = False,
) -> tuple[Path, str]:
    """Create a git worktree for this task and return (path, branch_name)."""
    _preflight_base(repo, branch_base, require_clean=require_clean_base)
    branch = f"{linear_id.lower()}-{task_id.lower()}"
    if _branch_exists(repo, branch):
        branch = f"{branch}-{session_id[:6]}"
    wt_path = _paths.worktree_dir(mission_id, task_id)
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    result = _git(
        ["worktree", "add", str(wt_path), "-b", branch, branch_base],
        cwd=repo,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"git worktree add failed (rc={result.returncode}):\n"
            f"  cmd: git worktree add {wt_path} -b {branch} {branch_base}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return wt_path, branch


def _enforce_self_execute_guardrail(args: argparse.Namespace, prompt_text: str) -> None:
    """Refuse self-execute unless all three preconditions hold."""
    if not args.allow_self_execute:
        raise SystemExit(
            "Self-execute requires --allow-self-execute. Either pass it "
            "explicitly, or use --workspace worktree (default for workers) "
            "for safe parallel execution."
        )
    size = len(prompt_text)
    if size > SELF_EXECUTE_PROMPT_THRESHOLD:
        raise SystemExit(
            f"Self-execute refused: prompt is {size} chars "
            f"(>{SELF_EXECUTE_PROMPT_THRESHOLD}). Either trim the prompt or "
            "use --workspace worktree for an isolated checkout."
        )
    if args.scope is None or args.scope == "none":
        raise SystemExit(
            "Self-execute requires --scope tiny|bugfix|docs (not 'none'). "
            "This records the orchestrator's blast-radius decision in "
            "decision-log.md for audit."
        )


def _record_scope_marker(spec_dir: Path, args: argparse.Namespace, prompt_size: int) -> None:
    """Append a Scope: entry to decision-log.md and a marker to the runlog."""
    decision_log = spec_dir / "decision-log.md"
    decision_log.parent.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    entry = (
        f"\n## {now} — Scope: {args.scope}\n\n"
        f"Self-execute approved for {args.task_id} via `--workspace self`.\n\n"
        f"- Linear: {args.linear_id} — {args.linear_url}\n"
        f"- Prompt size: {prompt_size} chars (under {SELF_EXECUTE_PROMPT_THRESHOLD}-char threshold)\n"
        f"- Reason: {args.reason or args.note}\n"
        f"- Allowed scope marker: {args.scope}\n\n"
        "By accepting this scope, the orchestrator certifies the work is small\n"
        "enough that worktree isolation is not required.\n"
    )
    with decision_log.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def main() -> None:
    args = parse_args()
    prompt = read_prompt(args)
    spec_dir = args.mission.resolve()
    mission_id = _paths.mission_id_from_spec_path(spec_dir)
    runtime_dir = _paths.mission_runtime_dir(mission_id)
    ensure_mission(spec_dir, runtime_dir)
    if not args.linear_id.strip() or not args.linear_url.strip():
        raise SystemExit("Linear gate failed: --linear-id and --linear-url are required.")
    session_id = uuid.uuid4().hex[:12]
    prompt_path = runtime_dir / "prompts" / f"{args.task_id}-{session_id}.md"
    log_path = runtime_dir / "logs" / f"{args.task_id}-{session_id}.log"
    prompt_text = build_worker_prompt(args, session_id, prompt)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")

    # M-2 / ENG-225 — resolve workspace, provision worktree or enforce guardrail.
    if args.workspace is None:
        args.workspace = _resolve_default_workspace(args.role)
    if args.workspace == "worktree":
        wt_path, wt_branch = _provision_worktree(
            REPO_ROOT,
            mission_id,
            args.task_id,
            args.linear_id,
            args.branch_base,
            session_id,
            require_clean_base=args.require_clean_base,
        )
        args.worktree = str(wt_path)
        args.branch = wt_branch
    elif args.workspace == "self":
        _enforce_self_execute_guardrail(args, prompt_text)
        _record_scope_marker(spec_dir, args, len(prompt_text))
    else:  # pragma: no cover — argparse choices enforce this
        raise SystemExit(f"Unsupported workspace: {args.workspace}")

    command = build_command(args, prompt_path)
    update_runtime(args, spec_dir, runtime_dir, session_id, prompt_path, log_path)
    refresh_tables(spec_dir, runtime_dir)
    now = utc_now()
    append_line(
        runtime_dir / "runlog.md",
        f"- {now} | orchestrator | {args.task_id} | handoff | Handoff: orchestrator/codex -> {args.role}/{args.runtime} for {args.linear_id}. {args.reason}",
    )
    append_line(
        runtime_dir / "runlog.md",
        f"- {now} | {args.runtime} | {args.task_id} | {args.mode} | Launch command prepared for {args.role} (workspace={args.workspace}, branch={args.branch}).",
    )
    if args.workspace == "self":
        append_line(
            runtime_dir / "runlog.md",
            f"- {now} | orchestrator | {args.task_id} | scope | Scope: {args.scope} (self-execute approved; logged to decision-log.md).",
        )
    pid = launch(args, command, log_path)
    if pid is not None:
        runtime = read_json(runtime_dir / "runtime.json")
        for item in runtime.get("sessions", []):
            if isinstance(item, dict) and item.get("id") == session_id:
                item["pid"] = pid
                item["status"] = "running"
                item["last_activity"] = utc_now()
        runtime["updated_at"] = utc_now()
        write_json(runtime_dir / "runtime.json", runtime)
        refresh_tables(spec_dir, runtime_dir)


if __name__ == "__main__":
    main()
