# P2 Data Foundation Implementation Plan

Task ID: P2
Linear issue: ENG-181
Agent role: architecture/schema worker
Status: complete
Branch: current working tree, read-only except this report
Worktree: `/Users/eduardkarionov/Desktop/Fusion_crm`

## Summary

The next data-foundation step should add three canonical surfaces:
`ingest.normalized_person_hint`, `identity.match_candidate`, and two ops
business objects: `ops.inquiry` and `ops.consultation`.

The matching path should be automated by default. Exact source IDs and
high-confidence email/phone/name evidence should link or merge automatically
with an explicit `identity.match_candidate` evidence row. Only ambiguous or
contradictory evidence should stay `open`, and open candidates must not block
normal Salesforce or CareStack processing.

## Current Constraints Observed

- `identity.person.id` is the global `person_uid`.
- `identity.source_link` already dedupes stable provider records by
  `(source_system, source_kind, source_id)`.
- `identity.merge_event` already records accepted person merges, but does not
  rewrite downstream domain references.
- `SfLeadIngestService` currently performs hidden email/phone reactivation
  matching inside the Salesforce pipeline. This should move into an explicit
  identity match policy so Salesforce and CareStack use the same rules.
- `ops.lead` is currently one row per person. Do not extend that shape for
  repeated ad/form submissions; use `ops.inquiry`.
- `ops` must remain PHI-free. CareStack clinical details, DOB, treatment notes,
  findings, plans, allergies, prescriptions, procedure details, and free-text
  clinical fields stay out of `ops`.
- Existing `person_identifier` and `source_link` uniqueness appears global in
  model/migration shape instead of tenant-scoped. New tables should use
  `tenant_id` in unique keys, and the old uniqueness shape should be handled by
  the existing verify/drift cleanup before production multi-tenant use.

## Proposed Tables

### `ingest.normalized_person_hint`

Purpose: store the provider-neutral, normalized person evidence extracted from
a raw provider payload. It is not the canonical person row and must not become
an ops dashboard surface.

Columns:

| Column | Type | Null | Notes |
|---|---:|---:|---|
| `id` | UUID PK | no | `UUIDPrimaryKeyMixin` |
| `tenant_id` | UUID | no | `TenantScopedMixin` |
| `raw_event_id` | UUID | no | DB FK to `ingest.raw_event.id` is acceptable because it stays within `ingest` |
| `source_system` | String(32) | no | `salesforce`, `carestack`, `web_form`, etc. |
| `source_kind` | String(32) | no | `lead`, `contact`, `patient`, `submitter`, etc. |
| `source_id` | String(240) | yes | provider record id if available |
| `observed_at` | TIMESTAMPTZ | no | provider event/update time or `raw_event.received_at` |
| `given_name` | String(120) | yes | normalized/canonical casing only when safe |
| `family_name` | String(120) | yes | normalized/canonical casing only when safe |
| `display_name` | String(240) | yes | non-clinical |
| `email_normalized` | String(320) | yes | lower-cased; do not store raw email variants |
| `phone_normalized` | String(32) | yes | current project normalizer strips to digits |
| `person_uid` | UUID | yes | set after resolution; plain UUID, no Python import from identity |
| `source_link_id` | UUID | yes | optional provenance pointer after link creation |
| `payload_sha256` | String(64) | yes | hash of canonical raw payload bytes, for replay/idempotency |
| `hint_hash` | String(64) | no | hash of normalized matching features |
| `quality_flags` | JSONB | no | e.g. invalid email, missing name, shared-phone risk |
| `meta` | JSONB | no | non-PHI parser metadata only |
| `created_at` / `updated_at` | TIMESTAMPTZ | no | `TimestampMixin` |

Constraints and indexes:

- `UNIQUE (tenant_id, raw_event_id)` if one hint per event.
- If a raw event can yield multiple people later, use
  `UNIQUE (tenant_id, raw_event_id, source_kind, source_id)` instead.
- `ix_normalized_person_hint_source` on
  `(tenant_id, source_system, source_kind, source_id)`.
- `ix_normalized_person_hint_email` on `(tenant_id, email_normalized)`.
- `ix_normalized_person_hint_phone` on `(tenant_id, phone_normalized)`.
- `ix_normalized_person_hint_person_uid` on `(tenant_id, person_uid)`.
- CHECK `source_system` and `source_kind` should mirror identity source lists,
  or use service validation if we want to avoid repeated DB check migrations.

Optional same-PR `ingest.raw_event` additive columns:

- `processing_key` String(320), nullable.
- `payload_sha256` String(64), nullable.
- `source_observed_at` TIMESTAMPTZ, nullable.
- `sync_run_id` UUID, nullable plain pointer to `integrations.sync_run`.

