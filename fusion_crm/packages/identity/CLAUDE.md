# CLAUDE.md — `packages/identity`

The global `Person`. The ID of a `Person` row is the **`person_uid`**
that every other domain uses to reference a human.

## Tables (schema `identity`)

- **`person`** — canonical record. Holds non-clinical demographic
  fields only: names, display name, plus ENG-309 identity-strength
  signals `dob` (DATE, nullable) and `ssn` (VARCHAR(32), nullable,
  digit-only normalised). DOB/SSN are HARD VETO inputs to the
  resolver — different DOB or different SSN → never merge — and
  must never be logged or written into `MatchCandidate.evidence`.
- **`person_identifier`** — external aliases: phone, email, CareStack
  patient id, Salesforce contact id, etc. `(kind, value)` is unique.
- **`source_link`** — provenance: which external system instance first
  introduced this Person and under what record id. Distinct from
  `person_identifier`: identifiers are aliases for resolution
  (find a Person by phone or email); source links record where the
  Person came from. `(tenant_id, source_system, source_instance,
  source_kind, source_id)` is unique when `source_id IS NOT NULL`.
- **`merge_event`** — append-only record of when two Persons were
  collapsed. The retired row's `person_uid` stays stable (never
  deleted); references resolve via the merge chain.

## Service responsibilities

`IdentityService` is the public surface. Anything that wants to find
or create a `Person` goes through it.

- `resolve_by_phone` / `resolve_by_email` — lookup by normalised id.
- `get_person(person_uid)` — raises `NotFoundError`.
- `create_person(payload)` — creates with identifiers in one UoW.
- `upsert_by_identifier(kind, value, defaults)` — find-or-create by
  alias (used by ingest handlers and tools).
- `resolve_or_create_person(source_system, source_kind, source_id,
  hints, source_instance?)` — find-or-create by external-system
  origin scoped to a provider/import instance. Returns a
  `ResolveResult(person, was_created)`. The canonical entry point
  for provider-pull workers (W1 / W2) when only exact provider
  origin is available. It performs source-link recapture only; use
  `resolve_or_create_from_hint` for conservative cross-provider
  auto-linking.
- `resolve_or_create_from_hint(hint: MatchHintIn)` — provider-neutral
  match policy entry point (ENG-185). Consumes the identity-owned
  `MatchHintIn` (built by the ingest-side adapter from a captured
  `ingest.normalized_person_hint` row) and applies the explicit tier
  ladder before writing an `identity.match_candidate` ledger row for
  every non-trivial decision. Returns a typed `ResolveFromHintResult`
  the caller (`SfLeadIngestService`, future CareStack handler) uses
  to populate `ops.lead` / `ops.inquiry` without owning matching
  policy. Tiers:
    * **Tier 0 (source-link recapture)** — exact
      `(source_system, source_instance, source_kind, source_id)` key
      is already on file inside the tenant. Touches `last_seen_at`,
      returns the existing person, writes **no** match candidate row.
    * **Tier 1 (auto-accept)** — exactly one existing person clears
      a high-confidence rule. The new source link is added to that
      person and a `MatchCandidate(status='auto_accepted')` row is
      written with the matched rule (`email_phone_name` 0.99 /
      `phone_name` 0.95 / `email_name` 0.92).
    * **Tier 2 (open ambiguous)** — multiple candidates or a single
      weak match (name conflict, phone conflict, identifier-only
      hit). Creates a new source-linked person, writes
      `MatchCandidate(status='open')` with `email_only_ambiguous`
      or `phone_only_ambiguous` and conflict evidence, and returns
      a usable `person_uid` so the caller never blocks on
      reconciliation.
    * **Fallback (brand-new person)** — no candidate matched at all;
      creates the person + source link, writes no candidate row.
  Idempotency: re-pulling the same hint reuses the existing active
  candidate row via the `uq_match_candidate_hint_candidate_active`
  partial unique guard and skips a second source-link write. Tier 0
  never writes a candidate row regardless of `hint_id`.
