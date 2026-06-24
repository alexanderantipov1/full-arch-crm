You are a Claude Code WORKER on Fusion CRM. Linear: **ENG-310**. Isolated git
worktree. Implement → verify → report. Do NOT touch `main`, do NOT push.
Commit to your worktree branch once green; Orchestrator integrates.

## Mission — 3 person-card identity surfaces

A. Per-pid **names** in the multi-link expander (Gaiane / Gaiane / Eduard
   instead of bare pids).
B. **Patient details** click-to-reveal panel (DOB/phones/email/address per pid).
C. **Household links** — bidirectional navigational links to OTHER persons
   sharing a normalized phone/email. Financials/consultations NOT merged.

Full ticket detail: ENG-310 in Linear. Key facts below are AUDITED — do not
re-investigate.

## Pre-flight facts (AUDITED)

### A — per-pid names
- `CarestackOriginRowOut` at `packages/ingest/schemas.py:240-273` (8 fields).
  ADD `first_name: str | None = None`, `last_name: str | None = None`.
- The repo aggregator `person_carestack_origin_context` builds rows in
  `packages/ingest/repository.py` (~691-840). City/state already extracted
  via `RawEvent.payload["addressDetail"]["city"].astext` (lines 834-841).
  Add `RawEvent.payload["firstName"].astext` + `["lastName"].astext` the
  same way, from the latest `carestack.patient.upsert` per pid.
- Frontend expander `CarestackMultiLinkPanel` at
  `apps/web/app/(staff)/persons/[uid]/page.tsx:814-850` renders each row's
  patient_id + location + provider. Add the name: render
  `{row.first_name} {row.last_name} · {row.patient_id}` (fall back to just
  pid when names null).
- Zod `PersonCarestackOriginRowSchema` at `apps/web/lib/api/schemas/person.ts:265-275`
  — add `first_name`/`last_name` nullable.

