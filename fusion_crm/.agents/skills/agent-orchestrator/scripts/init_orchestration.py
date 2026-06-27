#!/usr/bin/env python3
"""Create a coordination folder for parallel terminal-agent work."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
REFERENCE_TEMPLATE_DIR = SCRIPT_DIR.parent / "references"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:64] or "mission"


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.write_text(content, encoding="utf-8")


def read_reference_template(name: str) -> str:
    return (REFERENCE_TEMPLATE_DIR / name).read_text(encoding="utf-8")


def build_mission(title: str) -> str:
    return f"""# Mission: {title}

## Outcome

- Define the target outcome before launching agents.

## Constraints

- Record repository rules, architecture constraints, and prohibited changes.

## Current State

- Capture git status, active servers, known dirty files, and open risks.

## Waves

### Wave 1

- Planned:
- Running:
- Complete:
- Blocked:

## Decisions

- Record orchestration decisions and why tasks are sequenced or parallelized.
"""


def build_board() -> str:
    return """# Agent Orchestration Board

| Task | Linear Issue | Role | Owner | Branch | Worktree | Status | Write Scope | Depends On | Report |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | TBD | worker | terminal-1 | agent/mission-A1 | ../Fusion_crm-A1 | planned | TBD | none | reports/A1.md |

## File Ownership

| Path / Module | Owner | Status | Notes |
| --- | --- | --- | --- |
| TBD | TBD | planned | |

## Blockers

- None.
"""


def build_backlog() -> str:
    return """# Mission Backlog

## Intake Queue

| ID | Title | Type | Priority | Risk | Area | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| I1 | TBD | feature | normal | medium | TBD | intake | |

## Backlog Item Template

ID:
Title:
Type: feature | bug | refactor | infra | research
Priority: blocker | high | normal | later
Risk: low | medium | high
Area:
Expected files:
Dependencies:
Acceptance criteria:
Linear issue:
"""


def build_daily_sprint() -> str:
    return """# Daily Sprint Plan

Date:
Mission:
Linear project:

## Sprint Goal

- TBD

## Capacity

| Role | Count | Notes |
| --- | --- | --- |
| Orchestrator | 1 | planning, Linear sync, reviews |
| Workers | TBD | implementation/exploration |
| Integrator | 1 | merge/conflict owner |
| Verifier | 1 | verification gate |

## Planned Waves

| Wave | Goal | Tasks | Launch Window | Integration Point | Status |
| --- | --- | --- | --- | --- | --- |
| Wave 1 | TBD | A1, A2 | morning | midday | planned |

## Decision Windows

- Morning planning:
- Midday report review:
- Afternoon integration:
- End-of-day handoff:

## Done Criteria

- TBD
"""


def build_goal() -> str:
    return """# Goal

## Outcome

- TBD

## Business Value

- TBD

## Non-Goals

- TBD
"""


def build_acceptance() -> str:
    return """# Acceptance

- [ ] Acceptance item 1.
- [ ] Acceptance item 2.
"""


def build_verification() -> str:
    return """# Verification

## Focused Checks

- [ ] TBD

## Full Repository Checks

- [ ] `make lint`
- [ ] `mypy .`
- [ ] `make test`
- [ ] `cd packages/db && alembic check`
"""


def build_linear_sync() -> str:
    return """# Linear Sync

## Policy

- The orchestrator creates and moves Linear issues.
- Workers do not create, split, close, or reprioritize Linear issues.
- Workers may reference the assigned Linear issue in reports.
- Mission folder remains the technical source of truth; Linear is the project board.

## Project / Epic

Linear team:
Linear project:
Parent issue:

## Status Mapping

| Orchestration Status | Linear Status |
| --- | --- |
| intake | Backlog |
| planned | Ready |
| running | In Progress |
| blocked | Blocked |
| needs-integration | Needs Integration |
| reviewing | In Review |
| verified | Verified |
| done | Done |

## Issue Map

| Task | Linear Issue | Title | Status | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| A1 | TBD | TBD | Ready | TBD | |

## Sync Log

- TBD
"""


def build_contract() -> str:
    return """# Contract

## Shared Interfaces

- TBD

## Invariants

- No product code may depend on `.agents`.
- Do not touch `.env*`, shipped migrations, deploy scripts, or secrets.

## Risks

- TBD
"""


def build_ownership() -> str:
    return """# Ownership

## Write Scopes

| Task | Owner | Paths | Notes |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |

## Shared No-Touch

- TBD
"""


def build_ownership_yaml() -> str:
    return """mission: TBD
status: draft
tasks: {}
shared_no_touch: []
"""


def build_decision_log() -> str:
    return """# Decision Log

- TBD
"""


def build_runlog() -> str:
    return """# Runlog

- TBD
"""


def build_task_template() -> str:
    return read_reference_template("task-brief-template.md")


def build_report_template() -> str:
    return read_reference_template("report-template.md")


def build_incidents() -> str:
    return """# Incidents

- None recorded.
"""


def build_lessons() -> str:
    return """# Lessons

- TBD
"""


def build_integration_plan() -> str:
    return read_reference_template("integration-plan-template.md")


def build_plan_checklist() -> str:
    return read_reference_template("plan-checklist-template.md")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a mission folder for parallel terminal-agent orchestration."
    )
    parser.add_argument("title", help="Short mission title")
    parser.add_argument(
        "--root",
        default=".agents/orchestration",
        help="Base directory for orchestration folders",
    )
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    mission_dir = Path(args.root) / f"{stamp}-{slugify(args.title)}"
    mission_dir.mkdir(parents=True, exist_ok=False)

    for child in ("tasks", "reports", "locks"):
        (mission_dir / child).mkdir()

    write_new(mission_dir / "mission.md", build_mission(args.title))
    write_new(mission_dir / "backlog.md", build_backlog())
    write_new(mission_dir / "daily-sprint.md", build_daily_sprint())
    write_new(mission_dir / "PLAN_CHECKLIST.md", build_plan_checklist())
    write_new(mission_dir / "goal.md", build_goal())
    write_new(mission_dir / "acceptance.md", build_acceptance())
    write_new(mission_dir / "verification.md", build_verification())
    write_new(mission_dir / "linear-sync.md", build_linear_sync())
    write_new(mission_dir / "contract.md", build_contract())
    write_new(mission_dir / "ownership.md", build_ownership())
    write_new(mission_dir / "ownership.yaml", build_ownership_yaml())
    write_new(mission_dir / "board.md", build_board())
    write_new(mission_dir / "integration-plan.md", build_integration_plan())
    write_new(mission_dir / "decision-log.md", build_decision_log())
    write_new(mission_dir / "runlog.md", build_runlog())
    write_new(mission_dir / "incidents.md", build_incidents())
    write_new(mission_dir / "lessons.md", build_lessons())
    write_new(mission_dir / "tasks" / "TEMPLATE.md", build_task_template())
    write_new(mission_dir / "reports" / "TEMPLATE.md", build_report_template())
    write_new(
        mission_dir / "locks" / "README.txt",
        "Optional human-readable file ownership notes. These are coordination hints, not OS locks.\n",
    )

    print(mission_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
