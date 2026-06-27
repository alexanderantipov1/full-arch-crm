# Linear Orchestration

Use this template when turning a business task into a daily sprint and Linear project/issues.

## Business Intake

Business task:
User / customer impact:
Deadline:
Priority:
Risk:

## Mission

Mission title:
Done condition:
Verification gate:
Release target:

## Linear Project / Parent Issue

Team:
Project:
Parent issue:
Labels:
Milestone/cycle:

## Issue Decomposition

| Task | Linear Issue | Title | Type | Priority | Risk | Wave | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | TBD | Backend/API | feature | high | medium | Wave 1 | worker | Ready |

## Subissue Rules

- Use subissues for agent-executable tasks with clear ownership.
- Keep cross-cutting contract decisions in the parent issue or project.
- Create separate issues for blockers discovered during execution.
- Do not close implementation issues before integration and verification are complete.

## Sync Rules

- Confirm actual Linear team status names before syncing.
- Worker report `complete` -> Linear `Needs Integration` unless the issue is read-only.
- Worker report `blocked` -> Linear `Blocked` with blocker comment.
- Integration complete -> Linear `In Review`.
- Verification pass -> Linear `Verified`.
- Release done or explicitly deferred -> Linear `Done`.

## End-of-Day Update

- Update issue statuses.
- Comment concise progress on parent issue/project.
- Move unfinished tasks to the next daily sprint or backlog.
- Generate `handoff.md`.
