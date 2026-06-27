# ENG-310 — Patient details panel + per-pid names + household links

- **Task id:** ENG-310
- **Linear issue:** [ENG-310](https://linear.app/fusion-dental-implants/issue/ENG-310/patient-details-panel-surface-phi-fields-dob-phones-email-address-per)
- **Linear title:** Patient details panel + per-pid names + household links
- **Role / agent:** worker / claude-code
- **Runtime:** claude-code, session `facb65505b72`
- **Branch:** `eng-310-eng-310`
- **Worktree:** `~/.fusion-agent-orchestrator/c2db50910d08/current/worktrees/ENG-310`
- **Allowed scope:** mission spec (A per-pid names, B Patient details
  panel, C household links). No other code touched.

## What changed

### A — per-pid names in the multi-link expander

- `packages/ingest/schemas.py` — added `first_name` / `last_name`
  fields to `CarestackOriginRowOut`.
- `packages/ingest/repository.py::person_carestack_origin_context` —
  extended the `patient_stmt` SELECT to pull `payload['firstName']` /
  `payload['lastName']` and a dozen other detail fields from the
  latest `carestack.patient.upsert` per pid; folded into the per-pid
  bucket.
- `packages/ingest/service.py::person_carestack_origin_context` —
  forwards the new fields into the DTO.
- `apps/web/lib/api/schemas/person.ts` — Zod schema mirrors the new
  fields (optional + nullable).
- `apps/web/app/(staff)/persons/[uid]/page.tsx::CarestackMultiLinkPanel`
  — row label is now `formatPidRowLabel(row)` = `"First Last · pid"`
  when names present, bare pid otherwise.
- `apps/web/lib/msw/fixtures/persons.ts` — fixtures populated with
  names + patient detail fields.

### B — patient details panel

- One **design decision** I had to make: extend `CarestackOriginRowOut`
  with the detail fields **OR** add a sibling
  `person_carestack_patient_details` resolver. I extended the existing
  row. Rationale: the new fields all come from the same
  latest-patient.upsert payload the origin aggregator already reads, so
  doing it in one SELECT keeps the route at a single
  `person_carestack_origin_context` round-trip; a sibling resolver
  would have duplicated the `latest_patient_subq` join. Per-pid grouping
  is also natural (one panel per pid).
- Fields added: `dob`, `gender`, `marital_status`, `mobile`,
  `phone_with_ext`, `work_phone_with_ext`, `email`, `address_line1`,
  `address_line2`, `address_zip`, `patient_identifier`, `account_id`.
  All `str | None`. The `dob` value is the raw payload string (ISO
  date or datetime); the frontend renders verbatim.
- **SSN decision: OMIT in v1.** The mission allowed redaction OR
  omission; I chose omission because the masked-tail-digits form still
  expands the PHI surface (a partial SSN is still PHI) and the
  operators have not asked for SSN visibility in the v1 panel. The
  field can be added behind a separate ticket if a workflow needs it.
- Frontend: new `PatientDetailsPanel({ row })` component, mounted
  inside each multi-link expander row. Hidden by default, click-to-
  reveal (matches the `FieldLineWithHelp` show/hide pattern). Every
  absent field renders `"—"` (reuses existing UI semantics). Address
  is concatenated via `formatFullAddress(row)` = line1 + line2 +
  city,state + zip.

### C — household links (the new, important part)

#### Hard rule satisfied

- **Household key = normalised phone OR email. NEVER `accountId`.**
  The SQL-shape test
  `test_household_query_never_uses_accountid` greps the compiled SQL
  across every statement the resolver issues and asserts the string
  `accountid` does not appear.
- **Reads the verbatim `carestack.patient.upsert` payload, NOT
  `identity.person_identifier`.** The global `UNIQUE(kind, value)`
  constraint on `person_identifier` puts a shared phone on a single
  Person row after the ENG-311 split, so PersonIdentifier would miss
  siblings.

#### Algorithm (in `IngestRepository.person_household_members`)

1. Resolve this person's CareStack patient_ids via
   `identity.source_link` (tenant-scoped). Empty → `[]`.
2. Read the latest `carestack.patient.upsert` per self-pid; normalise
   `mobile` / `phoneWithExt` / `workPhoneWithExt` via
   `packages.identity.service.normalise_phone` (digits-only, ≥7) and
   `email` via `normalise_email`. Invalid values raise
   `ValidationError`; we `try/except`-skip silently. No self phones
   AND no self emails → `[]`.
3. **Candidate SQL pre-filter** — `carestack.patient.upsert` rows
   (latest per `external_id`), tenant-scoped, `external_id NOT IN
   self_pids`, where any of three phone payload fields contains the
   last-7-digit substring (`payload->>'mobile' ILIKE '%<last7>%'`,
   etc.) OR `lower(payload->>'email') = <email>` exactly. The OR
   clauses are evaluated server-side and only matching rows are
   returned.
4. **Python confirm** — re-normalise the candidate's phones/email,
   intersect with the self sets. If the intersection is empty the
   candidate is dropped (rules out coincidental digit substrings).
5. Map the matched pids → `identity.source_link.person_uid`
   (tenant-scoped, `person_uid != self`). Dedup by sibling
   `person_uid` (first signal wins). Identity-side display name comes
   from `identity.person.given_name + family_name` then
   `display_name`; falls back to the CareStack payload's
   `firstName + lastName` when identity has no name.
6. Mask the shared value: phone → `"···" + last4`, email →
   `"<first-char>···@<domain>"`.

#### Query-cost bound

The expensive step is step 3's candidate query. It is a tenant-scoped
seq-scan of the latest patient.upsert per `external_id` (~60K rows in
prod), with the same `MAX(received_at) GROUP BY external_id` join
shape the existing `person_carestack_origin_context` aggregator
already uses. PostgreSQL evaluates the OR-of-ILIKEs server-side and
returns ONLY the rows that contain at least one match — for a real
household the candidate count is in the low single digits. Python then
normalises and confirms; we never scan all 50K patients on the Python
side. Cost is comparable to the existing origin aggregator (which
runs on every person detail GET), and gated by the same tenant index.

#### DTO + service + route

- `packages/ingest/schemas.py` — new `HouseholdMemberOut` (`person_uid`,
  `display_name`, `shared_via`, `shared_value_masked`).
- `packages/ingest/service.py` — new
  `IngestService.person_household_members(tenant_id, person_uid)`.
- `apps/api/routers/persons.py` — added `household_members:
  list[HouseholdMemberOut] = []` to `PersonDetailOut`; route now does
  one extra `await ingest.person_household_members(tenant_id,
  person.id)` call (single round-trip, no N+1).

#### Frontend

- Zod `PersonHouseholdMemberSchema` + `household_members` on
  `PersonDetailSchema` (default `[]`).
- `HouseholdLinksCard({ members })` renders inside
  `app/(staff)/persons/[uid]/page.tsx` — hides entirely when empty;
  otherwise lists each member as a `<Link href="/persons/<uid>">` plus
  a muted `"Shares <via>: <masked>"` line. Disclaimer copy at the top:
  *"Shares a phone or email — these are different people. Financials
  and consultations are kept separate."*
- MSW fixture: Torosyan fixture now ships a 2-member household so the
  panel exercises both `"phone"` and `"both"` `shared_via` modes plus
  the masked-value hint.

### Route wiring

`apps/api/routers/persons.py:206-218` — same single round-trip
pattern the financial_summary + carestack_origin calls already use.
DTO carries both new fields; `consultations` and `timeline` remain
empty per existing convention (separate endpoints feed them).

## Touched files

| File | Why |
| --- | --- |
| `packages/ingest/schemas.py` | A+B: `CarestackOriginRowOut` extension. C: new `HouseholdMemberOut`. |
| `packages/ingest/repository.py` | A+B: extra payload SELECT in origin aggregator. C: new `person_household_members` + helpers. |
| `packages/ingest/service.py` | A+B: DTO mapping. C: new `person_household_members` service method. |
| `apps/api/routers/persons.py` | DTO field + route wiring for `household_members`. |
| `apps/web/lib/api/schemas/person.ts` | Zod schema for new fields + `household_members`. |
| `apps/web/lib/msw/fixtures/persons.ts` | Fixtures: per-pid names, patient detail fields, 2-member Torosyan household. |
| `apps/web/app/(staff)/persons/[uid]/page.tsx` | `formatPidRowLabel`, `PatientDetailsPanel`, `HouseholdLinksCard` + wiring. |
| `tests/ingest/test_person_household_repository_sql.py` | NEW. 14 tests covering household resolver. |
| `tests/ingest/test_person_carestack_origin_repository_sql.py` | Updated city/state-only invariant to match the new (ENG-310-broadened) full-address read. |
| `apps/web/tests/unit/PersonCardIdentity.test.tsx` | 7 new tests covering names, Patient details panel, household card. |

## Tests run

### Backend — ran inside sandbox

- `ruff check packages/ingest/ apps/api/routers/persons.py tests/ingest/`
  — **2 errors remain, both pre-existing on baseline** (confirmed by
  `git stash` + re-running). They are `UP037` on
  `packages/ingest/repository.py:477` (`list["SourceLink"]`, ENG-307)
  and `I001` on
  `tests/ingest/test_carestack_patients_with_payments_sql.py`. ENG-310
  code is ruff-clean.
- `mypy packages/ingest/ apps/api/routers/persons.py` — **Success: no
  issues found in 20 source files.**
- `pytest tests/ingest/` — **269 passed in 1.85s** (no regressions in
  the broader ingest suite).
- `pytest tests/ingest/test_person_household_repository_sql.py
  tests/ingest/test_person_carestack_origin_repository_sql.py` — **20
  passed** (all 14 new household tests + the 4 baseline origin tests
  + the 2 ENG-310-extension tests).

### Backend — deferred

- `pytest tests/api/test_person_detail.py` — sandbox-blocked. The
  test imports `apps.api.dependencies` which triggers
  `packages.db.session._build_engine()` at module load and pydantic-
  settings raises on missing `SECRET_KEY` / `DATABASE_URL` /
  `REDIS_URL`. No `.env` exists in the worktree (mission rule forbids
  editing `.env*`), and the harness blocks inline env-var injection.
  Existing repo convention is the same: `make verify` runs ruff +
  mypy + `verify-deploy` only and does NOT run pytest — full pytest
  is gated under `make verify-full` until env shims land. The new
  ENG-310 assertions I added inside the file follow the same
  `AsyncMock` + `app.dependency_overrides` shape as the existing
  ENG-306/308 tests and are statically reviewed.

### Frontend — deferred

- `npm run lint`, `npx tsc --noEmit`, `npm run test` — sandbox-
  blocked. The worktree has no `node_modules`, and the harness blocks
  `npm`/`tsc`/`vitest` invocations even via absolute paths into the
  main checkout's `node_modules`. The Zod schema additions are
  additive (default values + optional fields), the new
  `PatientDetailsPanel` and `HouseholdLinksCard` components follow
  the existing `FieldLineWithHelp` / `CarestackMultiLinkPanel`
  patterns, and the tests mirror the existing PersonCardIdentity
  test shape — should land green when the verifier runs the FE suite.

## Verification result

**Green where the sandbox allowed.** Ruff clean (mine), mypy clean,
all 269 ingest pytest tests pass including the 14 new household
tests. API and frontend test layers deferred to the verifier per the
sandbox constraints above; the code follows the existing patterns
(`PersonPaymentFinancialSummaryOut` + `CarestackOriginRowOut`
contract, `FieldLineWithHelp` UI pattern) so the verifier should be
able to confirm green.

## Risks

- The household resolver's candidate SQL is a seq-scan inside the
  tenant. In prod we have ~60K patient.upsert raw_events per tenant;
  cost is comparable to the existing origin aggregator that already
  runs per person detail GET. If hot-path latency degrades, a GIN
  index on `payload->>'mobile'` / `payload->>'email'` would be the
  next lever — but that's a migration ticket, not in scope here.
- The `ILIKE '%<last7>%'` substring match could theoretically false-
  positive on a phone whose last 7 digits collide. The Python
  normalise+exact-intersect step in step 4 rejects any false
  positive, but the seq-scan cost is paid either way.
- The address fields (`addressLine1`, `addressLine2`, `zipCode`) are
  now read by `person_carestack_origin_context`. The pre-ENG-310
  Safe-Harbor carve-out test
  (`test_person_carestack_origin_reads_patient_payload_city_state`)
  was deliberately updated to assert the broader read; that is a
  policy change (2026-06-01 PHI policy update + ENG-310 mission
  spec), not an oversight. PHI still never reaches structured log
  values.
- SSN is intentionally omitted. If the doctor decides operators need
  the last-4-digit mask, it lands as a separate ticket — the payload
  field is unchanged in the raw_event, just not surfaced.

## Blockers / open questions

None.

## Do-not-merge conditions

- The ENG-310 mission rule "**household key = phone/email only,
  accountId FORBIDDEN**" is enforced by
  `test_household_query_never_uses_accountid`. If a future change
  re-introduces `accountId` reads in the household path, that test
  must catch it — do not weaken the assertion.
- Don't merge if the integration verifier finds the seq-scan latency
  on the household query above the existing
  `person_carestack_origin_context` baseline by a meaningful margin
  — re-tier with a GIN index ticket first.
- Don't merge if the frontend lint/tsc/vitest run (which I could not
  exercise in-sandbox) surfaces issues; my changes follow existing
  conventions but the verifier should run the suite before
  integration.

## Suggested next task

`ENG-310` is feature-complete on this branch. After integration:

- Manual smoke on the Torosyan fixture (`/persons/55555555-aaaa-…`)
  to confirm the 3-row expander shows
  `Gaiane Torosyan · 1460847` / `Gaiane Torosyan · 1461274` /
  `Eduard Torosyan · 2171827`, the Patient details panel toggles per
  row, and the household card lists the 2 members with `···4258`.
- Open a follow-up if operators request SSN-mask visibility (deferred
  decision documented above).
