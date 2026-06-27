# Glossary — CareStack terms ↔ Fusion CRM domains

How CareStack's concepts land in our `packages/*` domain model.
Use this as a decision table when writing an adapter.

## PHI classification — our rule

A field is PHI in Fusion if it is one of:
- Clinical content (diagnoses, procedures, notes, vitals, allergies,
  medications, imaging).
- Identifiers attached to clinical context (DOB bound to a medical
  record; an appointment slot tied to a patient name).
- Payments/insurance when tied to a specific person's care.

Bare schedule/directory data (locations, providers, operatories,
procedure code catalog, payment types, referral source categories)
is NOT PHI on its own.

## Term map

| CareStack | Fusion domain | Fusion entity (target) | Notes |
|---|---|---|---|
| Patient | `identity` + `phi` | `identity.person` + `phi.patient_profile` | Split: name/phone/email → identity; DOB + demographics → phi |
| Patient external id | `identity` | `identity.person_identifier` (`kind="carestack_patient_id"`) | Primary join key |
| Appointment | new `scheduling` (TBD) | `scheduling.appointment` | References `person_uid`, `provider_id`, `location_id`; ties to PHI via chief complaint / notes |
| Provider | new `staff` (TBD) | `staff.provider` | non-PHI directory |
| User | new `staff` | `staff.user` | CareStack operator accounts |
| Location | new `clinic` (TBD) | `clinic.location` | |
| Facility | new `clinic` | `clinic.facility` | |
| Operatory | new `clinic` | `clinic.operatory` | |
| Referral source | `ops` | `ops.referral_source` | marketing, non-PHI |
| Medical alerts (allergies/conditions) | `phi` | `phi.medical_alert` (new) | PHI |
| Medications | `phi` | `phi.medication` (new) | PHI |
| Treatment plan | `phi` | `phi.treatment_plan` (new) | PHI |
| Periodontal chart | `phi` | `phi.perio_chart` (new) | PHI |
| Patient notes / memo | `phi` | `phi.patient_note` (new) | free-text clinical |
| Vital monitor | `phi` | `phi.vital` (new) | PHI |
| Referral document | `phi` | `phi.referral_document` (new) + `ingest` for raw | document is PHI |
| Procedure code | new `catalog` | `catalog.procedure_code` | code dictionary, non-PHI |
| Payment type | `catalog` | `catalog.payment_type` | |
| Payment summary | new `billing` (TBD) | `billing.payment_summary` | per-patient — mixed PHI |
| Adjustment | `billing` | `billing.adjustment` | |
| Invoice (sync) | `billing` | `billing.invoice` | |
| Accounting procedure (sync) | `billing` | `billing.accounting_procedure` | |
| Accounting transaction (sync) | `billing` | `billing.accounting_transaction` | |
| Find slot | on-demand | no persistent row | read-through for UI |
| Insurance (patient-level) | `billing` | `billing.patient_insurance` | PHI when scoped to a patient |
| Insurance plan / payor / templates | `billing` | `billing.*` (flat catalogs) | non-PHI directory |
| Document upload | `ingest` + GCS | raw blob in GCS + `ingest.raw_event` | PHI if attached to a patient |

## Sync sources → our `ingest`

All seven CareStack sync endpoints feed into `ingest.raw_event` with
`source="carestack"` and `event_type=<resource>.<op>` (e.g.
`patient.upsert`, `appointment.upsert`). The per-event handler lives
in `apps/worker/jobs/ingest_carestack.py`.

## Identifiers — joining strategy

- Every CareStack `patientId` we see → an `identity.person_identifier`
  row with `kind="carestack_patient_id"`.
- Resolve/create path: `IdentityService.upsert_by_identifier(
  "carestack_patient_id", str(patient_id), defaults=...)`.
- First time we see a `patient`, also backfill phone/email identifiers
  if present in the CareStack payload.
