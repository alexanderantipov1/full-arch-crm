# CLAUDE.md — `packages/ops`

Non-clinical CRM data. Front-desk flows, marketing, follow-up tasks.
**Strictly PHI-free.**

## Tables (schema `ops`)

- **`lead`** — sales/marketing opportunity, status enum.
- **`followup_task`** — an action a staff member should perform.
- **`account`** — Phase 1 minimal external-organisation view (SF
  Account, future HubSpot Company). Idempotent on
  `(provider, source_id)` — re-pulls find the existing row. Full
  v0.2 design (`docs/plans/2026-04-30-full-schema-v0_2.md` §9.1)
  ships richer fields when needed.
- **`consultation`** — marketing-safe projection of a CareStack
  appointment or Salesforce Event. Clinical notes and treatment
  payloads stay in provider raw storage / `phi.*`.
- **`person_location_profile`** — evidence-derived relationship
  projection between a global `identity.person` and one clinic
  location. Stores CRM-safe status only; imported row existence alone
  must not mark someone as a patient.

`lead` and `followup_task` reference a person via `person_uid`
(UUID column, no cross-schema FK). `account` is provider-keyed,
not person-keyed; Lead-to-Account linkage joins via SF
``Account.Id`` carried on the Lead's raw payload (no DB-level FK
in Phase 1).

## Hard rules

- **`ops` MUST NOT import from `packages.phi`.** Not in tests, not
  in scripts, not in tools. If you need a clinical fact for a
  decision, the decision belongs in `phi` or in a higher-level
  orchestration service — not here.
- **`ops` outputs are safe for AI agents and external dashboards.**
  `OpsPersonSnapshot` is the contract — keep it scrubbed.
- **Free-text fields** (`lead.notes`, `followup_task.description`)
  must be reviewed when surfacing them to LLMs; staff sometimes
  paste clinical text in by accident. Today the safeguard is policy;
  add automated scrubbing before agents read these fields verbatim.

## Service surface

`OpsService.snapshot(person_uid) → OpsPersonSnapshot`
`OpsService.create_followup(payload) → FollowupTask`
`OpsService.create_lead(payload) → Lead`
`OpsService.list_followups(person_uid) → list[FollowupTask]`
`OpsService.record_account(provider, source_id, name, raw?) → Account`
`OpsService.upsert_lead(person_uid, raw) → UpsertLeadResult`
`OpsService.upsert_consultation_from_hint(payload) → ConsultationUpsertResult`
`OpsService.list_person_location_profiles_for_person(person_uid) → list[PersonLocationProfileOut]`

Existence of the referenced `Person` is validated against
`IdentityService` before insert. Do not skip that.

### `upsert_lead` change-detection contract

The W1 Salesforce-Lead-pull worker calls this once per pulled SF
Lead row. Phase 1 keeps the lookup key as `person_uid` (one Lead
row per person). The service:

1. If no existing Lead → insert + return
   `UpsertLeadResult(was_created=True, was_changed=True)`.
2. If existing AND watched fields differ → update + return
   `(was_created=False, was_changed=True)`.
3. If existing AND watched fields equal → no-op + return
   `(was_created=False, was_changed=False)`.

Watched fields: `lead_status` (mirrors SF `Status`), `lead_source`
(mirrors SF `LeadSource`). Stored under `Lead.extra`.

The worker uses these flags to decide which `interaction.event`
kind to emit:

```
result = await ops.upsert_lead(person_uid=p.id, raw=sf_row)
if result.was_changed:
    kind = "lead_created" if result.was_created else "lead_updated"
    await interaction.create_event(...)
```

We do NOT duplicate the full raw row onto `Lead.extra` — raw
payloads live in `ingest.raw_event`. `extra` carries only the
change-detection mirror.

## Status enums

- `LeadStatus`: `new | qualified | contacted | booked | lost`
- `FollowupStatus`: `open | done | skipped`

Adding a value → migration + update of any agent prompt that
enumerates them.

## Person-location profile rule

`person_location_profile.relationship_kind` is location-scoped. A
scheduled, cancelled, or no-show consultation may create/update a
`prospect` profile, but only completed appointment/consultation
evidence may promote `relationship_kind` to `patient`. When a
consultation has no `location_id`, do not create a profile; the
location context is ambiguous.
