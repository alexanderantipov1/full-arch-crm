# CareStack integration — notes, plan, open questions

Working notes for the CareStack adapter. Updated as we go.

## Integration plan (phased)

### Phase 0 — foundation (prerequisites)

- Confirm per-account provisioning: `client_id`, `client_secret`,
  `username` (vendor), `password` (account).
- Decide where the per-account `password` lives: encrypted column on a
  future `clinic.account` row, OR mounted secret file per-deploy.
- Add `CARESTACK_IDP_URL`, `CARESTACK_CLIENT_ID`,
  `CARESTACK_CLIENT_SECRET`, `CARESTACK_VENDOR_KEY` to
  `packages.core.config.Settings` (global secrets).

### Phase 1 — adapter skeleton (`packages/integrations/carestack/`)

Structure (proposed):

```
packages/integrations/carestack/
├── __init__.py
├── client.py         # async httpx + token refresh + retry
├── auth.py           # token acquisition + Redis cache
├── schemas/          # pydantic models for CareStack payloads (camelCase)
│   ├── patient.py
│   ├── appointment.py
│   └── ...
├── mappers/          # CareStack DTO  →  Fusion domain DTO
│   ├── patient.py
│   └── appointment.py
├── sync.py           # cursor-driven polling helpers
└── errors.py         # CareStack-specific → IntegrationError
```

### Phase 2 — identity + patient sync

- Add `identity.person_identifier` kind: `carestack_patient_id`.
- Worker job: `apps/worker/jobs/ingest_carestack_patients.py`
  - Cron every 5 min.
  - Pull `GET /v1.0/sync/patients?modifiedAfter=<cursor>`.
  - Write each page to `ingest.raw_event`
    (`source="carestack"`, `event_type="patient.upsert"`).
  - Handler → `IdentityService.upsert_by_identifier(...)` +
    `PhiService.upsert_profile(...)` for DOB / demographics.
- Add `ingest.sync_cursor` table:
  `(source text, resource text, watermark timestamptz)` PK
  `(source, resource)`.

### Phase 3 — appointments

- Create `scheduling` domain with `scheduling.appointment`.
- Sync via `GET /v1.0/sync/appointments` (same cadence as patients).
- References: `person_uid`, `provider_id`, `location_id`.
- PHI-flavoured (chief complaint, notes) — treat whole payload as
  PHI.

### Phase 4 — clinical feeds

- Treatment Procedure sync + Existing Treatment Procedure sync.
- Medical Alerts, Medications (on-demand, not sync — fetch per patient
  when the profile is opened or during a nightly refresh).
- Treatment plans, perio charts, vitals — on-demand per patient.

### Phase 5 — billing

- Invoice sync, Accounting Procedure sync, Accounting Transaction
  sync → new `billing` domain.
- Adjustments + payment summary + payment types as catalog.

### Phase 6 — insurance manager

- Full Insurance Manager module. Defer until clinical + billing base
  is stable. Most of it is directory-like (plans, payors, templates);
  not PHI on its own.

### Phase 7 — writes (create/update/delete)

- Initially the adapter is READ-ONLY. Writes (create appointment,
  update patient, add note) come after Phase 2–4 are solid.

## Cadence (first cut)

| Feed | Cadence |
|---|---|
| Patients sync | every 5 min |
| Appointments sync | every 5 min |
| Treatment procedures | every 15 min |
| Existing treatment procedures | every 15 min (bootstrap) |
| Invoices | every 15 min |
| Accounting procedure | every 30 min |
| Accounting transaction | every 30 min |
| Catalogs (procedure codes, payment types) | nightly |
| Insurance plans / payors | manual or nightly |

## PHI stance

- **Every CareStack sync payload is treated as potentially PHI.**
  `ingest.raw_event.payload` is JSONB — restrict read access, never
  surface verbatim payloads to ops dashboards or LLM contexts.
- **Never log payload bodies.** Log: `event_type`, `external_id`,
  `received_at`, counts. Nothing else.
- **Documents (files)** are PHI by default when associated with a
  patient. Store blobs in GCS with uniform bucket-level access and
  audit reads via `PhiService` equivalents for files (TBD).

## Open questions (follow up in PDF or with CareStack support)

### Spec ambiguities captured during extraction

- `appointments`: notes max length — 1000 (model) vs 2000 (body)?
- `providers`: `providerType` string vs integer mismatch between
  list and detail responses; no enum dictionary given.
- `slots`: `productionTyeId` — probable typo for `productionTypeId`.
- `medications`: model appears thinner than reality — confirm fields.
- `documents`: `Type` enum values missing from the dump.
- `facility`: single-object vs list return unclear.
- `treatment-plans`: return shape (object vs list) unclear.
- `patient-notes`: PUT/DELETE success codes not explicit.
- `search/patients`: spec path actually `v2.0`? `LocationName` with
  no id — need to join locally.
- `search/appointments`: `/scheduler/` prefix; `DateTimeUTC` vs
  `dateTime` case inconsistency.
- `sync/patients`: Patient object attributes not in this section —
  cross-check with Resource 3.
- `sync/appointments`: `startTime` vs `startDateTime`; no `isDeleted`
  flag — how are deletions represented?
- `sync/treatment-procedures`: `tooth` shown unquoted with commas in
  example — confirm string vs list.
- `sync/existing-treatment-procedures`: one-table vs two-table
  modelling decision on our side.
- `sync/invoices`: `invoiceSource=6` spelled "PaymenLink" in spec
  (likely typo).
- `sync/accounting-transactions`: next-page URL prefix `/billing/`
  differs from initial URL; full `transactionCode` enum cut off.
- `insurance-manager/plans`: many string enum values undocumented.
- `insurance-manager/payors`: several spec typos flagged per file.

### Design questions

- Per-account client concurrency: one `httpx.AsyncClient` per account,
  or a pool? (single is simpler; pool if we run multi-clinic).
- Webhook support: does CareStack offer webhooks for real-time
  updates, or is polling the only option? (spec is polling-only).
- Soft-delete semantics: how to recognise a deleted patient /
  appointment in a sync feed?
- Historical backfill: safest `modifiedAfter` starting watermark for
  a fresh clinic — probably "1970-01-01" but paginate carefully.

## Next steps (concrete, in order)

1. Resolve the top 3 ambiguities that block Phase 2 (patient sync
   field shape, soft-delete semantics, watermark semantics).
2. Create `ingest.sync_cursor` migration.
3. Draft `packages/integrations/carestack/client.py` + `auth.py`.
4. Write the first sync job for patients; run against a sandbox
   account; verify `raw_event` rows + `identity.person` upsert.
5. Add structured tests that replay a captured `raw_event` payload
   and assert deterministic mapping.
