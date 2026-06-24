# CLAUDE.md — `packages/interaction`

Phase 1 slim subset: a single table, ``interaction.event``, that holds the
append-only semantic timeline of every Person.

Full v0.2 design (event_content, transcript_artifact, message_artifact) is
in `docs/plans/2026-04-30-full-schema-v0_2.md` §5 and lands in M3 with
FUS-16. Don't add those tables here in Phase 1.

## Tables (schema `interaction`)

- **`event`** — semantic events (`lead_created`, `lead_updated`,
  `consultation_scheduled`, `consultation_rescheduled`,
  `consultation_cancelled`, `consultation_completed`,
  `consultation_no_show`, `task_created`, `task_completed`,
  `call_logged`, `call_reference_found`, `treatment_proposed`,
  `treatment_completed`, `invoice_created`, `case_opened`,
  `case_closed`, `opportunity_created`, `opportunity_won`,
  `opportunity_lost`, `opportunity_stage_changed`, `contact_created`,
  `payment_recorded`, `payment_refunded`,
  `payment_reversed`, `payment_applied`, `treatment_accepted`,
  `surgery_scheduled`, `surgery_completed`; legacy `consultation_created`
  remains accepted for already-shipped Phase 1 callers). Linked to
  `identity.person.id` (RESTRICT delete) and optionally to
  `ingest.raw_event.id` (RESTRICT delete; raw events are forensic and
  never dropped). Each workflow-ready event carries `data_class`,
  `source_kind`, `source_external_id`, optional `projection_ref_*`, and
  `review_status`. Primary timeline index: `(person_uid, occurred_at)`.

## Hard rules

- **`summary` and `payload` are no-PII.** Action verb + provider +
  non-PII source_id only. NEVER name, email, phone, DOB, address,
  MRN, clinical free-text. The Phase 1 PII fixture set is the union
  of fields in W2 (CareStack) tests; that set is the canonical
  forbidden list.
- **Use `summary_for_event(kind, source_provider, source_id)`** to
  build summaries. Direct string-formatting in callers is a
  code-review event — it makes the no-PII contract bypass-able.
- **`payload`** is structured non-PII fields. PII-bearing data lives
  in `ingest.raw_event.payload` (which is governed by
  `packages/ingest/CLAUDE.md` carve-out rules).
- **Append-only at the model layer.** No `update_*` or `delete_*` is
  defined on `InteractionService` in Phase 1. Future kinds can
  supersede earlier rows by emitting new events; the timeline reads
  in occurred_at-order.
- **Cross-pull idempotency is NOT this package's job.** The partial
  UNIQUE catches single-pipeline-run replays of the same
  `(source_provider, source_event_id)`. Re-pulls produce new
  `ingest.raw_event` rows -> new `source_event_id` -> no UNIQUE
  collision. Workers (W1/W2) suppress no-op interaction emission via
  `was_changed` returned from `OpsService.upsert_*`.

## Service responsibilities

`InteractionService` is the public surface. Every other domain that wants
to write or read an event goes through it.

- `create_event(EventIn)` — append; idempotent on
  `(source_provider, source_event_id)` via partial UNIQUE +
  `IntegrityError` catch + lookup. The caller does NOT need to
  pre-check for existence.
- `list_for_person(person_uid, limit?, before?)` — newest-first
  timeline slice; cursor pagination on `occurred_at`.

`summary_for_event(...)` is a module-level helper, not a method —
callers (workers, future API DTOs) should use it directly.

## Cross-package imports

This package may import:

- `packages.core` (exceptions, types, logging, config) — always.
- That's it. No `identity` / `ops` / `phi` / `actor` / `auth` /
  `integrations` / `audit` / `ingest` imports.

Cross-domain references go through the `person_uid` UUID column (no DB
FK across schemas — same convention as `interaction.event.person_uid`).
The FK strings in models (`"identity.person.id"`,
`"ingest.raw_event.id"`, `"actor.actor.id"`) are DB-level constraints,
not Python imports — they live as bare strings.

