# Data Model Catalog

**Single source of truth for all database tables in Fusion CRM.**

Update this file in the same PR/commit as any migration that adds, renames or
removes a table or external-identifier kind. CI / review may block changes that
do not update the catalog.

---

## Hard rules — read before adding ANY table or column

1. **Canonical Domain Model.** Tables in `identity`, `ops`, `phi` are the *only*
   truth for people, leads, accounts, clinical data. Never create
   `salesforce_lead`, `hubspot_contact`, `carestack_patient`, etc. Provider data
   is mapped into the canonical tables.

2. **External IDs go to `identity.person_identifier`.** One `Person` may have
   N identifiers from N systems (`salesforce_contact_id`, `hubspot_contact_id`,
   `carestack_patient_id`, …). Adding a new external-system kind = add a row to
   the "External ID kinds" table below.

3. **Raw payloads go to `ingest.raw_event`.** Never lose data — every webhook,
   CDC event or API pull writes the original JSON to `raw_event` keyed by
   `(source, kind)` for audit and future reprocessing.

4. **Provider-specific tables don't exist.** Integration plumbing (creds,
   tokens, mappings, sync runs, cursors) lives in schema `integrations`.
   Anything domain-shaped goes in the canonical schemas.

5. **Generic safe for rare objects:** `integrations.external_entity` holds
   provider objects that don't yet have a canonical home (Opportunity, Case,
   Quote, Order, …). When such an object earns a real domain table, migrate it
   out and update this catalog.

6. **PHI is reachable only through `PhiService`.** Mapping clinical data from
   external systems into `phi.*` requires a service call that audits the access
   and checks `Principal.can_read_phi()`. Integration sync code MUST call
   `PhiService.upsert(...)` (or another `PhiService.*` method) — never a
   `phi.*` repository directly, and never `phi.*` ORM models from a non-`phi`
   package. CareStack `Patient` is the canonical example: every Patient pulled
   from CareStack lands in `phi.patient_profile` ONLY through `PhiService`,
   keyed by `identity.person_identifier(kind='carestack_patient_id')`.

---

## Domain schemas

### `identity` — canonical "who is this person"

| Table | Purpose | External IDs (kinds) | Notes |
|---|---|---|---|
| `identity.person` | One row per real human; UUID = `person_uid` referenced everywhere | — | Phone/email/name normalized here |
| `identity.person_identifier` | Maps a Person to N external system IDs | (see "External ID kinds" below) | `(kind, value)` is unique |

### `ops` — non-clinical CRM (PHI-free)

| Table | Purpose | External IDs (kinds) | Notes |
|---|---|---|---|
| `ops.lead` | CRM lead pipeline | `salesforce_lead_id` | PHI-free; safe for AI tools |
| `ops.followup_task` | Reminder tasks | `salesforce_task_id` (optional) | Referenced from `interaction.event` with `projection_ref_type='ops_followup_task'` |
| `ops.account` *(planned)* | Organization / company / household | `salesforce_account_id`, `hubspot_company_id` | Added with the Salesforce integration |
| `ops.consultation` | Marketing-safe appointment / consultation projection | Salesforce Event id, CareStack Appointment id | Clinical notes and treatment payloads stay outside `ops`; `provider_created_at` stores provider-side booking create time for dashboard date filters |
| `ops.person_location_profile` | Per-location relationship state for a global person | evidence source ids only | Completed consultation evidence may promote to patient; imported row existence alone must not |

### `phi` — clinical PHI (reachable only via `PhiService`)

| Table | Purpose | External IDs (kinds) | Notes |
|---|---|---|---|
| `phi.patient_profile` | Clinical profile per Person | (none — clinical data not auto-mapped) | Manual mapping only, audited |
| `phi.consultation` | Visit / consultation record | (none) | |

### `ingest` — raw inbound events

| Table | Purpose | External IDs (kinds) | Notes |
|---|---|---|---|
| `ingest.raw_event` | Raw JSON payloads from any external system | `source` + `kind` discriminate | Append-only, never deleted |

### `interaction` — workflow-ready semantic timeline

| Table | Purpose | External IDs (kinds) | Notes |
|---|---|---|---|
| `interaction.event` | Append-only person timeline events normalized from provider evidence | `source_provider`, `source_kind`, `source_external_id` | No-PII `summary` and no-PII structured `payload`; references `ingest.raw_event.id` via `source_event_id` |

### `audit` — append-only access log

| Table | Purpose | External IDs (kinds) | Notes |
|---|---|---|---|
| `audit.access_log` | Every PHI access + every outbound integration write | — | Never deleted |

### `integrations` — provider plumbing only (no domain data)

