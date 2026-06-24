# Terminal Agent Report

Task ID:
Linear issue:
Agent role:
Task class: normal | tiny_fix | hotfix | contract_change
Status: complete | partial | blocked | failed
Branch:
Worktree:

## Summary

One or two sentences describing what changed or what was learned.

## Files Changed

- `path`: short reason

## Ownership Card

- Owned paths:
- Shared paths declared:
- Shared paths touched:
- Forbidden paths touched:
- Integration mode:
- Requires Integrator review:
- Requires cross-runtime review:
- Reviewer runtime:
- Cross-runtime reviewer report:
- Main advanced during work: yes/no
- Sync performed after main advanced: yes/no/not needed
- Context rollover trigger observed: yes/no
- Context rollover handoff written or explicitly deferred: yes/no/not needed

## Git State

- Current branch:
- Dirty files:
- Commits made:
- Push status:
- Draft PR URL:

## Tests / Checks

- Command: result

## Goal Evidence

- Evidence this task contributes to `goal.md`:
- Missing evidence:

## Ownership Notes

- Confirm whether all edits stayed within the assigned write scope.
- List any files touched outside scope and why.
- Confirm whether the work followed `contract.md`.
- List any requested contract or shared path changes.
- If task class is `tiny_fix`, confirm no contract/API/schema/tool/read-model/date-time/deploy/env behavior changed.
- If autonomous PR prep was used, confirm only task-owned files were staged and
  unrelated dirty/untracked files were preserved.
- If task class is `hotfix`, list affected active workers or paths that need `sync_required`.
- If the task is large, high-risk, or `contract_change`, confirm the
  cross-runtime review requirement and reviewer runtime.

## Linear Notes

- Recommended Linear status:
- Comment/update for orchestrator to post:
- New issues suggested:

## Blockers

- None, or list concrete blockers.

## Integration Risks

- None, or list conflicts, migrations, shared behavior, missing tests, or follow-up review needs.

## Process / Lesson Notes

- Any workflow mistake, unclear brief, missing setup, or reusable lesson candidate:

## Suggested Next Tasks

- Small, specific follow-ups the orchestrator can schedule.

## Context Rollover

- Trigger: none | major merge | large PR boundary | mission direction change | context compaction | budget exhaustion
- Handoff summary location or message:
- Fresh thread/mission recommendation:
