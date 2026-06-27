#!/usr/bin/env python3
"""Generate a mission PLAN_CHECKLIST.md draft from orchestration artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]

sys.path.insert(0, str(SCRIPT_DIR))
import paths as _paths  # noqa: E402

HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")
NUMBERED_RE = re.compile(r"^\s*\d+\.\s+(?P<text>.+)$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>.+)$")
TABLE_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path, *, limit: int = 120_000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def load_json(path: Path) -> dict[str, Any]:
    text = read_text(path)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def runtime_file(mission_dir: Path, name: str) -> Path:
    runtime_path = _paths.mission_runtime_dir(mission_dir.name) / name
    return runtime_path if runtime_path.is_file() else mission_dir / name


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def strip_md_link(value: str) -> str:
    return TABLE_LINK_RE.sub(r"\1", value)


def parse_first_table(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    index = 0
    while index < len(lines) - 1:
        header = lines[index].strip()
        separator = lines[index + 1].strip()
        if not (header.startswith("|") and separator.startswith("|")):
            index += 1
            continue
        headers = [cell.strip() for cell in header.strip("|").split("|")]
        separators = [cell.strip() for cell in separator.strip("|").split("|")]
        if len(headers) != len(separators):
            index += 1
            continue
        if not all(set(cell.replace(":", "").strip()) <= {"-"} for cell in separators):
            index += 1
            continue
        rows: list[dict[str, str]] = []
        index += 2
        while index < len(lines) and lines[index].strip().startswith("|"):
            values = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
            if len(values) == len(headers):
                rows.append(dict(zip(headers, values, strict=False)))
            index += 1
        return rows
    return []


def acceptance_items(text: str) -> list[str]:
    items: list[str] = []
    current = ""
    for line in text.splitlines():
        match = NUMBERED_RE.match(line)
        if match:
            if current:
                items.append(current.strip())
            current = match.group("text").strip()
            continue
        if current and line.startswith(("  ", "\t")):
            current += " " + line.strip()
    if current:
        items.append(current.strip())
    if items:
        return items

    for line in text.splitlines():
        match = BULLET_RE.match(line)
        if match:
            items.append(match.group("text").strip())
    return items


def verification_items(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        match = BULLET_RE.match(line)
        if not match:
            continue
        item = match.group("text").strip()
        if "`" in item or any(token in item.lower() for token in ("make ", "mypy", "pytest", "alembic", "npm", "npx", "smoke")):
            items.append(item)
    return items


def goal_excerpt(text: str, *, max_lines: int = 22) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("# "):
            continue
        lines.append(line)
        if len(lines) >= max_lines:
            break
    excerpt = "\n".join(lines).strip()
    return excerpt or "_No mission goal text found._"


def section_titles(text: str) -> list[str]:
    titles = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            titles.append(match.group("title").strip())
    return titles


def task_rows(mission_dir: Path, runtime: dict[str, Any]) -> list[dict[str, str]]:
    board_rows = parse_first_table(read_text(runtime_file(mission_dir, "board.md")))
    if board_rows:
        return board_rows

    sessions = runtime.get("sessions")
    if not isinstance(sessions, list):
        return []
    rows = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        rows.append(
            {
                "Task": str(session.get("task_id") or ""),
                "Linear": str(session.get("linear_issue_id") or ""),
                "Status": str(session.get("status") or ""),
                "Owner": f"{session.get('role') or ''}/{session.get('agent') or ''}".strip("/"),
                "Notes": str(session.get("current_note") or session.get("phase") or ""),
            }
        )
    return rows


def mission_completed(runtime: dict[str, Any], rows: list[dict[str, str]]) -> bool:
    sessions = runtime.get("sessions")
    if isinstance(sessions, list) and sessions:
        terminal = {"completed", "done", "cancelled", "merged"}
        return all(
            isinstance(session, dict)
            and str(session.get("status") or "").lower() in terminal
            for session in sessions
        )
    if rows:
        return all(
            str(row.get("Status") or row.get("status") or "").lower() in {"done", "completed", "merged"}
            for row in rows
        )
    return False


def checkbox(done: bool, text: str) -> str:
    mark = "x" if done else " "
    return f"- [{mark}] {text}"


def render_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "| Task | Linear | Status | Owner | Notes |\n| --- | --- | --- | --- | --- |\n| TBD | TBD | Planned | TBD | No task board found. |"
    headers = list(rows[0].keys())
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(out)


def render_dag(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "```text\nNo task DAG available yet.\n```"
    node_lines = []
    previous = ""
    for row in rows:
        task = strip_md_link(row.get("Task") or row.get("task") or "TASK")
        label = strip_md_link(row.get("Linear") or row.get("Title") or row.get("Notes") or task)
        node = re.sub(r"[^A-Za-z0-9_]", "_", task).strip("_") or "TASK"
        node_lines.append(f'  {node}["{task}: {label[:80]}"]')
        if previous:
            node_lines.append(f"  {previous} --> {node}")
        previous = node
    return "```mermaid\nflowchart TD\n" + "\n".join(node_lines) + "\n```"


def find_strategy_context(strategy_path: Path, mission_name: str, goal_text: str) -> str:
    text = read_text(strategy_path, limit=220_000)
    if not text:
        return "_No strategy handoff file found._"
    needles = {mission_name.lower()}
    for line in goal_text.splitlines():
        cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", line).strip().lower()
        if 18 <= len(cleaned) <= 90:
            needles.add(cleaned[:60])
            break
    lowered = text.lower()
    if not any(needle and needle in lowered for needle in needles):
        return "_No matching strategy handoff section found._"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if any(needle and needle in line.lower() for needle in needles):
            start = index
            while start > 0 and not lines[start].startswith("### "):
                start -= 1
            end = start + 1
            while end < len(lines) and not lines[end].startswith("### "):
                end += 1
            return "\n".join(lines[start:end]).strip()[:8000]
    return "_No matching strategy handoff section found._"


def strategy_lineage(
    *,
    mission_name: str,
    goal_text: str,
    candidate_path: Path,
    handoff_path: Path,
    rows: list[dict[str, str]],
) -> str:
    candidate_context = find_strategy_context(candidate_path, mission_name, goal_text)
    handoff_context = find_strategy_context(handoff_path, mission_name, goal_text)
    parent = ""
    for row in rows:
        task = strip_md_link(row.get("Task") or row.get("task") or "")
        if task:
            parent = task
            break
    return f"""- Strategy Agent candidate source: `{relative(candidate_path) if candidate_path.is_file() else candidate_path}` — {"matched" if not candidate_context.startswith("_No matching") else "not matched"}
