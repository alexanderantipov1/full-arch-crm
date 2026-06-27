# Worker task — ENG-503: Find a Person → resolve to internal CRM person

You are a Claude Code Worker in the Fusion CRM orchestrator. Read root
`CLAUDE.md`, `apps/api/CLAUDE.md`, and `apps/web/CLAUDE.md` before coding.
Conversation with the operator is Russian; everything written to the repo is
English.

Linear: **ENG-503** — https://linear.app/fusion-dental-implants/issue/ENG-503
Branch: this worktree's branch (forked from `origin/main`). Do NOT rebase onto
the stale local `main`. Class: contract_change → a Codex cross-runtime reviewer
runs before integration; you only prep a draft PR.

## Problem (verified)

`/people/search/live` (apps/web/app/api/people/search/route.ts, re-exported via
app/(staff)/people/search/live/route.ts) is a LIVE SF+CareStack lookup that
hardcodes `linked_person_uids = []`. So `PeopleSearchResults.tsx` never shows
the "Already in CRM → /persons/{uid}" strip and the per-card Link button stays
disabled. `apps/api/routers/persons.py` has list/detail/timeline but no
phone/name search and no resolve endpoint. Net: an operator can't get from a
search hit to the unified person page. Reference person for manual QA (local
dev DB, tenant 11111111): Oxana Semeryuk, phone 9162252485, person_uid
`a02e32b8-4054-4dc1-8f6d-03cbcd7e2225`, two CareStack patients (1466081 @ loc
10029, 2172055 @ loc 8027) both linked to that one person via
identity.source_link.

## Deliverables

### A. Backend — resolve search hits to internal person
- Add a resolution step: for each SF/CareStack match, look up
  `identity.source_link` by (source_system, source_kind, source_id) within the
  principal's tenant → `person_uid`. Fallback to `person_identifier` by
  canonical phone/email when no source_link exists.
- Populate response `linked_person_uids` (dedup, stable order) AND a per-match
  `linked_person_uid` so each card can deep-link.
- Move the live-search backend logic into `apps/api` (new
  `apps/api/routers/people_search.py` mounted so `/people/search/live` keeps
  working in prod per the routing-split rule — prod-capable endpoints live in
  apps/api, not Next.js route handlers). Keep the existing
  `PeopleSearchOut` response shape; only `linked_person_uid(s)` change from
  empty to populated. Use IdentityService (read-only) — never touch the DB
  from outside the service layer.

### B. Backend — internal person search by phone/name
- Extend `apps/api/routers/persons.py` `GET /persons` (or add a sibling) with
  optional `phone` and `q` (name) query params. Canonicalize phone to E.164
  before matching (see normalise_phone). Return existing `PersonSummaryOut`.
- This must work with NO external connector (pure internal read).

### C. Frontend — navigation + Link
- In `PeopleSearchResults.tsx`: render the "Already in CRM" strip with
  clickable `/persons/{uid}` whenever matches resolve; enable the per-card Link
  button to navigate to the person page; remove/replace the
  `LINK_DISABLED_TOOLTIP` gating. Keep MSW handlers in sync — delete any mock
  that the real endpoint now covers (no zombie mocks).
- Update `peopleSearch.ts` only if a per-match `linked_person_uid` field is
  added (additive, optional).

## Constraints
- No auth gating (documented pre-access-control posture). PHI/PII may render.
- No DB migration expected; if you think you need one, STOP and write
  `Needs decision:` in the runlog.
- No `.env*`, no infra/deploy changes.
- Logs stay PHI-free (person_uid/action codes only).

## Verification (must pass before PR)
- `.venv/bin/ruff check apps/api`
- `.venv/bin/python -m pytest tests/api/test_persons_search.py tests/api/test_people_search_resolve.py -v`
  (write these; integration tests use the real test Postgres, not mocks)
- `cd apps/web && pnpm tsc --noEmit && pnpm test PeopleSearchResults`
- Manual: search 9162252485 in the dialog → resolves to person
  a02e32b8…, strip + Link navigate to /persons/a02e32b8….

## Reporting
Write `.agents/orchestration/eng-503-find-person-link-v1/reports/eng-503-worker-report.md`
with: touched files, what changed, tests run + results, verification status,
risks, do-not-merge conditions, open questions. Use runlog markers
(`Blocked:`, `Needs decision:`, `Handoff:`). Prep a DRAFT PR only — do not
merge. Merge/deploy require explicit operator approval.