| Table | Purpose | External IDs (kinds) | Notes |
|---|---|---|---|
| `integrations.integration_account` *(planned)* | Per-(provider, company) creds + OAuth tokens (encrypted) | — | `company_uid` = GLOBAL stub today, real multi-tenant later |
| `integrations.object_mapping` *(planned)* | Per-account field mapping JSON for each SObject | — | Edited via UI/API, not in code |
| `integrations.sync_run` | Journal of inbound/pull/push/cdc/webhook batches | — | Operational telemetry; provider-level runs store `provider`, `object_scope`, and `trigger` in `meta` |
| `integrations.cdc_cursor` *(planned)* | Last-processed Replay-Id per CDC channel | — | Lets the worker resume |
| `integrations.external_entity` *(planned)* | Generic safe for SF objects without a canonical home | provider-scoped `external_id` | Migrate out when an object earns a real table |

### `analytics` — read-model layer (rebuildable projection, NEVER a source of truth)

Operator-approved schema (ENG-504 / ENG-505, ADR-0007). Derived from the
canonical schemas by the fact builder (ENG-506); may be dropped and rebuilt at
any time. Nothing writes here except the builder service. No PHI — only dates,
money, and reference ids.

| Table | Purpose | External IDs (kinds) | Notes |
|---|---|---|---|
| `analytics.fact_patient_journey` | One row per `person_uid` tracing ad spend → collected revenue (dimensions + stage timestamps + money) | — | Every column nullable except `person_uid` PK; plain UUID columns (no cross-domain FK); `field_provenance` JSONB holds per-field `{source, method: auto\|manual\|unresolved, confidence, resolved_at}`; `location_id` → `tenant.location.id` for aggregate/per-location filtering |

---

## Workflow-ready `interaction.event`

`interaction.event` is the normalized, workflow-ready person timeline derived
from `ingest.raw_event` evidence and canonical projections. The operational
read surface is `GET /persons/{uid}/operational-timeline`, which intentionally
returns safe timeline fields and projection snapshots rather than raw provider
payloads.

### Workflow-ready columns

| Column | Purpose | Allowed values / notes |
|---|---|---|
| `data_class` | Sensitivity and routing class for the timeline row | `public`, `operational`, `clinical_summary`, `phi_protected`, `billing`, `call_recording_ref` |
| `source_kind` | Provider object kind that produced the event | `salesforce_lead`, `salesforce_event`, `salesforce_task`, `salesforce_opportunity`, `salesforce_case`, `carestack_appointment`, `carestack_patient`, `carestack_treatment_procedure`, `carestack_invoice`; must match `source_provider` |
| `source_external_id` | Provider object id for the row that produced the event | Required for provider-origin events; never stores names, emails, phones, notes, or clinical text |
| `projection_ref_type` | Canonical projection type linked from the event | `ops_lead`, `ops_consultation`, `ops_followup_task`; nullable only when there is no current projection |
| `projection_ref_id` | UUID of the referenced canonical projection | Required when `projection_ref_type` is set |
| `review_status` | Review state for automatic or human-reviewed interpretation | `auto`, `pending_review`, `reviewed`, `rejected` |

Projection links:

- `projection_ref_type='ops_lead'` points to `ops.lead.id`.
- `projection_ref_type='ops_consultation'` points to `ops.consultation.id`.
- `projection_ref_type='ops_followup_task'` points to `ops.followup_task.id`.

### `interaction.event.kind` taxonomy

| Kind | Meaning |
|---|---|
| `lead_created` | A Salesforce Lead first created a canonical `ops.lead` projection for the person. |
| `lead_updated` | A Salesforce Lead re-pull changed the existing `ops.lead` projection. |
| `consultation_scheduled` | A Salesforce Event or CareStack Appointment created a scheduled `ops.consultation`. |
| `consultation_rescheduled` | The consultation's scheduled time or scheduled-state evidence changed. |
| `consultation_cancelled` | The provider evidence marked the consultation cancelled. |
| `consultation_completed` | The provider evidence marked the consultation completed. |
| `consultation_no_show` | The provider evidence marked the consultation as no-show. |
| `task_created` | A Salesforce Task created an actionable `ops.followup_task` projection. |
| `task_completed` | A Salesforce Task marked the linked follow-up task completed. |
| `call_logged` | A call activity was captured without a safe recording or meeting reference. |
| `call_reference_found` | A safe call or meeting reference was detected and stored as a pointer, not fetched content. |
| `treatment_proposed` | CareStack treatment evidence proposed treatment activity without exposing clinical free text. |
| `treatment_completed` | CareStack treatment evidence completed treatment activity without exposing clinical free text. |
| `invoice_created` | CareStack invoice evidence created billing-sensitive timeline activity. |
| `case_opened` | Salesforce Case evidence opened a safe operational case timeline row. |
| `case_closed` | Salesforce Case evidence closed a safe operational case timeline row. |
| `opportunity_created` | Salesforce Opportunity evidence created an operational opportunity timeline row. |
| `opportunity_won` | Salesforce Opportunity evidence marked an opportunity as won. |
| `opportunity_lost` | Salesforce Opportunity evidence marked an opportunity as lost. |