- Strategy Agent handoff source: `{relative(handoff_path) if handoff_path.is_file() else handoff_path}` — {"matched" if not handoff_context.startswith("_No matching") else "not matched"}
- Orchestrator execution mission: `{mission_name}`
- Linear parent / first task: `{parent or "TBD"}`
- Rule: Strategy proposes, Orchestrator disposes. This checklist is execution control, not a replacement for strategy artifacts."""


def build_plan(
    mission_dir: Path,
    *,
    strategy_path: Path,
    candidate_path: Path,
) -> str:
    runtime_path = runtime_file(mission_dir, "runtime.json")
    runtime = load_json(runtime_path)
    goal_text = read_text(mission_dir / "goal.md")
    acceptance_text = read_text(mission_dir / "acceptance.md")
    contract_text = read_text(mission_dir / "contract.md")
    verification_text = read_text(mission_dir / "verification.md")
    rows = task_rows(mission_dir, runtime)
    done = mission_completed(runtime, rows)
    acceptance = acceptance_items(acceptance_text)
    verification = verification_items(verification_text)
    contract_sections = section_titles(contract_text)
    strategy_context = find_strategy_context(strategy_path, mission_dir.name, goal_text)
    lineage = strategy_lineage(
        mission_name=mission_dir.name,
        goal_text=goal_text,
        candidate_path=candidate_path,
        handoff_path=strategy_path,
        rows=rows,
    )

    acceptance_block = "\n".join(checkbox(done, item) for item in acceptance) or "- [ ] No acceptance criteria found."
    verification_block = "\n".join(checkbox(False, item) for item in verification) or "- [ ] No verification commands found."
    task_block = "\n".join(
        checkbox(
            str(row.get("Status") or row.get("status") or "").lower() in {"done", "completed", "merged"},
            f"{strip_md_link(row.get('Task') or row.get('task') or 'Task')} — {strip_md_link(row.get('Linear') or row.get('Notes') or '')}".strip(" —"),
        )
        for row in rows
    ) or "- [ ] Create or sync Linear-backed tasks."

    sources = [
        mission_dir / "goal.md",
        mission_dir / "acceptance.md",
        mission_dir / "contract.md",
        mission_dir / "verification.md",
        mission_dir / "ownership.yaml",
        runtime_file(mission_dir, "board.md"),
        runtime_file(mission_dir, "linear-sync.md"),
        runtime_path,
    ]
    source_lines = "\n".join(
        f"- `{relative(path) if str(path).startswith(str(REPO_ROOT)) else path}`"
        for path in sources
        if path.is_file()
    )

    return f"""# Plan Checklist — {mission_dir.name}