Tools, API routes, MCP tools, and worker jobs may import this package
(via `InteractionService`).

## `kind` allowed values

| kind                       | who emits           | trigger                                      |
|----------------------------|---------------------|----------------------------------------------|
| `lead_created`             | W1 (Salesforce)     | first time we see a Lead                     |
| `lead_updated`             | W1 (Salesforce)     | re-pull where `was_changed=true` on the lead |
| `consultation_scheduled`   | W2 (CareStack)      | first time we see a scheduled appointment    |
| `consultation_created`     | legacy Phase 1      | retained for existing callers / rows         |
| `consultation_rescheduled` | W2 (CareStack)      | `scheduled_at` changed on re-pull            |
| `consultation_cancelled`   | W2 (CareStack)      | `status` flipped to cancelled on re-pull     |
| `consultation_completed`   | W2 (CareStack)      | appointment completed                        |
| `consultation_no_show`     | W2 (CareStack)      | appointment marked no-show                   |
| `task_created`             | W1 (Salesforce)     | action-oriented Task creates follow-up       |
| `task_completed`           | W1 (Salesforce)     | action-oriented Task completed               |
| `call_logged`              | W1/Future call lane | call activity logged without raw transcript  |
| `call_reference_found`     | W1/Future call lane | call recording/reference URL discovered      |
| `treatment_proposed`       | W2 (CareStack)      | treatment procedure in planned/proposed state |
| `treatment_completed`      | W2 (CareStack)      | treatment procedure completed                |
| `invoice_created`          | W2 (CareStack)      | invoice created for billing                  |
| `case_opened`              | W1 (Salesforce)     | SF Case opened (IsClosed=false)              |
| `case_closed`              | W1 (Salesforce)     | SF Case closed (IsClosed=true)               |
| `opportunity_created`      | W1 (Salesforce)     | SF Opportunity open (not closed)             |
| `opportunity_won`          | W1 (Salesforce)     | SF Opportunity closed-won                    |
| `opportunity_lost`         | W1 (Salesforce)     | SF Opportunity closed-lost                   |
| `opportunity_stage_changed` | W1 (Salesforce)    | SF OpportunityHistory stage row (pipeline movement, ENG-382) |
| `contact_created`          | W1 (Salesforce)     | SF Contact captured (post-conversion identity, ENG-382) |
| `payment_recorded`         | W2 (CareStack)      | accounting-transaction `transactionCode` PATIENTPAYMENTS / INSURANCEPAYMENTS (real cash IN, ENG-283) |
| `payment_applied`          | W2 (CareStack)      | accounting-transaction `transactionCode` PATPAYMENTAPPLIED / INSPAYMENTAPPLIED (allocation leg, excluded from Collected, ENG-283) |
| `payment_refunded`         | W2 (CareStack)      | accounting-transaction `transactionCode` REFUND / PATIENTREFUND / INSURANCEREFUND |
| `payment_reversed`         | W2 (CareStack)      | accounting-transaction `transactionCode` PATIENTPAYMENTSDELETE OR row with `isReversed=true` |
| `treatment_accepted`       | W2 (CareStack)      | TreatmentPlan `StatusId=3` (Accepted), first observed; source_kind `carestack_treatment_plan` (ENG-511) |
| `surgery_scheduled`        | W2 (CareStack)      | implant-surgery treatment procedure `statusId=2` (Scheduled), CDT-gated (ENG-511) |
| `surgery_completed`        | W2 (CareStack)      | implant-surgery treatment procedure `statusId=8` (Completed), CDT-gated (ENG-511) |

Adding a new value = update `EVENT_KINDS` tuple in `models.py`,
update CHECK constraint in a new migration, update the schemas
`EventKind` Literal, update this table, update `_KIND_VERB` dict in
`service.py`. All four must move together.