### `identity.match_candidate`

Purpose: explicit decision ledger for matching incoming provider hints and/or
two existing persons. It records why the system auto-linked, auto-merged, left
an ambiguity open, rejected a stale match, or superseded an earlier candidate.

Columns:

| Column | Type | Null | Notes |
|---|---:|---:|---|
| `id` | UUID PK | no | `UUIDPrimaryKeyMixin` |
| `tenant_id` | UUID | no | `TenantScopedMixin` |
| `hint_id` | UUID | yes | plain UUID pointer to `ingest.normalized_person_hint.id`; avoid identity importing ingest |
| `source_person_uid` | UUID | yes | person created from the incoming source, if already materialized |
| `candidate_person_uid` | UUID | no | existing person proposed as the same human |
| `accepted_person_uid` | UUID | yes | populated for `auto_accepted` / `accepted` |
| `merge_event_id` | UUID | yes | plain UUID pointer to `identity.merge_event.id` after an actual merge |
| `status` | String(24) | no | `open`, `auto_accepted`, `accepted`, `rejected`, `superseded` |
| `match_rule` | String(64) | no | e.g. `email_phone_name`, `phone_name`, `email_name`, `source_link` |
| `confidence` | Numeric(5,4) | no | 0.0000-1.0000 |
| `evidence` | JSONB | no | normalized, non-raw evidence; no clinical text |
| `conflicts` | JSONB | no | competing persons, name mismatch, shared identifier flags |
| `person_pair_key` | String(73) | yes | sorted UUID pair key when two persons exist |
| `decided_at` | TIMESTAMPTZ | yes | set for all non-`open` statuses |
| `decided_by_actor_id` | UUID | yes | actor/system id when known |
| `superseded_by_match_id` | UUID | yes | self-reference pointer, optional FK |
| `created_at` / `updated_at` | TIMESTAMPTZ | no | `TimestampMixin` |

Constraints and indexes:

- CHECK `status IN ('open', 'auto_accepted', 'accepted', 'rejected', 'superseded')`.
- CHECK `confidence >= 0 AND confidence <= 1`.
- CHECK `source_person_uid IS NULL OR source_person_uid <> candidate_person_uid`.
- CHECK `accepted_person_uid IS NULL OR status IN ('auto_accepted', 'accepted')`.
- `ix_match_candidate_candidate` on `(tenant_id, candidate_person_uid)`.
- `ix_match_candidate_source_person` on `(tenant_id, source_person_uid)`.
- `ix_match_candidate_hint` on `(tenant_id, hint_id)`.
- `ix_match_candidate_status` on `(tenant_id, status, created_at)`.
- Partial unique open-candidate guard:
  `UNIQUE (tenant_id, person_pair_key) WHERE status = 'open' AND person_pair_key IS NOT NULL`.
- Partial unique hint acceptance guard:
  `UNIQUE (tenant_id, hint_id, candidate_person_uid) WHERE status IN ('open', 'auto_accepted', 'accepted') AND hint_id IS NOT NULL`.

Policy note: when an incoming hint high-confidence matches an existing person,
prefer adding `identity.source_link` to the existing `person_uid` instead of
creating a duplicate person and then merging. `merge_event` is needed when two
persons already exist.

### `ops.inquiry`

Purpose: canonical repeated intake/ad/form/lead-submission object. Salesforce
Lead, web form submission, inbound call inquiry, HubSpot contact/deal signal,
or future landing-page submit can all become an inquiry. This avoids forcing
repeat submissions into the current one-row-per-person `ops.lead` aggregate.

Columns:

| Column | Type | Null | Notes |
|---|---:|---:|---|
| `id` | UUID PK | no | `UUIDPrimaryKeyMixin` |
| `tenant_id` | UUID | no | `TenantScopedMixin` |
| `person_uid` | UUID | no | plain UUID reference to `identity.person.id` |
| `source_provider` | String(32) | no | `salesforce`, `web_form`, `hubspot`, etc. |
| `source_kind` | String(32) | no | `lead`, `form_submission`, `call`, `sms`, etc. |
| `source_id` | String(240) | yes | provider record id |
| `source_event_id` | UUID | yes | raw event pointer |
| `occurred_at` | TIMESTAMPTZ | no | provider-created time or received time |
| `status` | String(24) | no | `new`, `working`, `booked`, `closed`, `lost`, `duplicate` |
| `channel` | String(32) | yes | `paid_search`, `organic`, `referral`, `phone`, `sms`, etc. |
| `campaign` | String(240) | yes | marketing campaign label; no free-text clinical content |
| `utm_source` | String(160) | yes | allowlisted attribution |
| `utm_medium` | String(160) | yes | allowlisted attribution |
| `utm_campaign` | String(240) | yes | allowlisted attribution |
| `utm_content` | String(240) | yes | allowlisted attribution |
| `utm_term` | String(240) | yes | allowlisted attribution |
| `lead_source` | String(120) | yes | normalized source label |
| `intent` | String(120) | yes | non-clinical marketing intent label; taxonomy-governed later |
| `location_ref` | String(120) | yes | provider/location hint, not address |
| `owner_ref` | String(120) | yes | provider owner/user id if needed |
| `raw_marketing` | JSONB | no | strict allowlist only; no raw provider payload |
| `created_at` / `updated_at` | TIMESTAMPTZ | no | `TimestampMixin` |