### B — patient details panel
- Reuse the `FieldLineWithHelp` tooltip + show/hide pattern at
  `persons/[uid]/page.tsx:671-711` (same as "First ingest"/"Earliest
  activity"). Add a "Patient details" collapsible (default hidden) that,
  per linked pid, shows: full name, DOB, gender, marital status, mobile,
  phoneWithExt, workPhoneWithExt, email, address (line1/2/city/state/zip),
  patientIdentifier, accountId. SSN: render redacted `***-**-NNNN` from last
  4 digits, OR omit in v1 — your call, document it.
- Backend: these fields come from the latest `carestack.patient.upsert`
  payload per pid. Either extend `CarestackOriginRowOut` with the detail
  fields, OR add a sibling `person_carestack_patient_details` resolver.
  Your design call — document. Empty fields → frontend renders `"—"`
  (reuse the existing FieldLine `"—"` behavior).

### C — household links (the new, important part)

**Household key = normalized phone OR email. NEVER accountId.**
VERIFIED: CareStack `accountId` is a clinic-level default — value `10762`
appears on **55,704** of ~55,700 pids (the clinic's own CareStack account).
The Torosyan mobile `(916) 215-4258` appears on exactly **3** pids = the
real household. Using accountId would link every patient to every patient.
If you find yourself writing `accountId` in the household query, STOP —
that's the bug.

**Resolver MUST read raw_event payload, NOT PersonIdentifier.**
`identity.person_identifier` has a global `UNIQUE(kind, value)` constraint
(`identity/models.py:162`), so a shared phone lives on only ONE person row
after the ENG-311 split. Joining PersonIdentifier would miss the siblings.
The household resolver reads the `carestack.patient.upsert` payload
`mobile` / `phoneWithExt` / `workPhoneWithExt` / `email` fields.

Build `IngestRepository.person_household_members(tenant_id, person_uid) ->
list[dict]`:
1. Resolve this person's CareStack patient_ids (via source_link).
2. Collect their normalized phones + emails from the latest
   `carestack.patient.upsert` payload per pid. Use
   `packages.identity.service.normalise_phone` / `normalise_email`
   (service.py:86-102) — wrap in try/except ValidationError, skip invalid.
3. Find OTHER source_link person_uids whose CareStack patients' latest
   payload has a matching normalized phone OR email — EXCLUDING this
   person_uid. Tenant-scoped. Distinct by person_uid.
4. For each sibling person: resolve a display_name (given_name+family_name
   from identity.person, or the CareStack payload name), `shared_via`
   ("phone"|"email"|"both"), `shared_value_masked` (last 4 of phone, e.g.
   "···4258", or the email local-part masked like "g···@gmail.com").
5. Empty-input short-circuit (no pids → []).

Normalization happens in Python (read payloads, normalize, match) OR in
SQL — but since `normalise_phone` is a Python regex, the cleanest path is:
read the candidate set with a SQL pre-filter, then normalize+match in
Python. Avoid loading all 50K patients — pre-filter by the raw (un-normalized)
phone/email substrings or by a bounded candidate query. Document your
approach + its query-cost bound in the report.

DTO `HouseholdMemberOut` in `packages/ingest/schemas.py`:
`person_uid: str`, `display_name: str | None`, `shared_via: str`,
`shared_value_masked: str`.

Service `person_household_members(tenant_id, person_uid)` in
`packages/ingest/service.py` → returns `list[HouseholdMemberOut]`.

### Route wiring
`apps/api/routers/persons.py:206-213` — after `carestack_origin`, add:
```python
household_members = await ingest.person_household_members(tenant_id, person.id)
```
Add `household_members: list[HouseholdMemberOut] = []` to `PersonDetailOut`
(near lines 112-115). Single round-trip; no N+1.

### Frontend household section
- Zod: add `PersonHouseholdMemberSchema` + `household_members` array to
  `PersonDetailSchema` (person.ts).
- On the person card, a "Household / shared contact" section (only when
  `household_members.length > 0`): each member rendered as
  `<Link href={`/persons/${m.person_uid}`}>{m.display_name}</Link>` +
  a muted `shared_via` + `shared_value_masked` hint. Link import is
  `import Link from "next/link"` (already imported, line 4).
- Explicit copy at the top of the section: "Shares a phone or email — these
  are different people. Financials and consultations are kept separate."
- Bidirectional is automatic (resolver symmetric).

## Tests

Backend (`tests/ingest/...`, reuse `_stub_session_capturing`):
- `person_household_members` finds a sibling sharing a phone; excludes self;
  symmetric; tenant-scoped; empty short-circuit.
- **SQL-shape test asserts the query does NOT reference `accountId`** (grep
  the compiled SQL string).
- names appear in carestack_origin rows.
- masking: phone → "···4258", email → masked local-part.

Frontend (`apps/web/tests/unit/PersonCardIdentity.test.tsx`, extend):
- expander row shows "First Last · pid".
- Patient details panel hidden by default; click reveals DOB/phones/email/address.
- household section renders a member with a working `<Link>` + masked hint +
  the "different people / financials separate" copy; hidden when empty.
- empty fields → "—".

MSW fixtures (`apps/web/lib/msw/fixtures/persons.ts`): add `household_members`
+ names to the relevant fixtures (a 2-member household so the link renders).

## Hard constraints
- **Household key = phone/email ONLY. accountId FORBIDDEN** (test asserts).
- Resolver via raw_event payload, NOT PersonIdentifier.
- No PHI in structured log VALUES (UI surfaces are fine; logs are not).
- Schema separation; PhiService if phi.* crossed (it isn't here — all reads
  are from `ingest.raw_event` + `identity`).
- CareStack mocked in tests. Strict TS / strict mypy.
- `except Exception`, never `except BaseException`.
- No `apps/web/lib/msw/handlers.ts` edits. No new migration expected.
- Reuse: `CarestackOriginRowOut`, the `FieldLineWithHelp` tooltip, the
  `normalise_phone/email` helpers, the multi-link expander.

## Verify (sandbox-aware)
```bash
ruff check packages/ingest/ apps/api/routers/persons.py tests/ingest/
mypy packages/ingest/ apps/api/routers/persons.py
pytest tests/ingest/ tests/api/test_person_detail.py -o pythonpath=. -q
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```
Document what ran vs deferred.

## Done
1. Sandbox-allowed verify green.
2. ONE commit on worktree branch:
   `ENG-310: per-pid names + patient details panel + household links`.
3. Report at `.agents/orchestration/current/reports/ENG-310-worker-report.md`:
   touched files, the household resolver approach + query-cost bound, the
   SSN-redaction decision, tests, verify outcomes, risks, DO-NOT-MERGE.

If the household resolver can't avoid scanning all patients efficiently,
STOP and write `Blocked:` with the options rather than ship an O(50K) query.
