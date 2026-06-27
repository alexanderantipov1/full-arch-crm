# N1 Data Foundation Architecture

Date: 2026-05-18
Owner: Tesla read-only architecture agent, reviewed by Codex orchestrator
Status: complete, no file changes from agent

## Recommendation

Use `ops.inquiry`, not `lead_submission`, as the durable business object.
`lead_submission` can remain a provider/source kind. `inquiry` covers
Salesforce Leads, web forms, phone/SMS, HubSpot, and future non-form intake.

Use a separate `ops.consultation` for CareStack appointment/consultation-like
operational records. Do not reuse `phi.consultation` for the Phase 1 marketing
appointment view.

Use `identity.match_candidate` as a match-decision ledger. Do not blindly
auto-merge Salesforce and CareStack people from shared phone/email, but do
support policy-based auto-acceptance when confidence is high enough.

## Proposed Pipeline

```text
Salesforce Lead / CareStack Patient + Appointment
  -> ingest.raw_event
  -> normalized person hints
  -> identity.person + identity.source_link
  -> identity.match_candidate for cross-provider match decisions
  -> ops.inquiry / ops.consultation
  -> interaction.event only for semantic changes
```

## Tables To Add In Small PRs

- `identity.match_candidate` with statuses
  `open | auto_accepted | accepted | rejected | superseded`
- optional `ingest.normalized_person_hint`
- `ops.inquiry`
- `ops.consultation`

Optional raw event metadata in a later small migration:

- `processing_key`
- `payload_sha256`
- `source_observed_at`
- nullable `sync_run_id`

## Match Policy

The desired operating model is automated by default, with manual review only
for ambiguous or contradictory cases.

### Tier 1: Auto-Link

Always resolve automatically when the same stable source identity is seen
again:

- existing `identity.source_link`;
- same Salesforce Lead / Contact ID;
- same CareStack Patient ID.

This is linking, not a fuzzy merge.

### Tier 2: Auto-Accepted Cross-Provider Merge

Automatically merge Salesforce/CareStack people when the policy evidence is
strong, for example:

- exact normalized phone match;
- exact normalized email match;
- compatible normalized name;
- no conflicting name evidence;
- no other active CareStack Patient or Salesforce identity competing for the
  same phone/email;
- tenant/location context is compatible.

The system must still write:

- `identity.match_candidate` with status `auto_accepted`;
- `identity.merge_event`;
- evidence JSON explaining the decision;
- enough provenance to support future undo/split tooling.

### Tier 3: Open Candidate

Do not merge automatically when evidence is weak or ambiguous:

- only phone matches;
- only email matches;
- name conflicts;
- shared family email/phone pattern;
- multiple possible CareStack Patients or Salesforce records match the same
  identifier.

These rows remain `open` candidates and should not block normal operations.

## Key Rules

- Exact provider IDs resolve automatically through `identity.source_link`.
- Same-provider stable IDs resolve automatically.
- Cross-provider email/phone match creates a match decision:
  `auto_accepted` for high-confidence policy matches, `open` for ambiguous
  evidence, `rejected` / `superseded` for contradicted stale candidates.
- Accepted or auto-accepted match candidates record `identity.merge_event` and
  then call explicit domain merge handlers. `IdentityService` should not
  silently rewrite every domain reference.
- CareStack appointment payload is PHI-sensitive. Store only allowlisted
  operational fields outside PHI.

## Implementation Split

1. Identity PR: `identity.match_candidate` model/schema/repository/service tests.
2. Ingest PR: optional `person_hint` and raw event idempotency metadata.
3. Ops inquiry PR: `ops.inquiry` model/service/upsert/tests.
4. Ops consultation PR: `ops.consultation` model/service/upsert/tests.
5. Salesforce pipeline PR: Lead snapshot -> raw_event -> hint -> source_link or match_candidate -> inquiry -> interaction.
6. CareStack pipeline PR: Patient/Appointment sync -> raw_event -> hint -> source_link -> consultation -> interaction.

## Noted Risks

- `identity.person_identifier` uniqueness currently appears global on `(kind, value)`; multi-tenant duplicates may collide.
- `ops.lead` is currently one row per person; Salesforce can have multiple Lead records. Do not extend that 1:1 assumption for repeat ad/form submissions.
- CareStack appointment data must be allowlisted; no notes, DOB, chief complaint, findings, procedure detail, or clinical content in `ops.consultation`.