- `record_merge(surviving, merged, reason, evidence?, actor?)` —
  appends a `merge_event`. Does NOT rewrite cross-domain references
  (callers do that per their PHI / audit / idempotency rules).

## Hard rules

- **NEVER store clinical data here.** No allergies, no prescriptions,
  no diagnoses, no treatment notes, no chief complaint. Clinical
  attributes belong in `phi`.
- **DOB and SSN are demographic identity-strength signals (ENG-309
  carve-out, 2026-06-01 PHI policy update).** They live on `Person`
  alongside `given_name` / `family_name` because they identify a
  human, not because they describe a health state. The resolver
  applies them as HARD VETOES (different DOB or different SSN →
  never merge, no matter how many soft signals overlap). They MUST
  NEVER appear in log values or in `MatchCandidate.evidence` /
  `.conflicts` dicts; the deny-list keys `"dob"` and `"ssn"` stay in
  `_FORBIDDEN_EVIDENCE_KEYS` for that reason. The veto reads them
  as top-level `Person.dob` / `Person.ssn` and `MatchHintIn.dob` /
  `MatchHintIn.ssn`, not via evidence-dict lookups.
- **Normalise before storing.** Phones via `normalise_phone()`,
  emails via `normalise_email()`. Inserting raw user input bypasses
  the unique constraint and creates duplicate persons.
- **Adding a new identifier kind:** just use a new `kind` string —
  no DDL needed. Document the convention here.
- **Conservative automatic matching.** Avoiding incorrect merges is
  more important than avoiding duplicates. `resolve_or_create_person`
  matches ONLY on the exact tenant-scoped `(source_system,
  source_instance, source_kind, source_id)` key. Cross-provider/person-hint matching goes through
  `resolve_or_create_from_hint`: high-confidence rules auto-link;
  ambiguous evidence creates a separate source-linked Person plus an
  open `MatchCandidate`. Do not block ingestion waiting for manual
  review.
- **Append-only `merge_event`.** Reverse merges create new rows;
  nothing in this table is ever rewritten.
- This package is allowed to be imported by every other domain
  (read-only via `IdentityService`); the inverse is not allowed —
  `identity` does NOT import from `ops`/`phi`/`ingest`. The
  `MatchHintIn` DTO consumed by `resolve_or_create_from_hint` is the
  identity-owned contract; callers translate their provider rows
  (or the `ingest.normalized_person_hint` projection) into this DTO
  rather than passing a sibling package's schema.

## Identifier `kind` values in use

| kind                     | format                   | source        |
|--------------------------|--------------------------|---------------|
| `phone`                  | E.164 `+<cc>…` (US default; valid numbers only, ENG-463); unparseable input falls back to a ≥7-digit strip | manual + ingest |
| `email`                  | lower-cased              | manual + ingest |
| `carestack_patient_id`   | as-supplied              | CareStack ingest |
| `salesforce_contact_id`  | as-supplied              | Salesforce ingest |

Add a row above when you introduce a new kind.

## `source_link` allowed values

| field           | values                                                                              |
|-----------------|-------------------------------------------------------------------------------------|
| `source_system` | `salesforce`, `carestack`, `twilio`, `vapi`, `web_form`, `manual`, `import`         |
| `source_instance` | Provider/import instance slug, e.g. `salesforce-main`, `carestack-main`, `import-main` |
| `source_kind`   | `lead`, `contact`, `patient`, `caller`, `sms_sender`, `submitter`, `account` (ENG-382) |

CHECK constraints in the migration enforce `source_system` and `source_kind`.
Adding a new checked value = new migration + update of `SOURCE_SYSTEMS` /
`SOURCE_KINDS` tuples in `models.py`. New source instances do not require DDL;
use stable slugs and keep legacy default slugs in `DEFAULT_SOURCE_INSTANCES`.

## `merge_event.reason` allowed values

`duplicate_email`, `duplicate_phone`, `manual`, `cross_provider_match`.