Constraints and indexes:

- CHECK `status IN ('new', 'working', 'booked', 'closed', 'lost', 'duplicate')`.
- CHECK `source_provider IN (...)` or service validation.
- `UNIQUE (tenant_id, source_provider, source_kind, source_id) WHERE source_id IS NOT NULL`.
- `ix_inquiry_person_occurred` on `(tenant_id, person_uid, occurred_at DESC)`.
- `ix_inquiry_source` on `(tenant_id, source_provider, source_kind)`.
- `ix_inquiry_status_occurred` on `(tenant_id, status, occurred_at DESC)`.
- Optional GIN index on `raw_marketing` only if query volume justifies it.

Relationship to `ops.lead`:

- Keep `ops.lead` as the current CRM aggregate for a person.
- Write one `ops.inquiry` per provider/form submission.
- Salesforce pipeline should eventually call `upsert_inquiry(...)` first, then
  update `ops.lead` as a derived/current-state convenience.

### `ops.consultation`

Purpose: non-clinical marketing/scheduling view of a consultation-like
appointment, primarily from CareStack. It is not `phi.consultation` and not
future `phi.appointment`.

Columns:

| Column | Type | Null | Notes |
|---|---:|---:|---|
| `id` | UUID PK | no | `UUIDPrimaryKeyMixin` |
| `tenant_id` | UUID | no | `TenantScopedMixin` |
| `person_uid` | UUID | no | plain UUID reference to `identity.person.id` |
| `source_provider` | String(32) | no | usually `carestack` |
| `source_id` | String(240) | no | provider appointment id |
| `source_event_id` | UUID | yes | raw event pointer |
| `scheduled_start_at` | TIMESTAMPTZ | no | appointment start |
| `scheduled_end_at` | TIMESTAMPTZ | yes | appointment end if available |
| `status` | String(24) | no | `scheduled`, `rescheduled`, `cancelled`, `completed`, `no_show`, `unknown` |
| `appointment_type` | String(120) | yes | only if in allowlist; no procedure notes |
| `location_ref` | String(120) | yes | CareStack location id or safe label |
| `provider_ref` | String(120) | yes | CareStack provider id, not clinical note |
| `coordinator_ref` | String(120) | yes | optional staff/coordinator id |
| `source_created_at` | TIMESTAMPTZ | yes | provider-created time |
| `source_updated_at` | TIMESTAMPTZ | yes | provider-modified time |
| `raw_marketing` | JSONB | no | allowlisted scheduling fields only |
| `created_at` / `updated_at` | TIMESTAMPTZ | no | `TimestampMixin` |

Constraints and indexes:

- CHECK `status IN ('scheduled', 'rescheduled', 'cancelled', 'completed', 'no_show', 'unknown')`.
- `UNIQUE (tenant_id, source_provider, source_id)`.
- `ix_consultation_person_scheduled` on `(tenant_id, person_uid, scheduled_start_at DESC)`.
- `ix_consultation_status_scheduled` on `(tenant_id, status, scheduled_start_at)`.
- `ix_consultation_source_event` on `(tenant_id, source_event_id)`.

Allowlist for `raw_marketing`:

- appointment id
- appointment datetime / start / end
- status
- appointment type only if reviewed as operational
- created/modified timestamps
- location id/ref
- provider/coordinator ids

Explicitly forbidden in `ops.consultation`:

- DOB, clinical notes, treatment notes, findings, plan, chief complaint,
  medical history, allergies, prescriptions, imaging/x-ray references,
  procedure codes, diagnosis fields, and arbitrary provider free text.

## Match Policy

The default behavior should be automated.

### Tier 0: Exact Source Resolution

If `identity.source_link` already has `(tenant_id, source_system, source_kind,
source_id)`, return that `person_uid`, touch `last_seen_at`, and do not create
a new `match_candidate`.

