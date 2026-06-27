# Mission: ENG-503 — Find a Person → resolve to internal CRM person

Linear: ENG-503 — https://linear.app/fusion-dental-implants/issue/ENG-503
Class: contract_change (shared people-search contract behavior + new persons search param)
Branch base: `origin/main` (current tip — NOT stale local `main`)

## Business goal

The "Find a Person" search currently shows raw external records (live SF +
CareStack) with no bridge to our resolved `identity.person`. An operator
searching a phone gets non-clickable cards and cannot reach the person page
or the consultation. Make the search resolve hits to the internal person,
let the operator click through to `/persons/{uid}`, and add an internal
person search by phone/name that works even when the live external connector
is "not connected".

## Deliverables (operator-approved full scope)

- **A. Backend resolve** — populate `linked_person_uids` (and per-match
  `linked_person_uid`) by resolving SF/CareStack `source_id` →
  `identity.person` via `identity.source_link` (fallback: phone/email
  `person_identifier`). Move the search backend out of the Next.js route into
  `apps/api`, keeping the `/people/search/live` response contract stable.
- **B. Internal person search** — add phone/name search to
  `apps/api/routers/persons.py` over `identity.person` + `person_identifier`,
  returning the existing `PersonSummaryOut` shape.
- **C. Frontend** — render the "Already in CRM → /persons/{uid}" strip when a
  match resolves, enable the per-card Link action, make result cards
  actionable.

## Out of scope

ENG-405 (manual merge tool), ENG-477 (phone-dup backfill). No auth gating
(documented pre-access-control posture). No migrations expected.