Legacy note: `consultation_created` remains accepted by the model for already
shipped Phase 1 callers and rows, but new workflow-ready emitters should use
`consultation_scheduled`.

## `integrations.sync_run`

`integrations.sync_run` is the operational journal for provider batches.
Provider-level scheduled/manual pulls open one row before work begins and close
it after the batch terminates; `audit.access_log` mirrors the terminal outcome.

| Field | Purpose |
|---|---|
| `direction` | Batch lane: `inbound`, `pull`, `push`, `cdc`, or `webhook`. |
| `status` | Lifecycle state: `running`, `succeeded`, `failed`, `partial`, or `skipped_credential`; `success` remains accepted for legacy rows. |
| `sf_object` | Historical column name that now holds provider object scope such as `Lead`, `Event`, `Task`, `Patient`, `Appointment`, or a combined provider scope. |
| `records_total`, `records_succeeded`, `records_failed` | Batch counters used by operator status and audit summaries. |
| `meta.provider` | Provider name, currently `salesforce` or `carestack` for workflow-ready ingest. |
| `meta.object_scope` | Provider object or grouped object scope covered by the run. |
| `meta.trigger` | Run trigger such as scheduled job or manual sync request. |

`skipped_credential` records a real attempted run where no usable active
credential existed; it is still audit-relevant operational telemetry.

---

## External ID kinds

Reserved values for `identity.person_identifier.kind`. Add new rows here BEFORE
using a new kind in code.

| Kind | Source system | Value format | Status |
|---|---|---|---|
| `phone` | normalized E.164 | `+15551234567` | live |
| `email` | normalized lowercase | `jane@example.com` | live |
| `carestack_patient_id` | CareStack | numeric/string as supplied | reserved (added with CareStack integration) — Patient → `phi.patient_profile` ONLY via `PhiService` |
| `carestack_appointment_id` | CareStack | as-supplied | reserved (added with CareStack integration) — Appointment → `integrations.external_entity` until promoted |
| `carestack_provider_id` | CareStack | as-supplied | reserved (added with CareStack integration) — Provider/staff member |
| `carestack_location_id` | CareStack | as-supplied | reserved (added with CareStack integration) — Clinic location |
| `salesforce_contact_id` | Salesforce | 18-char Id | reserved |
| `salesforce_lead_id` | Salesforce | 18-char Id | reserved (added with SF integration) |
| `salesforce_account_id` | Salesforce | 18-char Id | reserved (added with SF integration) |
| `hubspot_contact_id` | HubSpot | numeric vid | reserved (planned) |
| `hubspot_company_id` | HubSpot | numeric companyId | reserved (planned) |

---

## Checklist — "Before I create a new table or column"

Run through this every time a migration is on the table:

1. Open this file. Could this entity already be `identity.person`,
   `ops.lead`, `ops.account`, or one of the `phi.*` tables under another name?
   If yes → use the existing table.
2. Is it "a person / lead / account / company from a provider"? → Not a new
   table. Use canonical table + `person_identifier`.
3. Is it "an event from a provider"? → Not a new table. Use
   `ingest.raw_event(source=…, kind=…)`.
4. Is it a real new business entity with its own lifecycle (e.g., Opportunity)?
   → Add it to the *existing* domain package (`ops`, `phi`, …) — never to
   `packages/integrations/`. Integration is transport, not the home of data.
5. Is it ad-hoc or rare? → Stash it in `integrations.external_entity`. Promote
   to a real domain table only when usage proves it out.
6. Update this CATALOG in the same commit as the migration.

---

## Process

- Migrations are generated via `make db-revision M="…"` inside the api
  container, then copied to `packages/db/alembic/versions/` on the host.
- Every migration must:
  - register its models in `packages/db/registry.py`
  - declare its schema in `infra/docker/init-schemas.sql` and in
    `DOMAIN_SCHEMAS` in `packages/db/alembic/env.py`
  - update this CATALOG.md
- Renames/removals: keep the old row in CATALOG with `(removed YYYY-MM-DD,
  see <new>)` for one release before deleting.
