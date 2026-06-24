# ENG-206 Worker Report

## Task

- **Task id:** ENG-206
- **Title:** People search should find imported source-data records when live Salesforce is unavailable
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-206/people-search-should-find-imported-source-data-records-when-live
- **Role / agent:** worker / codex
- **Branch:** main
- **Worktree:** `.`

## Allowed Scope

Fix the local staff people-search bug where imported Salesforce source records were not returned when live Salesforce OAuth was disconnected. Keep the change scoped to the staff frontend/API route and preserve the local-dev source-data safety boundary.

## Touched Files

- `apps/web/app/api/people/search/route.ts`

## What Changed

- Added a local-dev source-data fallback to the people-search route.
- Mapped imported Salesforce source-data records into the existing Salesforce match shape.
- Mapped imported CareStack patient source-data records into the existing CareStack match shape when applicable.
- Merged local imported matches with live provider matches.
- Suppressed provider `not_connected` warnings when a local imported match exists for that provider.
- Populated `linked_person_uids` from matched records that already carry `resolved_person_uid`.

## Verification

Commands run from `apps/web`:

- `npm run typecheck` — passed.
- `npm run lint` — passed.
- `npm run test -- --run` — passed, 5 files / 24 tests.

Manual local endpoint verification:

```bash
curl -s 'http://localhost:3000/api/people/search?phone=15103810303' | jq '{warnings, linked_person_uids, salesforce: .salesforce.matches[0:2]}'
```

Result included:

- no warnings;
- linked person `227d0e8e-cbfd-4e45-8bb7-340809d4e51f`;
- Salesforce Lead `00QVw00000Z1VqPMAV`;
- name `Troy Mclauchlin`;
- email `troy94546@yahoo.com`;
- phone `15103810303`.

## Risks

- The fallback currently fetches up to 200 local source-data records, matching the local dev source-data surface. This is acceptable for the dev/debug view but should become a backend service search endpoint before broader production use.
- This is gated to `NEXT_PUBLIC_ENVIRONMENT === "local"` and depends on the existing `/api/dev/source-data` route.

## Blockers Or Questions

- None for the scoped bugfix.

## Suggested Next Task

Move source-data-backed people search into the FastAPI/service layer when the source-data projection graduates from local-dev inspection to a first-class staff search contract.

## Do Not Merge Conditions

- Do not merge if the source-data fallback is expected to work in production; this implementation intentionally limits fallback behavior to local-dev.
- Do not merge if `/api/dev/source-data` is removed or renamed without updating this route.

