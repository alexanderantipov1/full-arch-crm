#!/usr/bin/env python3
"""Read-only localhost dashboard for agent orchestration state."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = DASHBOARD_ROOT / "static"

# Local import — paths.py + M-3 helpers live under the orchestrator skill.
sys.path.insert(0, str(REPO_ROOT / ".agents" / "skills" / "agent-orchestrator" / "scripts"))
import activity_heuristic as _activity  # noqa: E402
import paths as _paths  # noqa: E402
import pid_check as _pid_check  # noqa: E402

SPEC_FILES = (
    "PLAN_CHECKLIST.md",
    "goal.md",
    "acceptance.md",
    "verification.md",
    "contract.md",
    "ownership.yaml",
    "incidents.md",
    "lessons.md",
    "decision-log.md",
)
RUNTIME_FILES = (
    "board.md",
    "linear-sync.md",
    "runtime.json",
    "runlog.md",
)

# /api/live cache: refresh at most every LIVE_TTL_SECONDS to avoid hammering
# `git` and `gh` on every dashboard tick.
LIVE_TTL_SECONDS = 30
_live_cache: dict[str, Any] = {"generated_at": 0.0, "payload": None}

MISSION_FILES = [
    "goal.md",
    "acceptance.md",
    "verification.md",
    "contract.md",
    "ownership.yaml",
    "board.md",
    "linear-sync.md",
    "runtime.json",
    "runlog.md",
    "incidents.md",
    "lessons.md",
    "decision-log.md",
]

STRATEGY_FILES = [
    "CANDIDATE_MISSIONS.md",
    "HANDOFF_TO_ORCHESTRATOR.md",
    "architecture-radar.md",
    "roadmap.md",
    "business-assumptions.md",
    "strategic-decisions.md",
]

STRATEGY_DIRS = [
    "inbox",
    "discussions",
    "candidate-missions",
]

DECISION_MARKERS = [
    "needs decision",
    "decision needed",
    "needs approval",
    "ready for approval",
    "blocked",
    "blocker",
    "contract drift",
    "ownership violation",
    "verification failed",
    "failed acceptance",
    "missing linear",
    "linear sync failed",
    "handoff:",
]

CHECKBOX_PATTERN = re.compile(r"^(?P<prefix>\s*[-*]\s+)\[(?P<mark>[ xX])\]\s+(?P<text>.+)$")
HEADING_PATTERN = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")
STATUS_PATH_PATTERN = re.compile(r"^(?P<status>.{2})\s+(?P<path>.+)$")


@dataclass(frozen=True)
class DashboardConfig:
    host: str
    port: int
    mission: Path | None
    strategy: Path
    repo: Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def read_text(path: Path, limit: int = 80_000) -> str | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return handle.read(limit)
    except UnicodeDecodeError:
        return None
    except OSError:
        return None


def read_json(path: Path) -> Any:
    text = read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def tail_lines(path: Path, limit: int = 80) -> list[str]:
    text = read_text(path, limit=200_000)
    if text is None:
        return []
    return text.splitlines()[-limit:]


def read_runtime_or_spec_text(
    mission: Path,
    runtime_root: Path,
    name: str,
    *,
    limit: int = 120_000,
) -> tuple[Path, str | None]:
    runtime_path = runtime_root / name
    if runtime_path.is_file():
        return runtime_path, read_text(runtime_path, limit=limit)
    spec_path = mission / name
    return spec_path, read_text(spec_path, limit=limit)


def file_summary(path: Path, root: Path) -> dict[str, Any]:
    exists = path.exists()
    summary: dict[str, Any] = {
        "path": relative_path(path, root),
        "exists": exists,
        "type": "missing",
    }
    if not exists:
        return summary
    try:
        stat = path.stat()
    except OSError:
        summary["type"] = "unreadable"
        return summary
    summary["modified_at"] = datetime.fromtimestamp(
        stat.st_mtime,
        UTC,
    ).isoformat()
    if path.is_dir():
        summary["type"] = "directory"
        try:
            summary["entries"] = sorted(child.name for child in path.iterdir())
        except OSError:
            summary["entries"] = []
        return summary
    summary["type"] = "file"
    summary["size_bytes"] = stat.st_size
    text = read_text(path, limit=12_000)
    if text is not None:
        lines = text.splitlines()
        summary["line_count"] = len(lines)
        summary["preview"] = "\n".join(lines[:12])
    return summary


def parse_markdown_checkboxes(text: str | None) -> list[dict[str, Any]]:
    if not text:
        return []
    items: list[dict[str, Any]] = []
    section = "Overview"
    for index, line in enumerate(text.splitlines(), start=1):
        heading = HEADING_PATTERN.match(line)
        if heading:
            section = heading.group("title").strip()
            continue
        match = CHECKBOX_PATTERN.match(line)
        if not match:
            continue
        mark = match.group("mark")
        items.append(
            {
                "line": index,
                "section": section,
                "done": mark.lower() == "x",
                "text": match.group("text").strip(),
            }
        )
    return items


def parse_markdown_sections(text: str | None) -> list[dict[str, Any]]:
    if not text:
        return []
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for index, line in enumerate(text.splitlines(), start=1):
        heading = HEADING_PATTERN.match(line)
        if heading:
            if current is not None:
                sections.append(current)
            current = {
                "title": heading.group("title").strip(),
                "level": len(heading.group("level")),
                "line": index,
                "body": [],
            }
            continue
        if current is not None:
            current["body"].append(line)
    if current is not None:
        sections.append(current)
    return sections


def parse_markdown_table(text: str | None) -> list[dict[str, str]]:
    if not text:
        return []
    lines = text.splitlines()
    rows: list[dict[str, str]] = []
    index = 0
    while index < len(lines) - 1:
        header_line = lines[index].strip()
        separator_line = lines[index + 1].strip()
        if not (header_line.startswith("|") and separator_line.startswith("|")):
            index += 1
            continue
        headers = [cell.strip() for cell in header_line.strip("|").split("|")]
        separators = [cell.strip() for cell in separator_line.strip("|").split("|")]
        if not headers or len(headers) != len(separators):
            index += 1
            continue
        if not all(set(cell.replace(":", "").strip()) <= {"-"} for cell in separators):
            index += 1
            continue
        index += 2
        while index < len(lines) and lines[index].strip().startswith("|"):
            values = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
            if len(values) == len(headers):
                rows.append(dict(zip(headers, values, strict=False)))
            index += 1
        continue
    return rows


def parse_git_status_line(line: str) -> dict[str, str]:
    raw = line.rstrip()
    match = STATUS_PATH_PATTERN.match(raw)
    if match:
        status = match.group("status").strip() or "modified"
        path = match.group("path").strip()
    elif len(raw) >= 3 and raw[1].isspace():
        # `run_git()` strips the full stdout, so the first short-status line can
        # lose its leading index-status space: " M file" becomes "M file".
        status = raw[0].strip() or "modified"
        path = raw[2:].strip()
    else:
        status = ""
        path = raw.strip()
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[-1].strip()
    return {
        "status": status,
        "path": path,
        "raw": line,
    }


def strip_inline_comment(value: str) -> str:
    return value.split("#", 1)[0].strip().strip("\"'")


def parse_ownership_rules(text: str | None) -> dict[str, Any]:
    rules: dict[str, Any] = {"tasks": {}, "shared_no_touch": []}
    if not text:
        return rules

    current_task: str | None = None
    in_tasks = False
    in_paths = False
    in_shared_no_touch = False

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if indent == 0:
            in_tasks = stripped == "tasks:"
            in_shared_no_touch = stripped == "shared_no_touch:"
            current_task = None
            in_paths = False
            continue

        if in_tasks and indent == 2 and stripped.endswith(":"):
            current_task = stripped[:-1]
            rules["tasks"].setdefault(current_task, {"paths": []})
            in_paths = False
            continue

        if in_tasks and current_task and indent == 4:
            in_paths = stripped == "paths:"
            continue

        if in_tasks and current_task and in_paths and stripped.startswith("- "):
            value = strip_inline_comment(stripped[2:])
            if value:
                rules["tasks"][current_task]["paths"].append(value)
            continue

        if in_shared_no_touch and stripped.startswith("- "):
            value = strip_inline_comment(stripped[2:])
            if value:
                rules["shared_no_touch"].append(value)

    return rules


def path_matches_rule(path: str, rule: str) -> bool:
    normalized_path = path.strip().rstrip("/")
    normalized_rule = rule.strip().rstrip("/")
    if not normalized_path or not normalized_rule:
        return False
    return normalized_path == normalized_rule or normalized_path.startswith(f"{normalized_rule}/")


def ownership_match(path: str, ownership_rules: dict[str, Any]) -> dict[str, str] | None:
    tasks = ownership_rules.get("tasks")
    if not isinstance(tasks, dict):
        return None
    for task_id, task in tasks.items():
        if not isinstance(task, dict):
            continue
        paths = task.get("paths")
        if not isinstance(paths, list):
            continue
        for rule in paths:
            if path_matches_rule(path, str(rule)):
                return {"task_id": str(task_id), "path_rule": str(rule)}
    return None


def no_touch_match(path: str, ownership_rules: dict[str, Any]) -> str | None:
    rules = ownership_rules.get("shared_no_touch")
    if not isinstance(rules, list):
        return None
    for rule in rules:
        if path_matches_rule(path, str(rule)):
            return str(rule)
    return None


def load_plan_locale(runtime_root: Path) -> dict[str, Any]:
    locale_path = runtime_root / "plan-checklist.ru.json"
    payload = read_json(locale_path)
    if not isinstance(payload, dict):
        return {
            "path": str(locale_path),
            "exists": False,
            "locale": None,
            "items": {},
            "sections": {},
            "tasks": {},
        }
    return {
        "path": str(locale_path),
        "exists": True,
        "locale": payload.get("locale") or "ru",
        "items": payload.get("items") if isinstance(payload.get("items"), dict) else {},
        "sections": payload.get("sections") if isinstance(payload.get("sections"), dict) else {},
        "tasks": payload.get("tasks") if isinstance(payload.get("tasks"), dict) else {},
    }


def collect_plan_checklist(mission: Path, runtime_root: Path, repo: Path) -> dict[str, Any]:
    plan_path = mission / "PLAN_CHECKLIST.md"
    text = read_text(plan_path, limit=180_000)
    sections = parse_markdown_sections(text)
    checklist = parse_markdown_checkboxes(text)
    locale = load_plan_locale(runtime_root)
    locale_items = locale["items"]
    locale_sections = locale["sections"]
    for item in checklist:
        line_key = str(item["line"])
        section = str(item["section"])
        item["display_text"] = str(locale_items.get(line_key) or item["text"])
        item["display_section"] = str(locale_sections.get(section) or section)
    dag_sections = [
        {
            "title": section["title"],
            "display_title": str(locale_sections.get(section["title"]) or section["title"]),
            "line": section["line"],
            "body": "\n".join(section["body"]).strip()[:8000],
        }
        for section in sections
        if any(
            token in section["title"].lower()
            for token in ("dag", "wave", "parallel", "dependency", "workflow")
        )
    ]
    total = len(checklist)
    done = sum(1 for item in checklist if item["done"])
    return {
        "path": relative_path(plan_path, repo),
        "exists": plan_path.is_file(),
        "total": total,
        "done": done,
        "open": total - done,
        "items": checklist,
        "dag_sections": dag_sections,
        "section_titles": [section["title"] for section in sections[:40]],
        "locale": {
            "path": locale["path"],
            "exists": locale["exists"],
            "locale": locale["locale"],
        },
        "task_labels": locale["tasks"],
        "empty_state": None
        if plan_path.is_file()
        else "PLAN_CHECKLIST.md is not present for this mission yet.",
    }


def collect_workflow_control(
    mission: Path,
    runtime_root: Path,
    runtime: Any,
    repo: Path,
) -> dict[str, Any]:
    locale = load_plan_locale(runtime_root)
    board_path, board_text = read_runtime_or_spec_text(mission, runtime_root, "board.md")
    linear_path, linear_text = read_runtime_or_spec_text(
        mission,
        runtime_root,
        "linear-sync.md",
    )
    sessions = runtime.get("sessions", []) if isinstance(runtime, dict) else []
    status_counts: dict[str, int] = {}
    worker_rows: list[dict[str, Any]] = []
    if isinstance(sessions, list):
        for session in sessions:
            if not isinstance(session, dict):
                continue
            status = str(session.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            worker_rows.append(
                {
                    "task_id": session.get("task_id") or "",
                    "linear_issue_id": session.get("linear_issue_id") or "",
                    "linear_issue_url": session.get("linear_issue_url") or "",
                    "linear_title": session.get("linear_title") or "",
                    "role": session.get("role") or "",
                    "agent": session.get("agent") or "",
                    "status": status,
                    "phase": session.get("phase") or "",
                    "worktree": session.get("worktree") or "",
                    "branch": session.get("branch") or "",
                    "last_activity": session.get("last_activity") or "",
                    "needs_human": bool(session.get("needs_human")),
                    "runtime_status": session.get("runtime_status") or "",
                    "agent_activity": session.get("agent_activity") or "",
                    "current_note": session.get("current_note") or "",
                }
            )
    return {
        "board_path": relative_path(board_path, repo),
        "linear_sync_path": relative_path(linear_path, repo)
        if str(linear_path).startswith(str(repo))
        else str(linear_path),
        "board_rows": parse_markdown_table(board_text),
        "linear_rows": parse_markdown_table(linear_text),
        "status_counts": status_counts,
        "workers": worker_rows,
        "task_labels": locale["tasks"],
    }


def collect_verification_control(mission: Path, repo: Path) -> dict[str, Any]:
    sources = [
        mission / "verification.md",
        mission / "closure.md",
        mission / "incidents.md",
    ]
    signals: list[dict[str, str]] = []
    keywords = (
        "make lint",
        "mypy",
        "make test",
        "pytest",
        "alembic",
        "browser smoke",
        "production route smoke",
        "pass",
        "fail",
        "failed",
    )
    for path in sources:
        text = read_text(path, limit=120_000)
        if not text:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            normalized = line.lower()
            if not any(keyword in normalized for keyword in keywords):
                continue
            result = "neutral"
            if "pass" in normalized or "passed" in normalized:
                result = "pass"
            if "fail" in normalized or "failed" in normalized:
                result = "fail"
            signals.append(
                {
                    "source": relative_path(path, repo),
                    "line": str(index),
                    "result": result,
                    "text": line.strip()[:500],
                }
            )
    return {"signals": signals[-80:]}


def collect_git_risks(git: dict[str, Any], mission_state: dict[str, Any]) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    status_lines = git.get("status") or []
    if status_lines:
        risks.append(
            {
                "level": "warning",
                "title": "Working tree has uncommitted changes",
                "detail": f"{len(status_lines)} changed path(s) are visible in git status.",
            }
        )
    branch_status = str(git.get("branch_status") or "")
    if "ahead" in branch_status or "behind" in branch_status:
        risks.append(
            {
                "level": "warning",
                "title": "Branch is not synchronized with upstream",
                "detail": branch_status,
            }
        )
    runtime = mission_state.get("runtime")
    sessions = runtime.get("sessions", []) if isinstance(runtime, dict) else []
    if sessions and all(
        isinstance(session, dict) and str(session.get("status") or "").lower() in {"completed", "done", "cancelled", "merged"}
        for session in sessions
    ) and status_lines:
        risks.append(
            {
                "level": "warning",
                "title": "Mission runtime is closed but repo still has changes",
                "detail": "Review whether the current diff belongs to this mission or needs a new mission.",
            }
        )
    ownership = mission_state.get("files", {}).get("ownership.yaml", {})
    preview = str(ownership.get("preview") or "").lower()
    if "status: active" in preview and sessions and all(
        isinstance(session, dict) and str(session.get("status") or "").lower() in {"completed", "done", "cancelled", "merged"}
        for session in sessions
    ):
        risks.append(
            {
                "level": "info",
                "title": "Ownership status may be stale",
                "detail": "ownership.yaml still says active while runtime sessions are completed.",
            }
        )
    return risks


def collect_process_control(
    git: dict[str, Any],
    mission_state: dict[str, Any],
) -> dict[str, Any]:
    ownership_rules = mission_state.get("ownership_rules")
    if not isinstance(ownership_rules, dict):
        ownership_rules = {"tasks": {}, "shared_no_touch": []}

    runtime = mission_state.get("runtime")
    sessions = runtime.get("sessions", []) if isinstance(runtime, dict) else []
    active_sessions = [
        session
        for session in sessions
        if isinstance(session, dict)
        and str(session.get("status") or "").lower()
        in {"assigned", "running", "waiting", "blocked", "verification-failed", "report-ready"}
    ]
    missing_linear = [
        str(session.get("task_id") or session.get("id") or "unknown")
        for session in active_sessions
        if not str(session.get("linear_issue_id") or "").strip()
        or not str(session.get("linear_issue_url") or "").strip()
    ]

    status_entries = git.get("status_entries")
    if not isinstance(status_entries, list):
        status_entries = []

    active_mission_path = str(mission_state.get("path") or "").strip().rstrip("/")
    changed: list[dict[str, str]] = []
    counts = {
        "authorized": 0,
        "mission_state": 0,
        "orchestration_tooling": 0,
        "no_touch": 0,
        "unmanaged": 0,
    }

    for entry in status_entries:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        status = str(entry.get("status") or "")

        category = "unmanaged"
        task_id = ""
        detail = "Changed path is not covered by active mission ownership."

        forbidden_rule = no_touch_match(path, ownership_rules)
        owned = ownership_match(path, ownership_rules)
        if forbidden_rule:
            category = "no_touch"
            detail = f"Matches shared_no_touch rule: {forbidden_rule}"
        elif active_mission_path and (
            path_matches_rule(path, active_mission_path)
            or path_matches_rule(path, ".agents/orchestration/current")
        ):
            category = "mission_state"
            detail = "Active mission artifact change."
        elif owned:
            category = "authorized"
            task_id = owned["task_id"]
            detail = f"Covered by ownership rule: {owned['path_rule']}"
        elif path_matches_rule(path, ".agents/dashboard") or path_matches_rule(
            path,
            ".agents/skills/agent-orchestrator",
        ):
            category = "orchestration_tooling"
            detail = "Orchestration tooling change; create or link a tooling task if this is not intentional."

        counts[category] += 1
        changed.append(
            {
                "path": path,
                "status": status,
                "category": category,
                "task_id": task_id,
                "detail": detail,
            }
        )

    requires_orchestrator = bool(
        missing_linear
        or counts["unmanaged"]
        or counts["no_touch"]
        or (changed and not mission_state.get("active_mission_name"))
    )
    if missing_linear:
        gate = "blocked"
        summary = f"{len(missing_linear)} active task(s) are missing Linear."
    elif counts["no_touch"]:
        gate = "blocked"
        summary = f"{counts['no_touch']} changed path(s) match shared_no_touch."
    elif counts["unmanaged"]:
        gate = "attention"
        summary = f"{counts['unmanaged']} changed path(s) are not covered by active mission ownership."
    elif counts["orchestration_tooling"]:
        gate = "attention"
        summary = f"{counts['orchestration_tooling']} orchestration tooling path(s) changed outside product ownership."
    elif changed:
        gate = "ok"
        summary = "Changed paths are covered by active mission ownership or mission state."
    else:
        gate = "ok"
        summary = "No changed paths in git status."

    return {
        "gate": gate,
        "requires_orchestrator": requires_orchestrator,
        "summary": summary,
        "counts": counts,
        "changed": changed,
        "missing_linear_tasks": missing_linear,
    }


def run_git(repo: Path, *args: str) -> str:
    git = shutil.which("git")
    if git is None:
        return ""
    try:
        # Git path is resolved above; callers pass fixed read-only dashboard commands.
        result = subprocess.run(  # noqa: S603
            [str(Path(git).resolve()), *args],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def collect_git(repo: Path) -> dict[str, Any]:
    branch_status = run_git(repo, "status", "--short", "--branch")
    status = run_git(repo, "status", "--short").splitlines()
    name_only = run_git(repo, "diff", "--name-only").splitlines()
    stat = run_git(repo, "diff", "--stat")
    branch = run_git(repo, "branch", "--show-current")
    worktrees_raw = run_git(repo, "worktree", "list", "--porcelain")
    return {
        "available": bool(run_git(repo, "rev-parse", "--is-inside-work-tree")),
        "branch": branch or None,
        "branch_status": branch_status,
        "status": status,
        "status_entries": [parse_git_status_line(line) for line in status],
        "changed_files": name_only,
        "diff_stat": stat,
        "worktrees": parse_worktrees(worktrees_raw),
    }


def parse_worktrees(raw: str) -> list[dict[str, str]]:
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        worktrees.append(current)
    return worktrees


# --- Active mission resolution ---------------------------------------------

_ENG_ID_PATTERN = re.compile(r"ENG-\d+", re.IGNORECASE)
ORCHESTRATION_DIR_NAME = "orchestration"
ARCHIVED_DIR_NAME = "archived"


def detect_branch_eng_id(repo: Path) -> str | None:
    branch = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch:
        return None
    match = _ENG_ID_PATTERN.search(branch)
    return match.group(0).upper() if match else None


def iter_mission_candidates(repo: Path) -> list[Path]:
    root = repo / ".agents" / ORCHESTRATION_DIR_NAME
    if not root.is_dir():
        return []
    return [
        child
        for child in root.iterdir()
        if child.is_dir() and child.name != ARCHIVED_DIR_NAME
    ]


def find_mission_by_linear_id(repo: Path, eng_id: str) -> Path | None:
    eng_id_upper = eng_id.upper()
    for child in sorted(iter_mission_candidates(repo)):
        runtime_path = _paths.mission_runtime_dir(child.name) / "runtime.json"
        runtime = read_json(runtime_path)
        # Backward-compat: pre-M-1 missions kept runtime.json in repo.
        if not runtime:
            runtime = read_json(child / "runtime.json")
        if not isinstance(runtime, dict):
            continue
        for collection_name in ("sessions", "handoffs"):
            collection = runtime.get(collection_name)
            if not isinstance(collection, list):
                continue
            for entry in collection:
                if not isinstance(entry, dict):
                    continue
                value = str(entry.get("linear_issue_id") or "").upper()
                if value == eng_id_upper:
                    return child
    return None


def find_newest_mission(repo: Path) -> Path | None:
    candidates: list[tuple[float, Path]] = []
    for child in iter_mission_candidates(repo):
        try:
            candidates.append((child.stat().st_mtime, child))
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


def resolve_active_mission(
    repo: Path,
    override: Path | None,
) -> tuple[Path | None, str]:
    """Resolve the mission folder to display in the dashboard on each request.

    Order:
      1. explicit `--mission` override (always wins when provided);
      2. git branch ENG-\\d+ matched against runtime.json sessions/handoffs;
      3. newest mtime under .agents/orchestration/ (excluding archived/);
      4. nothing.
    """
    if override is not None:
        return override, "explicit --mission override"
    eng_id = detect_branch_eng_id(repo)
    if eng_id:
        match = find_mission_by_linear_id(repo, eng_id)
        if match is not None:
            return match, f"matched {eng_id} from git branch"
    newest = find_newest_mission(repo)
    if newest is not None:
        if eng_id:
            return (
                newest,
                f"no runtime.json mentions {eng_id}; fell back to newest mtime ({newest.name})",
            )
        return newest, f"newest mission by mtime ({newest.name})"
    return None, "no missions found under .agents/orchestration/ (excluding archived/)"


def list_markdown_items(root: Path, repo: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    items = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() not in {".md", ".json", ".yaml", ".yml"}:
            continue
        items.append(file_summary(path, repo))
    return items


def extract_decisions_from_text(path: Path, repo: Path) -> list[dict[str, str]]:
    text = read_text(path, limit=120_000)
    if not text:
        return []
    decisions = []
    for index, line in enumerate(text.splitlines(), start=1):
        normalized = line.lower()
        if should_ignore_decision_line(normalized):
            continue
        if any(marker in normalized for marker in DECISION_MARKERS):
            decisions.append(
                {
                    "source": relative_path(path, repo),
                    "line": str(index),
                    "text": line.strip()[:500],
                }
            )
    return decisions


def should_ignore_decision_line(normalized_line: str) -> bool:
    if "draft / needs decision / ready for orchestrator" in normalized_line:
        return True
    if "<" in normalized_line and ">" in normalized_line:
        return True
    return False


def collect_decision_inbox(mission: Path | None, strategy: Path, repo: Path) -> list[dict[str, str]]:
    sources: list[Path] = []
    if mission and mission.exists():
        sources.extend(path for path in mission.rglob("*") if path.is_file())
    if strategy.exists():
        sources.extend(path for path in strategy.rglob("*") if path.is_file())
    decisions: list[dict[str, str]] = []
    for path in sources:
        if path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() not in {".md", ".json", ".yaml", ".yml", ".txt"}:
            continue
        decisions.extend(extract_decisions_from_text(path, repo))
    return decisions[:100]


def collect_runtime_decisions(mission_state: dict[str, Any]) -> list[dict[str, str]]:
    runtime = mission_state.get("runtime")
    if not isinstance(runtime, dict):
        return []
    sessions = runtime.get("sessions")
    if not isinstance(sessions, list):
        return []

    active_statuses = {"assigned", "running", "waiting", "blocked", "verification-failed"}
    decisions: list[dict[str, str]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        status = str(session.get("status") or "").lower()
        if status not in active_statuses:
            continue
        linear_id = str(session.get("linear_issue_id") or "").strip()
        linear_url = str(session.get("linear_issue_url") or "").strip()
        if linear_id and linear_url:
            continue
        task_id = str(session.get("task_id") or session.get("id") or "unknown")
        decisions.append(
            {
                "source": f"{mission_state.get('path') or 'mission'}/runtime.json",
                "line": "0",
                "text": f"Missing Linear: active task {task_id} has no linked Linear issue id and URL.",
            }
        )
    return decisions


def collect_handoffs(mission_state: dict[str, Any]) -> list[dict[str, str]]:
    handoffs: list[dict[str, str]] = []
    runtime = mission_state.get("runtime")
    if isinstance(runtime, dict) and isinstance(runtime.get("handoffs"), list):
        for item in runtime["handoffs"]:
            if not isinstance(item, dict):
                continue
            handoffs.append(
                {
                    "id": str(item.get("id") or ""),
                    "created_at": str(item.get("created_at") or ""),
                    "task_id": str(item.get("task_id") or ""),
                    "linear_issue_id": str(item.get("linear_issue_id") or ""),
                    "from_role": str(item.get("from_role") or ""),
                    "from_agent": str(item.get("from_agent") or ""),
                    "to_role": str(item.get("to_role") or ""),
                    "to_agent": str(item.get("to_agent") or ""),
                    "reason": str(item.get("reason") or ""),
                    "status": str(item.get("status") or ""),
                    "source": f"{mission_state.get('path') or 'mission'}/runtime.json",
                }
            )

    for line in mission_state.get("runlog_tail") or []:
        if "handoff:" not in line.lower():
            continue
        handoffs.append(
            {
                "id": "",
                "created_at": line.split("|", 1)[0].lstrip("- ").strip(),
                "task_id": "",
                "linear_issue_id": "",
                "from_role": "",
                "from_agent": "",
                "to_role": "",
                "to_agent": "",
                "reason": line.strip(),
                "status": "logged",
                "source": f"{mission_state.get('path') or 'mission'}/runlog.md",
            }
        )
    return handoffs[-50:]


def collect_mission(
    mission: Path | None,
    reason: str,
    repo: Path,
) -> dict[str, Any]:
    active_name = mission.name if mission is not None else None
    if mission is None:
        return {
            "active_mission_name": None,
            "resolution_reason": reason,
            "configured": False,
            "exists": False,
            "path": None,
            "empty_state": f"No mission resolved: {reason}",
        }
    runtime_root = _paths.mission_runtime_dir(mission.name)
    files: dict[str, Any] = {}
    for name in SPEC_FILES:
        files[name] = file_summary(mission / name, repo)
    for name in RUNTIME_FILES:
        runtime_file = runtime_root / name
        if runtime_file.is_file():
            files[name] = file_summary(runtime_file, repo)
        else:
            # Backward-compat: pre-M-1 missions kept these files in repo.
            files[name] = file_summary(mission / name, repo)
    reports = list_markdown_items(mission / "reports", repo)
    runtime_path = runtime_root / "runtime.json"
    runtime = read_json(runtime_path)
    if not runtime:
        runtime = read_json(mission / "runtime.json")
    # M-3 enrichment: add derived runtime_status + agent_activity per session.
    if isinstance(runtime, dict) and isinstance(runtime.get("sessions"), list):
        for session in runtime["sessions"]:
            if not isinstance(session, dict):
                continue
            session["runtime_status"] = _pid_check.runtime_status(session.get("pid"))
            log_path = session.get("log_path")
            if log_path:
                session["agent_activity"] = _activity.activity_state(Path(log_path))
            else:
                session["agent_activity"] = "idle"
    runlog_path = runtime_root / "runlog.md"
    if not runlog_path.is_file():
        runlog_path = mission / "runlog.md"
    return {
        "active_mission_name": active_name,
        "resolution_reason": reason,
        "configured": True,
        "exists": mission.exists(),
        "path": relative_path(mission, repo),
        "runtime_path": str(runtime_root),
        "files": files,
        "reports": reports,
        "runtime": runtime,
        "ownership_rules": parse_ownership_rules(read_text(mission / "ownership.yaml")),
        "plan_checklist": collect_plan_checklist(mission, runtime_root, repo),
        "workflow": collect_workflow_control(mission, runtime_root, runtime, repo),
        "verification_control": collect_verification_control(mission, repo),
        "runlog_tail": tail_lines(runlog_path, limit=80),
        "empty_state": None
        if mission.exists()
        else "The resolved mission folder does not exist yet.",
    }


def collect_strategy(strategy: Path, repo: Path) -> dict[str, Any]:
    files = {name: file_summary(strategy / name, repo) for name in STRATEGY_FILES}
    directories = {name: file_summary(strategy / name, repo) for name in STRATEGY_DIRS}
    has_runtime_artifacts = any(item["exists"] for item in files.values()) or any(
        item["exists"] for item in directories.values()
    )
    return {
        "configured": True,
        "exists": strategy.exists(),
        "path": relative_path(strategy, repo),
        "files": files,
        "directories": directories,
        "items": list_markdown_items(strategy, repo),
        "empty_state": strategy_empty_state(strategy, has_runtime_artifacts),
    }


def strategy_empty_state(strategy: Path, has_runtime_artifacts: bool) -> str | None:
    if not strategy.exists():
        return "The strategy folder does not exist yet."
    if not has_runtime_artifacts:
        return "The strategy folder exists, but no strategy runtime artifacts exist yet."
    return None


def collect_orchestrator(repo: Path) -> dict[str, Any]:
    skill_root = repo / ".agents" / "skills" / "agent-orchestrator"
    scripts = sorted((skill_root / "scripts").glob("*.py")) if (skill_root / "scripts").is_dir() else []
    pycache = sorted((skill_root / "scripts" / "__pycache__").glob("*.pyc")) if (skill_root / "scripts" / "__pycache__").is_dir() else []
    return {
        "skill_path": relative_path(skill_root, repo),
        "exists": skill_root.exists(),
        "scripts": [relative_path(path, repo) for path in scripts],
        "pycache_traces": [relative_path(path, repo) for path in pycache],
        "empty_state": None
        if scripts
        else "No orchestrator source scripts are present. Only runtime files that exist on disk will be shown.",
    }


def build_snapshot(config: DashboardConfig) -> dict[str, Any]:
    mission_path, mission_reason = resolve_active_mission(config.repo, config.mission)
    mission = collect_mission(mission_path, mission_reason, config.repo)
    strategy = collect_strategy(config.strategy, config.repo)
    decisions = collect_decision_inbox(mission_path, config.strategy, config.repo)
    decisions.extend(collect_runtime_decisions(mission))
    handoffs = collect_handoffs(mission)
    git = collect_git(config.repo)
    process_control = collect_process_control(git, mission)
    return {
        "generated_at": utc_now(),
        "repo": {
            "path": str(config.repo),
            "dashboard": relative_path(DASHBOARD_ROOT, config.repo),
        },
        "mission": mission,
        "strategy": strategy,
        "orchestrator": collect_orchestrator(config.repo),
        "handoffs": handoffs,
        "decisions": decisions[:100],
        "git": git,
        "process_control": process_control,
        "git_risks": collect_git_risks(git, mission),
    }


# --- /api/live helpers ------------------------------------------------------


def _run_capture(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a command with timeout; never raise. Returns (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv list, no user input.
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return 1, "", str(exc)


def _collect_recent_commits(window_hours: int = 24, limit: int = 20) -> list[dict[str, str]]:
    """Recent commits across all refs in a time window."""
    fmt = "%H%x1f%h%x1f%ai%x1f%an%x1f%s%x1f%D"
    code, out, _err = _run_capture([
        "git",
        "log",
        "--all",
        f"--since={window_hours} hours ago",
        f"-n{limit}",
        f"--format={fmt}",
    ])
    if code != 0:
        return []
    rows: list[dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) < 6:
            continue
        full_sha, short_sha, iso, author, subject, refs = parts[:6]
        rows.append(
            {
                "sha": full_sha,
                "short": short_sha,
                "committed_at": iso,
                "author": author,
                "subject": subject,
                "refs": refs.strip(),
            }
        )
    return rows


def _collect_pull_requests() -> tuple[list[dict[str, Any]], str | None]:
    """Open PRs with CI status via `gh pr list`. Returns (list, error_message)."""
    if shutil.which("gh") is None:
        return [], "gh CLI not available"
    code, out, err = _run_capture(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "20",
            "--json",
            "number,title,headRefName,isDraft,updatedAt,createdAt,statusCheckRollup,url,author",
        ],
        timeout=15,
    )
    if code != 0:
        return [], f"gh exited {code}: {err.strip()[:200] or 'no stderr'}"
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        return [], f"gh output parse failed: {exc}"
    rows: list[dict[str, Any]] = []
    for pr in data:
        checks = pr.get("statusCheckRollup") or []
        summary = {"pass": 0, "fail": 0, "pending": 0, "skip": 0}
        for c in checks:
            conclusion = (c.get("conclusion") or c.get("state") or "").upper()
            if conclusion in {"SUCCESS"}:
                summary["pass"] += 1
            elif conclusion in {"FAILURE", "TIMED_OUT", "CANCELLED"}:
                summary["fail"] += 1
            elif conclusion in {"SKIPPED", "NEUTRAL"}:
                summary["skip"] += 1
            else:
                summary["pending"] += 1
        rollup = (
            "fail" if summary["fail"] else "pending" if summary["pending"] else "pass" if summary["pass"] else "none"
        )
        rows.append(
            {
                "number": pr.get("number"),
                "title": pr.get("title", ""),
                "headRefName": pr.get("headRefName", ""),
                "isDraft": bool(pr.get("isDraft")),
                "updatedAt": pr.get("updatedAt", ""),
                "createdAt": pr.get("createdAt", ""),
                "url": pr.get("url", ""),
                "author": (pr.get("author") or {}).get("login", ""),
                "checks": summary,
                "checks_rollup": rollup,
            }
        )
    return rows, None


def build_live_activity(_config: DashboardConfig) -> dict[str, Any]:
    """Recent commits + open PRs with CI status. Cached for LIVE_TTL_SECONDS."""
    now = datetime.now(UTC).timestamp()
    if (
        _live_cache.get("payload") is not None
        and now - float(_live_cache.get("generated_at", 0.0)) < LIVE_TTL_SECONDS
    ):
        return _live_cache["payload"]

    errors: list[str] = []
    commits = _collect_recent_commits()
    if not commits:
        # Could be: no recent commits, or git failed silently. Distinguish by
        # checking if git is available at all.
        if shutil.which("git") is None:
            errors.append("git CLI not available")

    pull_requests, pr_error = _collect_pull_requests()
    if pr_error:
        errors.append(pr_error)

    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ttl_seconds": LIVE_TTL_SECONDS,
        "commits": commits,
        "pull_requests": pull_requests,
        "errors": errors,
    }
    _live_cache["payload"] = payload
    _live_cache["generated_at"] = now
    return payload


# --- end /api/live helpers --------------------------------------------------


def _read_jsonl_tail(path: Path, max_lines: int = 200) -> list[dict[str, Any]]:
    """Read last ``max_lines`` JSONL entries from a file. Best-effort."""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-max_lines:]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def _codex_recent_events(
    project_cwd: str,
    *,
    hours: int = 24,
    max_per_session: int = 50,
) -> list[dict[str, Any]]:
    """Pull recent codex session events relevant to this project.

    Codex writes one JSONL per session under
    ``~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl``. We tail the most
    recent files modified within the last ``hours`` and filter to events
    whose ``payload.cwd`` (or session_meta cwd) is inside ``project_cwd``.
    """
    sessions_root = Path.home() / ".codex" / "sessions"
    if not sessions_root.exists():
        return []
    cutoff = datetime.now(UTC).timestamp() - hours * 3600
    recent_files: list[Path] = []
    for path in sessions_root.rglob("rollout-*.jsonl"):
        try:
            if path.stat().st_mtime >= cutoff:
                recent_files.append(path)
        except OSError:
            continue
    recent_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    recent_files = recent_files[:10]

    out: list[dict[str, Any]] = []
    proj = str(Path(project_cwd).resolve())
    for path in recent_files:
        session_id = path.stem.split("-")[-1] if "-" in path.stem else path.stem
        session_cwd: str | None = None
        for entry in _read_jsonl_tail(path, max_lines=max_per_session):
            etype = entry.get("type", "")
            payload = entry.get("payload") or {}
            ts = entry.get("timestamp", "")
            if etype == "session_meta":
                session_cwd = payload.get("cwd")
                if session_cwd and not str(Path(session_cwd).resolve()).startswith(proj):
                    break  # different project — skip this whole session
                continue
            if session_cwd and not str(Path(session_cwd).resolve()).startswith(proj):
                continue
            # Summarise event for display
            tool = ""
            target = ""
            if etype == "response_item":
                content = payload.get("content")
                if isinstance(content, dict):
                    tool = str(content.get("type", "response"))[:40]
                    target = str(content.get("name", ""))[:120]
                elif isinstance(content, list) and content:
                    first = content[0] if isinstance(content[0], dict) else {}
                    tool = str(first.get("type", "response"))[:40]
                    target = str(first.get("text", first.get("name", "")))[:120]
                else:
                    tool = "response_item"
                    target = ""
            elif etype == "event_msg":
                tool = str(payload.get("type", "event"))[:40]
                msg = payload.get("message") or payload.get("text") or ""
                target = str(msg)[:120]
            else:
                tool = etype[:40]
            out.append({
                "ts": ts,
                "agent": "codex",
                "session": session_id[:8],
                "event": etype,
                "tool": tool,
                "target": target,
                "cwd": session_cwd or "",
            })
    return out


def build_activity_feed(config: DashboardConfig) -> dict[str, Any]:
    """Aggregate live activity from Claude Code hook log + Codex sessions."""
    project_cwd = str(config.repo)
    # Repo-hash directory mirrors paths.py: SHA256(cwd)[:12]
    import hashlib
    repo_hash = hashlib.sha256(project_cwd.encode()).hexdigest()[:12]
    log_path = Path.home() / ".fusion-agent-orchestrator" / repo_hash / "live-activity.jsonl"

    claude_events = _read_jsonl_tail(log_path, max_lines=200)
    codex_events = _codex_recent_events(project_cwd, hours=4, max_per_session=80)

    combined = claude_events + codex_events

    def _sort_key(e: dict[str, Any]) -> str:
        return str(e.get("ts", ""))

    combined.sort(key=_sort_key, reverse=True)
    combined = combined[:150]

    # Group by session for the UI
    sessions: dict[str, dict[str, Any]] = {}
    for e in combined:
        key = f"{e.get('agent', '?')}::{e.get('session', '') or 'main'}"
        if key not in sessions:
            sessions[key] = {
                "key": key,
                "agent": e.get("agent", "?"),
                "session": e.get("session", "") or "main",
                "last_ts": e.get("ts", ""),
                "event_count": 0,
                "events": [],
            }
        sess = sessions[key]
        sess["event_count"] += 1
        if len(sess["events"]) < 20:
            sess["events"].append(e)

    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "total_events": len(combined),
        "sessions": list(sessions.values()),
        "recent": combined[:50],
    }


# --- end /api/activity helpers ---------------------------------------------


class DashboardHandler(BaseHTTPRequestHandler):
    config: DashboardConfig

    def do_GET(self) -> None:
        self.route_request(send_body=True)

    def do_HEAD(self) -> None:
        self.route_request(send_body=False)

    def route_request(self, send_body: bool) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/snapshot":
            self.send_json(build_snapshot(self.config), send_body=send_body)
            return
        if parsed.path == "/api/logs":
            self.send_logs(parsed.query, send_body=send_body)
            return
        if parsed.path == "/api/live":
            self.send_json(build_live_activity(self.config), send_body=send_body)
            return
        if parsed.path == "/api/activity":
            self.send_json(build_activity_feed(self.config), send_body=send_body)
            return
        self.send_static(parsed.path, send_body=send_body)

    def send_logs(self, query: str, send_body: bool) -> None:
        params = parse_qs(query)
        target = params.get("target", ["runlog"])[0]
        try:
            lines = int(params.get("lines", ["80"])[0])
        except ValueError:
            lines = 80
        lines = max(1, min(lines, 500))
        mission_path, _reason = resolve_active_mission(self.config.repo, self.config.mission)
        if target != "runlog" or mission_path is None:
            self.send_json({"target": target, "lines": []}, send_body=send_body)
            return
        runtime_runlog = _paths.mission_runtime_dir(mission_path.name) / "runlog.md"
        runlog_path = runtime_runlog if runtime_runlog.is_file() else mission_path / "runlog.md"
        self.send_json(
            {
                "target": target,
                "path": str(runlog_path),
                "lines": tail_lines(runlog_path, lines),
            },
            send_body=send_body,
        )

    def send_static(self, request_path: str, send_body: bool) -> None:
        if request_path in {"", "/"}:
            request_path = "/index.html"
        relative = unquote(request_path.lstrip("/"))
        path = (STATIC_ROOT / relative).resolve()
        if not str(path).startswith(str(STATIC_ROOT.resolve())) or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(path.suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def send_json(self, payload: Any, send_body: bool) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the read-only agent dashboard.")
    parser.add_argument("--mission", type=Path, help="Optional mission folder to inspect.")
    parser.add_argument(
        "--strategy",
        type=Path,
        default=REPO_ROOT / ".agents" / "strategy",
        help="Strategy folder to inspect.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8787, help="Bind port.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    host = args.host
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Refusing to bind outside localhost. Use 127.0.0.1.")
    mission = args.mission.resolve() if args.mission else None
    strategy = args.strategy.resolve()
    config = DashboardConfig(
        host=host,
        port=args.port,
        mission=mission,
        strategy=strategy,
        repo=REPO_ROOT,
    )
    DashboardHandler.config = config
    server = ThreadingHTTPServer((config.host, config.port), DashboardHandler)
    print(f"Agent dashboard: http://{config.host}:{config.port}")
    print("Mode: read-only")
    print(f"Repository: {config.repo}")
    if config.mission:
        print(f"Mission: {config.mission}")
    print(f"Strategy: {config.strategy}")
    server.serve_forever()


if __name__ == "__main__":
    main()
