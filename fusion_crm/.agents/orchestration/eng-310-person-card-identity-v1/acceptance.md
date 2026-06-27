# Acceptance — ENG-310

## A. Per-pid names
- [ ] `CarestackOriginRowOut` gains `first_name` + `last_name` from latest
      `carestack.patient.upsert` payload per pid.
- [ ] Expander row renders `First Last · <pid>`.

## B. PHI details panel
- [ ] "Patient details" Show/Hide section (default hidden) per linked pid:
      full name, DOB, gender, marital status, mobile/phoneWithExt/
      workPhoneWithExt, email, address (line1/2/city/state/zip),
      patientIdentifier, accountId. SSN redacted `***-**-1234` or omitted
      (worker's call, documented).
- [ ] Empty fields → `"—"`.

## C. Household links
- [ ] `IngestRepository.person_household_members(tenant_id, person_uid)`
      → OTHER persons whose CS patients share a normalized phone OR email.
      Exclude self. Symmetric. Tenant-scoped. Empty short-circuit.
      **Uses phone/email, NEVER accountId** (test asserts no accountId in
      query).
- [ ] Resolves via raw_event payload (mobile/email) NOT PersonIdentifier
      — because the global UNIQUE(kind,value) means a shared phone lives
      on only one person post-split, so PersonIdentifier can't find
      siblings. (Pre-flight confirms; worker verifies.)
- [ ] DTO `HouseholdMemberOut`: `person_uid`, `display_name`,
      `shared_via` (phone|email|both), `shared_value_masked` (e.g. ···4258).
- [ ] `PersonDetailOut.household_members: list[HouseholdMemberOut]`,
      resolved in the existing single route round-trip.
- [ ] Frontend "Household / shared contact" section: each member name +
      Next.js `<Link href="/persons/{uid}">`; copy: "Shares a phone/email
      — not the same person. Financials kept separate." Hidden when empty.

## Tests
- [ ] Backend: household resolver finds shared-phone/email persons,
      excludes self, symmetric, tenant-scoped, empty short-circuit;
      SQL-shape test asserts NO accountId in the statement; names in
      origin rows.
- [ ] Frontend: expander names; PHI panel hidden→reveal; household
      section renders members + `<Link>` + masked hint + "not same person"
      copy; empty states `"—"`.

## Verify
- [ ] `cd apps/web && npm run lint && npx tsc --noEmit && npm run test` green.
- [ ] `make lint && mypy . && make test && cd packages/db && alembic check` green.
- [ ] Worker report at `reports/ENG-310-worker-report.md`.
- [ ] Commit to worktree branch only; no push; Orchestrator integrates.

## Out of scope
- accountId-based grouping (forbidden — clinic default).
- Financial/consultation merge across household (links are navigational only).
- SF-lead identity (different path).
