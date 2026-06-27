# ENG-254 Worker Report

## Task

- Linear: ENG-254
- Title: Wire person detail to operational timeline
- Role: Orchestrator self-execute
- Agent: Codex
- Branch: main
- Worktree: current checkout

## Changed Files

- `apps/web/components/person/Timeline.tsx`
- `apps/web/app/(staff)/persons/[uid]/page.tsx`

## Result

Person detail now reads `GET /persons/{uid}/operational-timeline` through the
existing `usePersonOperationalTimeline` hook and renders normalized
operational timeline rows.

The renderer displays only safe fields from `OperationalTimelineEntry`:

- summary;
- source provider;
- review status;
- occurred timestamp;
- source kind/id;
- data class;
- projection status and dates.

It does not render raw provider payloads, clinical notes, or unreviewed
clinical free text.

## Verification

- `cd apps/web && npm run lint` — passed.
- `cd apps/web && npm run test -- --run` — passed, 10 files / 48 tests.

## Status

Done in Linear.