### Tier 1: High-Confidence Auto-Accept

If no source link exists, build `ingest.normalized_person_hint` and search
within the tenant for candidate persons by normalized phone and email.

Auto-accept when all are true:

- exactly one candidate person is found;
- no competing person has the same normalized phone/email evidence;
- no strong name conflict;
- tenant/location context is compatible;
- score is above threshold.

Recommended first thresholds:

- exact normalized phone + exact normalized email: `0.99`, auto-accept.
- exact phone + compatible name: `0.95`, auto-accept.
- exact email + compatible name and no competing phone conflict: `0.92`,
  auto-accept.
- exact phone or exact email without name evidence: below auto threshold,
  leave open unless later product policy says otherwise.

Auto-accept action:

1. Insert `identity.match_candidate(status='auto_accepted', evidence=...)`.
2. Add `identity.source_link` for the incoming source to the accepted person.
3. Add missing `person_identifier` rows when safe and non-conflicting.
4. If two persons already exist, call `IdentityService.record_merge(...)` and
   explicit downstream domain merge handlers. Do not let `IdentityService`
   silently rewrite every domain reference.

### Tier 2: Open Candidate

Leave `status='open'` when evidence is ambiguous:

- multiple candidate persons share the phone/email;
- name conflict;
- shared family email/phone pattern;
- phone-only or email-only evidence below threshold;
- tenant/location context conflicts;
- malformed identifier normalization.

Open candidates must not block the provider pull. The system should create or
keep the source-linked person and continue writing `ops.inquiry` /
`ops.consultation`; later reconciliation can supersede or merge.

### Tier 3: Rejected / Superseded

Use `rejected` when later evidence proves the candidate is wrong. Use
`superseded` when a stronger candidate replaces an open one. These states are
important for preventing repeated re-opening of the same bad match.

## Service and Repository Boundaries

### `packages/ingest`

Add:

- `NormalizedPersonHint` model.
- `NormalizedPersonHintIn/Out` schemas.
- `IngestRepository.add_normalized_hint(...)`,
  `find_hint_by_raw_event(...)`, `list_unresolved_hints(...)`.
- `IngestService.capture_normalized_person_hint(...)`.

Do not import identity repository or ops repository. A provider-specific
normalizer can call `IngestService`, then pass the resulting DTO/id into
`IdentityService`.

### `packages/identity`

Add:

- `MatchCandidate` model.
- `MatchCandidateIn/Out` schemas.
- Repository methods:
  - `list_candidate_persons_by_identifiers(tenant_id, email, phone)`.
  - `add_match_candidate(...)`.
  - `find_open_match_for_pair(...)`.
  - `mark_match_decided(...)`.
- Service methods:
  - `resolve_or_create_from_hint(...)` as the new provider entry point.
  - `evaluate_match_policy(...)`.
  - `auto_accept_match(...)`.

The existing `resolve_or_create_person(...)` can stay as exact-source-link
primitive. Move Salesforce's hidden email/phone reactivation behavior out of
`SfLeadIngestService._resolve_person` and into the identity service/policy.

### `packages/ops`

Add:

- `Inquiry` and `Consultation` models.
- DTOs for upsert inputs and outputs.
- Repository methods:
  - `find_inquiry_by_source(...)`, `add_inquiry(...)`.
  - `find_consultation_by_source(...)`, `add_consultation(...)`.
  - person/status list/count helpers only when needed by UI.
- Service methods:
  - `upsert_inquiry(...) -> UpsertInquiryResult`.
  - `upsert_consultation(...) -> UpsertConsultationResult`.

Both upserts should return `was_created`, `was_changed`, and a narrow
`change_kind` string so worker code can decide whether to emit
`interaction.event`.

### No PHI Leakage Into `ops`

- Provider raw payloads stay in `ingest.raw_event`.
- `ops.inquiry.raw_marketing` and `ops.consultation.raw_marketing` must be
  built from explicit allowlists.
- Do not duplicate phone/email/name into ops tables; join via `person_uid` and
  `IdentityService` projections when the UI needs them.
- CareStack patient/profile clinical data goes only through `PhiService` when
  that phase lands. This ENG-181 plan does not require any `phi` writes.

## Migration Strategy

Use additive Alembic revisions only. Do not edit shipped revisions.

Likely revision order:

1. `add_ingest_normalized_person_hint`
   - `packages/ingest/models.py`
   - `packages/ingest/repository.py`
   - `packages/ingest/service.py`
   - `packages/ingest/schemas.py`
   - `packages/db/alembic/versions/<rev>_add_ingest_normalized_person_hint.py`
   - `docs/data-model/CATALOG.md`
   - `packages/ingest/CLAUDE.md`
   - tests under `tests/ingest/`

