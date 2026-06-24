# Contract — ENG-310

- `CarestackOriginRowOut` += `first_name`, `last_name` (per-pid latest payload).
- `HouseholdMemberOut`: person_uid, display_name, shared_via, shared_value_masked.
- `PersonDetailOut` += `household_members: list[HouseholdMemberOut]`.
- `IngestRepository.person_household_members(tenant_id, person_uid)` —
  raw_event payload phone/email match, exclude self, symmetric,
  tenant-scoped, empty short-circuit, NO accountId.
- New PHI fields surfaced in a click-to-reveal frontend panel (UI only;
  not logged).

## Hard limits
- Household key = normalized phone/email ONLY. accountId FORBIDDEN.
- No PHI in structured log values.
- Schema separation; PhiService if phi.* crossed.
- CareStack mocked in tests. Strict TS/mypy.
- No apps/web/lib/msw/handlers.ts edits. No new migration expected.
- except Exception only. English repo files.