Generated: {utc_now()}
Mission: `{mission_dir.name}`
Status: {"completed" if done else "draft / active"}
Primary source: `{relative(mission_dir)}`

## Business Goal

{goal_excerpt(goal_text)}

## Source Of Truth

{source_lines or "- No mission source files found."}

## Strategic Lineage

{lineage}

## Strategy Context

{strategy_context}

## Implementation Plan

{task_block}
- [ ] Keep `runtime.json`, `board.md`, `linear-sync.md`, `runlog.md`, and worker reports synchronized with actual progress.
- [ ] Update this `PLAN_CHECKLIST.md` after each worker wave, verification pass, or scope change.

## Acceptance Checklist

{acceptance_block}

## Contract Checklist

{chr(10).join(checkbox(done, f"Contract section present: {title}") for title in contract_sections) or "- [ ] No contract sections found."}

## Implementation DAG / Waves

{render_dag(rows)}

## Linear Map

{render_table(rows)}

## Ownership / Write Scopes

Review `{relative(mission_dir / "ownership.yaml")}` before launching or self-executing work.

- [ ] Every active execution task has a Linear issue id and URL.
- [ ] Every worker has an allowed write scope.
- [ ] No worker edits `.env*`, shipped Alembic revisions, or out-of-scope files.
- [ ] Concurrent work is isolated or explicitly recorded as self-execute scope.

## Verification Gate

{verification_block}

## Open Risks

- [ ] Confirm whether this mission needs a Strategy handoff entry or whether the mission spec is the accepted scope.
- [ ] Confirm dashboard/runtime state points at this mission before launching workers.
- [ ] Confirm no unrelated dirty files are mixed into the mission diff.
- [ ] Record blockers with exact markers: `Blocked:`, `Needs decision:`, `Needs approval:`, `Verification failed:`.

## Resume Prompt

Use the Fusion CRM Orchestrator protocol. Read this `PLAN_CHECKLIST.md` first,
then inspect `goal.md`, `acceptance.md`, `contract.md`, `verification.md`,
`ownership.yaml`, runtime `board.md`, `linear-sync.md`, `runlog.md`,
`incidents.md`, `decision-log.md`, and worker reports. Update checklist boxes
only when evidence exists in mission files, runtime files, Linear, git, or
verification output. Do not infer progress from terminal-only claims.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate PLAN_CHECKLIST.md for a Fusion CRM orchestration mission."
    )
    parser.add_argument(
        "--mission-folder",
        default=str(REPO_ROOT / ".agents" / "orchestration" / "current"),
        help="Mission spec folder. Defaults to .agents/orchestration/current.",
    )
    parser.add_argument(
        "--strategy-file",
        default=str(REPO_ROOT / ".agents" / "strategy" / "HANDOFF_TO_ORCHESTRATOR.md"),
        help="Strategy handoff file used for optional context.",
    )
    parser.add_argument(
        "--candidate-file",
        default=str(REPO_ROOT / ".agents" / "strategy" / "CANDIDATE_MISSIONS.md"),
        help="Strategy candidate mission file used for lineage.",
    )
    parser.add_argument(
        "--output",
        default="PLAN_CHECKLIST.md",
        help="Output filename relative to mission folder, or absolute path.",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    mission_dir = Path(args.mission_folder).resolve()
    if not mission_dir.is_dir():
        raise SystemExit(f"mission folder does not exist: {mission_dir}")
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = mission_dir / output_path
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"refusing to overwrite existing file: {output_path}")

    content = build_plan(
        mission_dir,
        strategy_path=Path(args.strategy_file).resolve(),
        candidate_path=Path(args.candidate_file).resolve(),
    )
    output_path.write_text(content, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