2. `add_identity_match_candidate`
   - `packages/identity/models.py`
   - `packages/identity/repository.py`
   - `packages/identity/service.py`
   - `packages/identity/schemas.py`
   - `packages/db/alembic/versions/<rev>_add_identity_match_candidate.py`
   - `docs/data-model/CATALOG.md`
   - `packages/identity/CLAUDE.md`
   - tests under `tests/identity/`

3. `add_ops_inquiry_consultation`
   - `packages/ops/models.py`
   - `packages/ops/repository.py`
   - `packages/ops/service.py`
   - `packages/ops/schemas.py`
   - `packages/db/alembic/versions/<rev>_add_ops_inquiry_consultation.py`
   - `docs/data-model/CATALOG.md`
   - `packages/ops/CLAUDE.md`
   - tests under `tests/ops/`

4. Provider pipeline adaptation after the schema/service PRs:
   - `packages/ingest/sf_lead_service.py`
   - new CareStack ingest service under `packages/ingest/` or worker job layer
   - worker/API trigger tests
   - interaction-event tests

Before generating migrations, resolve the existing Alembic drift tracked by
ENG-188. Otherwise new autogenerate output may mix intended tables with
pre-existing tenant/index drift.

## Suggested Agent Split

### PR / Agent 1: Ingest Hints

Write scope:

- `packages/ingest/*`
- `tests/ingest/*`
- one new Alembic revision
- `docs/data-model/CATALOG.md`
- `packages/ingest/CLAUDE.md`

Tests:

- model metadata columns/indexes;
- service creates one hint per raw event;
- normalizer does not mutate raw event payload;
- invalid email/phone stored as quality flag, not a crash.

### PR / Agent 2: Identity Match Policy

Write scope:

- `packages/identity/*`
- `tests/identity/*`
- one new Alembic revision
- `docs/data-model/CATALOG.md`
- `packages/identity/CLAUDE.md`

Tests:

- source-link exact hit returns existing person;
- email+phone+compatible name auto-accepts;
- competing candidates stay `open`;
- auto-accepted two-person case writes `merge_event`;
- no cross-tenant candidate leakage.

### PR / Agent 3: Ops Canonical Objects

Write scope:

- `packages/ops/*`
- `tests/ops/*`
- one new Alembic revision
- `docs/data-model/CATALOG.md`
- `packages/ops/CLAUDE.md`

Tests:

- `upsert_inquiry` inserts/updates/idempotently no-ops by source key;
- repeated Salesforce Lead submissions create separate inquiries, not duplicate
  people;
- `upsert_consultation` inserts/updates/idempotently no-ops by source key;
- CareStack forbidden clinical fields are dropped from `raw_marketing`;
- `ops` still imports no `phi`.

### PR / Agent 4: Pipeline Integration

Write scope after PRs 1-3 merge:

- `packages/ingest/sf_lead_service.py`
- new CareStack ingest/pull service files
- worker/API trigger tests only as needed

Tests:

- Salesforce Lead pull uses `normalized_person_hint` and identity match policy;
- CareStack patient + appointment path writes raw events, hints, source links,
  `ops.consultation`, and interaction events;
- ambiguous match does not block `ops.inquiry` / `ops.consultation`;
- high-confidence Salesforce/CareStack match becomes one `person_uid`
  automatically.

## Blockers / Unknowns

- Existing `alembic check` drift must be resolved before reliable new
  autogeneration.
- Existing global uniqueness on `identity.person_identifier(kind, value)` and
  `identity.source_link(source_system, source_kind, source_id)` is risky for
  multi-tenant production. New tables should be tenant-scoped; old uniqueness
  should be corrected in a dedicated migration if not already planned.
- Exact CareStack appointment and patient field names should be confirmed
  against the local CareStack docs before coding allowlists.
- Match thresholds need product approval, but the implementation can ship with
  conservative thresholds and full evidence logging.
- Domain merge handlers beyond identity are not designed yet. Initial auto-link
  should prefer attaching a new source link to an existing person before
  creating duplicates.

## Files Changed

- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/P2-data-foundation-implementation-plan.md`

## Tests / Checks

- Not run. This was a read-only architecture/report task.

## Linear Notes

- Recommended Linear status for ENG-181: keep `In Review` until the
  orchestrator accepts the plan and breaks implementation into PR tasks.
- Suggested child implementation issues:
  - Ingest normalized person hints.
  - Identity match candidate + auto-accept policy.
  - Ops inquiry + consultation canonical objects.
  - Salesforce/CareStack pipeline integration against the new services.
